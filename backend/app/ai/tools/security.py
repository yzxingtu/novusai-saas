"""
工具执行安全模块

提供工具执行的安全防护：
- 输入参数 JSON Schema 校验
- 输出敏感数据脱敏
- 单次对话工具调用次数限制
- HTTP 工具 SSRF 防护
- 数据库工具 SQL 白名单
- 邮件工具频率限制
"""

import asyncio
import ipaddress
import re
import socket
from typing import Any
from urllib.parse import urlparse

from app.core.logging import LogManager
from app.core.i18n import _

logger = LogManager.get_logger("ai.tool.security")


# ============================================
# 异常定义
# ============================================

class ToolSecurityError(Exception):
    """工具安全基础异常"""
    pass


class ToolInputValidationError(ToolSecurityError):
    """输入参数校验失败"""
    pass


class ToolOutputTruncatedError(ToolSecurityError):
    """输出被截断"""
    pass


class ToolExecutionLimitExceeded(ToolSecurityError):
    """工具调用次数超限"""
    pass


class SSRFBlockedError(ToolSecurityError):
    """SSRF 攻击被阻止"""
    pass


class SqlInjectionBlockedError(ToolSecurityError):
    """SQL 注入被阻止"""
    pass


class EmailRateLimitError(ToolSecurityError):
    """邮件频率超限"""
    pass


# ============================================
# 输入参数校验
# ============================================

class InputValidator:
    """
    输入参数校验器

    按 JSON Schema 校验工具输入参数
    """

    @staticmethod
    def validate(input_schema: dict[str, Any] | None, inputs: dict[str, Any]) -> None:
        """
        校验输入参数是否符合 JSON Schema

        Args:
            input_schema: JSON Schema 定义（来自 ToolDefinition）
            inputs: 实际输入参数

        Raises:
            ToolInputValidationError: 校验失败
        """
        if not input_schema:
            return

        required = input_schema.get("required", [])
        properties = input_schema.get("properties", {})

        # 检查必填字段
        for field in required:
            if field not in inputs or inputs[field] is None:
                raise ToolInputValidationError(
                    _("tool.error.missing_required_param", field=field)
                )

        # 检查类型
        for name, value in inputs.items():
            if name not in properties:
                continue

            prop = properties[name]
            expected_type = prop.get("type")
            if expected_type and value is not None:
                if not InputValidator._check_type(value, expected_type):
                    raise ToolInputValidationError(
                        _("tool.error.param_type_mismatch",
                          name=name,
                          expected_type=expected_type,
                          actual_type=type(value).__name__)
                    )

    @staticmethod
    def _check_type(value: Any, expected: str) -> bool:
        """基础类型检查"""
        type_map = {
            "string": str,
            "integer": int,
            "number": (int, float),
            "boolean": bool,
            "array": list,
            "object": dict,
        }
        expected_types = type_map.get(expected)
        if expected_types is None:
            return True
        return isinstance(value, expected_types)


# ============================================
# 输出脱敏
# ============================================

# 敏感数据正则模式
_SENSITIVE_PATTERNS = [
    # API Key / Token
    (re.compile(r'(?i)(api[_-]?key|token|secret|password|passwd|authorization)\s*[:=]\s*["\']?([a-zA-Z0-9_\-/.]{8,})["\']?'), r'\1=***MASKED***'),
    # Bearer Token
    (re.compile(r'(?i)bearer\s+[a-zA-Z0-9_\-/.]{8,}'), 'Bearer ***MASKED***'),
    # 常见 Key 格式 (sk-xxx, pk-xxx)
    (re.compile(r'\b(sk|pk|ak)[_-][a-zA-Z0-9]{16,}\b'), '***MASKED_KEY***'),
]


class OutputSanitizer:
    """
    输出脱敏处理器

    检测并掩盖输出中的敏感数据
    """

    @staticmethod
    def sanitize(output: str, max_size: int = 10000) -> tuple[str, bool]:
        """
        脱敏并截断输出

        Args:
            output: 原始输出
            max_size: 最大字符数

        Returns:
            (processed_output, was_truncated)
        """
        # 1. 脱敏
        sanitized = output
        for pattern, replacement in _SENSITIVE_PATTERNS:
            sanitized = pattern.sub(replacement, sanitized)

        # 2. 截断
        truncated = False
        if len(sanitized) > max_size:
            sanitized = sanitized[:max_size] + "\n...[truncated]"
            truncated = True

        return sanitized, truncated


# ============================================
# 工具调用次数限制
# ============================================

class ExecutionLimiter:
    """
    单次对话工具调用次数限制器

    使用 Redis 计数器，防止工具调用死循环
    """

    PREFIX = "ai:tool_exec_limit:"
    DEFAULT_MAX_CALLS = 20
    TTL = 3600  # 1 小时过期

    @staticmethod
    async def check_and_increment(
        conversation_id: int,
        max_calls: int = DEFAULT_MAX_CALLS,
    ) -> int:
        """
        检查并递增调用次数

        Args:
            conversation_id: 对话 ID
            max_calls: 最大允许调用次数

        Returns:
            当前调用次数

        Raises:
            ToolExecutionLimitExceeded: 超过限制
        """
        if conversation_id <= 0 or max_calls <= 0:
            return 0

        try:
            from app.core.redis import get_redis
            redis = await get_redis()
            key = f"{ExecutionLimiter.PREFIX}{conversation_id}"
            current = await redis.incr(key)
            await redis.expire(key, ExecutionLimiter.TTL)

            if current > max_calls:
                logger.warning(
                    "Tool execution limit exceeded: conversation=%d count=%d max=%d",
                    conversation_id, current, max_calls,
                )
                raise ToolExecutionLimitExceeded(
                    _("tool.error.call_limit_exceeded", max_calls=max_calls)
                )
            return current
        except ToolExecutionLimitExceeded:
            raise
        except Exception as exc:
            logger.error("ExecutionLimiter error: %s", str(exc))
            return 0


# ============================================
# HTTP 工具 SSRF 防护
# ============================================

# 内网 CIDR 黑名单
_BLOCKED_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]

# 允许的协议
_ALLOWED_SCHEMES = {"http", "https"}


class UrlValidator:
    """
    URL 安全校验器

    防止 SSRF 攻击：禁止访问内网地址、限制协议
    """

    @staticmethod
    async def validate(
        url: str,
        allowed_domains: list[str] | None = None,
        blocked_domains: list[str] | None = None,
    ) -> None:
        """
        校验 URL 安全性（异步，不阻塞事件循环）

        Args:
            url: 待检查的 URL
            allowed_domains: 白名单域名列表（设置后仅允许这些域名）
            blocked_domains: 黑名单域名列表

        Raises:
            SSRFBlockedError: URL 不安全
        """
        try:
            parsed = urlparse(url)
        except Exception:
            raise SSRFBlockedError(_("tool.error.invalid_url", url=url))

        # 1. 协议检查
        if parsed.scheme not in _ALLOWED_SCHEMES:
            raise SSRFBlockedError(
                _("tool.error.protocol_not_allowed", scheme=parsed.scheme)
            )

        hostname = parsed.hostname
        if not hostname:
            raise SSRFBlockedError(_("tool.error.url_no_hostname"))

        # 2. 白名单模式
        if allowed_domains:
            if hostname not in allowed_domains:
                raise SSRFBlockedError(
                    _("tool.error.domain_not_allowed", hostname=hostname)
                )
            return

        # 3. 黑名单域名检查
        if blocked_domains and hostname in blocked_domains:
            raise SSRFBlockedError(
                _("tool.error.domain_blocked", hostname=hostname)
            )

        # 4. IP 地址检查（防止 SSRF 访问内网）
        try:
            # 使用 asyncio 非阻塞 DNS 解析，避免阻塞事件循环
            loop = asyncio.get_running_loop()
            addrs = await loop.getaddrinfo(hostname, None)
            for addr_info in addrs:
                ip_str = addr_info[4][0]
                ip = ipaddress.ip_address(ip_str)
                for network in _BLOCKED_NETWORKS:
                    if ip in network:
                        raise SSRFBlockedError(
                            _("tool.error.internal_network_blocked", ip=ip_str)
                        )
        except SSRFBlockedError:
            raise
        except socket.gaierror:
            raise SSRFBlockedError(_("tool.error.dns_resolve_failed", hostname=hostname))
        except Exception as exc:
            logger.error("URL validation error: %s", str(exc))
            raise SSRFBlockedError(_("tool.error.url_validation_failed", detail=str(exc)))

    @staticmethod
    def sanitize_headers_for_log(headers: dict[str, str]) -> dict[str, str]:
        """
        清理请求头中的敏感信息（用于日志记录）

        Args:
            headers: 原始请求头

        Returns:
            脱敏后的请求头
        """
        sensitive_keys = {
            "authorization", "cookie", "x-api-key",
            "x-auth-token", "proxy-authorization",
        }
        sanitized = {}
        for key, value in headers.items():
            if key.lower() in sensitive_keys:
                sanitized[key] = "***MASKED***"
            else:
                sanitized[key] = value
        return sanitized


# ============================================
# 数据库工具 SQL 安全
# ============================================

# 禁止的 SQL 关键字（非 SELECT 开头）
_SQL_BLOCKED_PATTERN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|CREATE|GRANT|REVOKE|EXEC"
    r"|INTO|COPY|SET|DO|EXPLAIN)\b",
    re.IGNORECASE,
)

# 禁止访问的系统 schema
_BLOCKED_SCHEMAS = {"pg_catalog", "information_schema", "pg_toast"}

_SYSTEM_TABLE_PATTERN = re.compile(
    r"\b(pg_catalog|information_schema|pg_toast)\b",
    re.IGNORECASE,
)


class SqlValidator:
    """
    SQL 安全校验器

    仅允许 SELECT/WITH 语句，禁止写操作和系统表访问
    """

    @staticmethod
    def validate(sql: str) -> None:
        """
        校验 SQL 安全性

        Args:
            sql: SQL 语句

        Raises:
            SqlInjectionBlockedError: SQL 不安全
        """
        stripped = sql.strip()
        if not stripped:
            raise SqlInjectionBlockedError(_("tool.error.empty_sql"))

        # 检查是否以 SELECT 或 WITH 开头
        if not re.match(r"^\s*(SELECT|WITH)\b", stripped, re.IGNORECASE):
            raise SqlInjectionBlockedError(
                _("tool.error.sql_only_select")
            )

        # 检查禁止关键字（防止子查询中的写操作）
        if _SQL_BLOCKED_PATTERN.search(stripped):
            raise SqlInjectionBlockedError(
                _("tool.error.sql_write_blocked")
            )

        # 检查系统表访问
        if _SYSTEM_TABLE_PATTERN.search(stripped):
            raise SqlInjectionBlockedError(
                _("tool.error.sql_system_table_blocked")
            )

    @staticmethod
    def inject_limit(sql: str, max_rows: int = 100) -> str:
        """
        自动注入 LIMIT（如果缺失）

        Args:
            sql: 原始 SQL
            max_rows: 最大行数

        Returns:
            带 LIMIT 的 SQL
        """
        stripped = sql.strip().rstrip(";")
        if not re.search(r"\bLIMIT\b", stripped, re.IGNORECASE):
            return f"{stripped} LIMIT {max_rows}"
        return stripped


# ============================================
# 邮件工具频率限制
# ============================================

class EmailRateLimiter:
    """
    邮件发送频率限制器

    基于 Redis 计数器，按租户/小时限制发送量
    """

    PREFIX = "ai:email_rate:"
    DEFAULT_MAX_PER_HOUR = 50
    MAX_RECIPIENTS = 10
    MAX_ATTACHMENT_SIZE = 5 * 1024 * 1024  # 5MB
    TTL = 3600  # 1 小时

    @staticmethod
    async def check_rate(
        tenant_id: int,
        max_per_hour: int = DEFAULT_MAX_PER_HOUR,
    ) -> None:
        """
        检查租户邮件发送频率

        Args:
            tenant_id: 租户 ID
            max_per_hour: 每小时最大发送量

        Raises:
            EmailRateLimitError: 频率超限
        """
        try:
            from app.core.redis import get_redis
            redis = await get_redis()
            key = f"{EmailRateLimiter.PREFIX}{tenant_id}"
            current = await redis.incr(key)
            await redis.expire(key, EmailRateLimiter.TTL)

            if current > max_per_hour:
                raise EmailRateLimitError(
                    _("tool.error.email_rate_exceeded", max_per_hour=max_per_hour)
                )
        except EmailRateLimitError:
            raise
        except Exception as exc:
            logger.error("EmailRateLimiter error: %s", str(exc))

    @staticmethod
    def validate_recipients(recipients: list[str]) -> None:
        """
        校验收件人数量

        Args:
            recipients: 收件人列表

        Raises:
            ToolInputValidationError: 超过上限
        """
        if len(recipients) > EmailRateLimiter.MAX_RECIPIENTS:
            raise ToolInputValidationError(
                _("tool.error.too_many_recipients",
                  max=EmailRateLimiter.MAX_RECIPIENTS,
                  got=len(recipients))
            )

    @staticmethod
    def validate_attachment_size(total_bytes: int) -> None:
        """
        校验附件总大小

        Args:
            total_bytes: 附件总字节数

        Raises:
            ToolInputValidationError: 超过大小限制
        """
        if total_bytes > EmailRateLimiter.MAX_ATTACHMENT_SIZE:
            max_mb = EmailRateLimiter.MAX_ATTACHMENT_SIZE / (1024 * 1024)
            raise ToolInputValidationError(
                _("tool.error.attachment_too_large", max_mb=f"{max_mb:.0f}")
            )


__all__ = [
    # 异常
    "ToolSecurityError",
    "ToolInputValidationError",
    "ToolOutputTruncatedError",
    "ToolExecutionLimitExceeded",
    "SSRFBlockedError",
    "SqlInjectionBlockedError",
    "EmailRateLimitError",
    # 校验器
    "InputValidator",
    "OutputSanitizer",
    "ExecutionLimiter",
    "UrlValidator",
    "SqlValidator",
    "EmailRateLimiter",
]
