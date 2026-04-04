"""
Tool Execution Security Module
工具执行安全模块

Provides security protection for tool execution:
提供工具执行的安全防护：
- Input parameter JSON Schema validation / 输入参数 JSON Schema 校验
- Output sensitive data sanitization / 输出敏感数据脱敏
- Per-conversation tool call count limiting / 单次对话工具调用次数限制
- HTTP tool SSRF protection / HTTP 工具 SSRF 防护
- Database tool SQL whitelist / 数据库工具 SQL 白名单
- Email tool rate limiting / 邮件工具频率限制
"""

import asyncio
import ipaddress
import socket
from typing import Any
from urllib.parse import urlparse

from app.ai.data_intelligence.sql_analysis import (
    append_limit_clause,
    extract_table_references,
    find_keyword_sequences,
    has_top_level_limit,
    starts_with_select_or_cte,
)
from app.core.i18n import _
from app.core.logging import LogManager

logger = LogManager.get_logger("ai.tool.security")


# ============================================
# Exception Definitions / 异常定义
# ============================================


class ToolSecurityError(Exception):
    """Tool security base exception / 工具安全基础异常"""

    pass


class ToolInputValidationError(ToolSecurityError):
    """Input parameter validation failed / 输入参数校验失败"""

    pass


class ToolExecutionLimitExceeded(ToolSecurityError):
    """Tool call count exceeded / 工具调用次数超限"""

    pass


class SSRFBlockedError(ToolSecurityError):
    """SSRF attack blocked / SSRF 攻击被阻止"""

    pass


class SqlInjectionBlockedError(ToolSecurityError):
    """SQL injection blocked / SQL 注入被阻止"""

    pass


class EmailRateLimitError(ToolSecurityError):
    """Email rate limit exceeded / 邮件频率超限"""

    pass


# ============================================
# Input Parameter Validation / 输入参数校验
# ============================================


class InputValidator:
    """
    Input Parameter Validator / 输入参数校验器

    Validates tool input parameters against JSON Schema.
    按 JSON Schema 校验工具输入参数。
    """

    @staticmethod
    def validate(input_schema: dict[str, Any] | None, inputs: dict[str, Any]) -> None:
        """
        Validate input parameters against JSON Schema
        校验输入参数是否符合 JSON Schema

        Args:
            input_schema: JSON Schema definition (from ToolDefinition) / JSON Schema 定义
            inputs: Actual input parameters / 实际输入参数

        Raises:
            ToolInputValidationError: Validation failed / 校验失败
        """
        if not input_schema:
            return

        required = input_schema.get("required", [])
        properties = input_schema.get("properties", {})

        # Check required fields / 检查必填字段
        for field in required:
            if field not in inputs or inputs[field] is None:
                raise ToolInputValidationError(
                    _("tool.error.missing_required_param", field=field)
                )

        # Check types / 检查类型
        for name, value in inputs.items():
            if name not in properties:
                continue

            prop = properties[name]
            expected_type = prop.get("type")
            if (
                expected_type
                and value is not None
                and not InputValidator._check_type(value, expected_type)
            ):
                raise ToolInputValidationError(
                    _(
                        "tool.error.param_type_mismatch",
                        name=name,
                        expected_type=expected_type,
                        actual_type=type(value).__name__,
                    )
                )

    @staticmethod
    def _check_type(value: Any, expected: str) -> bool:
        """Basic type check / 基础类型检查"""
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
# Output Sanitization / 输出脱敏
# ============================================

_SENSITIVE_FIELD_TERMS = (
    "apikey",
    "token",
    "secret",
    "password",
    "passwd",
    "authorization",
)
_SENSITIVE_VALUE_CHARS = frozenset(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-/."
)
_KEY_PREFIXES = ("sk-", "pk-", "ak-", "sk_", "pk_", "ak_")


class OutputSanitizer:
    """
    Output Sanitizer / 输出脱敏处理器

    Detects and masks sensitive data in output.
    检测并掩盖输出中的敏感数据。
    """

    @staticmethod
    def sanitize(output: str, max_size: int = 10000) -> tuple[str, bool]:
        """
        Sanitize and truncate output / 脱敏并截断输出

        Args:
            output: Raw output / 原始输出
            max_size: Maximum character count / 最大字符数

        Returns:
            (processed_output, was_truncated)
        """
        # 1. Sanitize / 脱敏
        sanitized = _mask_inline_secret_assignments(output)
        sanitized = _mask_bearer_tokens(sanitized)
        sanitized = _mask_prefixed_keys(sanitized)

        # 2. Truncate / 截断
        truncated = False
        if len(sanitized) > max_size:
            sanitized = sanitized[:max_size] + "\n...[truncated]"
            truncated = True

        return sanitized, truncated


def _mask_inline_secret_assignments(text: str) -> str:
    lines: list[str] = []
    for line in text.splitlines():
        masked = _mask_secret_assignment_line(line)
        lines.append(masked)
    return "\n".join(lines)


def _mask_secret_assignment_line(line: str) -> str:
    separator_index = _find_first_assignment_separator(line)
    if separator_index < 0:
        return line

    separator = line[separator_index]
    head = line[:separator_index]
    key = head.strip().strip("\"'")
    normalized_key = key.replace("-", "").replace("_", "").replace(" ", "").lower()
    if not key or not any(term in normalized_key for term in _SENSITIVE_FIELD_TERMS):
        return line

    tail = line[separator_index + 1 :]
    leading_ws_len = len(tail) - len(tail.lstrip())
    leading_ws = tail[:leading_ws_len]
    if separator == ":" and head.rstrip().endswith('"'):
        return f'{head}{separator}{leading_ws}"***MASKED***"'
    return f"{head}{separator}{leading_ws}***MASKED***"


def _find_first_assignment_separator(text: str) -> int:
    first_equals = text.find("=")
    first_colon = text.find(":")
    candidates = [index for index in (first_equals, first_colon) if index >= 0]
    return min(candidates) if candidates else -1


def _mask_bearer_tokens(text: str) -> str:
    lower = text.lower()
    parts: list[str] = []
    index = 0
    while index < len(text):
        hit = lower.find("bearer", index)
        if hit < 0:
            parts.append(text[index:])
            break
        parts.append(text[index:hit])
        token_start = hit + len("bearer")
        while token_start < len(text) and text[token_start].isspace():
            token_start += 1
        token_end = token_start
        while token_end < len(text) and text[token_end] in _SENSITIVE_VALUE_CHARS:
            token_end += 1
        if token_end - token_start >= 8:
            parts.append("Bearer ***MASKED***")
            index = token_end
            continue
        parts.append(text[hit : hit + len("bearer")])
        index = hit + len("bearer")
    return "".join(parts)


def _mask_prefixed_keys(text: str) -> str:
    lower = text.lower()
    parts: list[str] = []
    index = 0
    while index < len(text):
        match_start = -1
        match_prefix = ""
        for prefix in _KEY_PREFIXES:
            candidate = lower.find(prefix, index)
            if candidate < 0:
                continue
            if match_start < 0 or candidate < match_start:
                match_start = candidate
                match_prefix = prefix
        if match_start < 0:
            parts.append(text[index:])
            break
        parts.append(text[index:match_start])
        if match_start > 0 and text[match_start - 1] in _SENSITIVE_VALUE_CHARS:
            parts.append(text[match_start])
            index = match_start + 1
            continue
        end = match_start + len(match_prefix)
        while end < len(text) and text[end].isalnum():
            end += 1
        if end - (match_start + len(match_prefix)) >= 16:
            parts.append("***MASKED_KEY***")
            index = end
            continue
        parts.append(text[match_start:end])
        index = end
    return "".join(parts)


# ============================================
# Tool Call Count Limiting / 工具调用次数限制
# ============================================


class ExecutionLimiter:
    """
    Per-conversation Tool Call Count Limiter / 单次对话工具调用次数限制器

    Uses Redis counter to prevent tool call infinite loops.
    使用 Redis 计数器，防止工具调用死循环。
    """

    PREFIX = "ai:tool_exec_limit:"
    DEFAULT_MAX_CALLS = 20
    TTL = 3600  # 1 hour expiry / 1 小时过期

    @staticmethod
    async def check_and_increment(
        conversation_id: int,
        max_calls: int = DEFAULT_MAX_CALLS,
    ) -> int:
        """
        Check and increment call count / 检查并递增调用次数

        Args:
            conversation_id: Conversation ID / 对话 ID
            max_calls: Maximum allowed calls / 最大允许调用次数

        Returns:
            Current call count / 当前调用次数

        Raises:
            ToolExecutionLimitExceeded: Limit exceeded / 超过限制
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
                    "Tool execution limit exceeded: conversation={} count={} max={}",
                    conversation_id,
                    current,
                    max_calls,
                )
                raise ToolExecutionLimitExceeded(
                    _("tool.error.call_limit_exceeded", max_calls=max_calls)
                )
            return current
        except ToolExecutionLimitExceeded:
            raise
        except Exception as exc:
            logger.error("ExecutionLimiter error: {}", str(exc))
            return 0


# ============================================
# HTTP Tool SSRF Protection / HTTP 工具 SSRF 防护
# ============================================

# Internal network CIDR blacklist / 内网 CIDR 黑名单
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

# Allowed protocols / 允许的协议
_ALLOWED_SCHEMES = {"http", "https"}


class UrlValidator:
    """
    URL Security Validator / URL 安全校验器

    Prevents SSRF attacks: blocks internal network access, restricts protocols.
    防止 SSRF 攻击：禁止访问内网地址、限制协议。
    """

    @staticmethod
    async def validate(
        url: str,
        allowed_domains: list[str] | None = None,
        blocked_domains: list[str] | None = None,
    ) -> None:
        """
        Validate URL safety (async, non-blocking event loop)
        校验 URL 安全性（异步，不阻塞事件循环）

        Args:
            url: URL to check / 待检查的 URL
            allowed_domains: Whitelist domain list (only these allowed if set) / 白名单域名列表
            blocked_domains: Blacklist domain list / 黑名单域名列表

        Raises:
            SSRFBlockedError: URL is unsafe / URL 不安全
        """
        try:
            parsed = urlparse(url)
        except Exception as exc:
            raise SSRFBlockedError(_("tool.error.invalid_url", url=url)) from exc

        # 1. Protocol check / 协议检查
        if parsed.scheme not in _ALLOWED_SCHEMES:
            raise SSRFBlockedError(
                _("tool.error.protocol_not_allowed", scheme=parsed.scheme)
            )

        hostname = parsed.hostname
        if not hostname:
            raise SSRFBlockedError(_("tool.error.url_no_hostname"))

        # 2. Whitelist mode / 白名单模式
        if allowed_domains:
            if hostname not in allowed_domains:
                raise SSRFBlockedError(
                    _("tool.error.domain_not_allowed", hostname=hostname)
                )
            return

        # 3. Blacklist domain check / 黑名单域名检查
        if blocked_domains and hostname in blocked_domains:
            raise SSRFBlockedError(_("tool.error.domain_blocked", hostname=hostname))

        # 4. IP address check (prevent SSRF access to internal network) / IP 地址检查
        try:
            # Use asyncio non-blocking DNS resolution / 非阻塞 DNS 解析
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
        except socket.gaierror as exc:
            raise SSRFBlockedError(
                _("tool.error.dns_resolve_failed", hostname=hostname)
            ) from exc
        except Exception as exc:
            logger.error("URL validation error: {}", str(exc))
            raise SSRFBlockedError(
                _("tool.error.url_validation_failed", detail=str(exc))
            ) from exc

    @staticmethod
    def sanitize_headers_for_log(headers: dict[str, str]) -> dict[str, str]:
        """
        Sanitize sensitive info in request headers (for logging)
        清理请求头中的敏感信息（用于日志记录）

        Args:
            headers: Raw request headers / 原始请求头

        Returns:
            Sanitized request headers / 脱敏后的请求头
        """
        sensitive_keys = {
            "authorization",
            "cookie",
            "x-api-key",
            "x-auth-token",
            "proxy-authorization",
        }
        sanitized = {}
        for key, value in headers.items():
            if key.lower() in sensitive_keys:
                sanitized[key] = "***MASKED***"
            else:
                sanitized[key] = value
        return sanitized


# ============================================
# Database Tool SQL Security / 数据库工具 SQL 安全
# ============================================

_BLOCKED_SQL_SEQUENCES: list[tuple[str, ...]] = [
    ("INSERT",),
    ("UPDATE",),
    ("DELETE",),
    ("DROP",),
    ("ALTER",),
    ("TRUNCATE",),
    ("CREATE",),
    ("GRANT",),
    ("REVOKE",),
    ("EXEC",),
    ("INTO",),
    ("COPY",),
    ("SET",),
    ("DO",),
    ("EXPLAIN",),
]
_BLOCKED_SCHEMAS = {"pg_catalog", "information_schema", "pg_toast"}


class SqlValidator:
    """
    SQL Security Validator / SQL 安全校验器

    Only allows SELECT/WITH statements, blocks write operations and system table access.
    仅允许 SELECT/WITH 语句，禁止写操作和系统表访问。
    """

    @staticmethod
    def validate(sql: str) -> None:
        """
        Validate SQL safety / 校验 SQL 安全性

        Args:
            sql: SQL statement / SQL 语句

        Raises:
            SqlInjectionBlockedError: SQL is unsafe / SQL 不安全
        """
        stripped = sql.strip()
        if not stripped:
            raise SqlInjectionBlockedError(_("tool.error.empty_sql"))

        # Check if starts with SELECT or WITH / 检查是否以 SELECT 或 WITH 开头
        if not starts_with_select_or_cte(stripped):
            raise SqlInjectionBlockedError(_("tool.error.sql_only_select"))

        # Check blocked keywords (prevent write operations in subqueries) / 检查禁止关键字
        if find_keyword_sequences(stripped, _BLOCKED_SQL_SEQUENCES):
            raise SqlInjectionBlockedError(_("tool.error.sql_write_blocked"))

        # Check system table access / 检查系统表访问
        references = extract_table_references(stripped)
        if any(
            (ref.schema_name or "").lower() in _BLOCKED_SCHEMAS
            or ref.table_name.lower() in _BLOCKED_SCHEMAS
            for ref in references
        ) or any(f"{schema}." in stripped.lower() for schema in _BLOCKED_SCHEMAS):
            raise SqlInjectionBlockedError(_("tool.error.sql_system_table_blocked"))

    @staticmethod
    def inject_limit(sql: str, max_rows: int = 100) -> str:
        """
        Auto-inject LIMIT if missing / 自动注入 LIMIT

        Args:
            sql: Original SQL / 原始 SQL
            max_rows: Maximum rows / 最大行数

        Returns:
            SQL with LIMIT / 带 LIMIT 的 SQL
        """
        stripped = sql.strip()
        if has_top_level_limit(stripped):
            return stripped.rstrip(";")
        return append_limit_clause(stripped, max_rows)


# ============================================
# Email Tool Rate Limiting / 邮件工具频率限制
# ============================================


class EmailRateLimiter:
    """
    Email Send Rate Limiter / 邮件发送频率限制器

    Uses Redis counter to limit send volume per tenant per hour.
    基于 Redis 计数器，按企业/小时限制发送量。
    """

    PREFIX = "ai:email_rate:"
    DEFAULT_MAX_PER_HOUR = 50
    MAX_RECIPIENTS = 10
    MAX_ATTACHMENT_SIZE = 5 * 1024 * 1024  # 5MB  # 补充说明 / note
    TTL = 3600  # 1 hour / 1 小时

    @staticmethod
    async def check_rate(
        tenant_id: int,
        max_per_hour: int = DEFAULT_MAX_PER_HOUR,
    ) -> None:
        """
        Check tenant email send rate / 检查企业邮件发送频率

        Args:
            tenant_id: Tenant ID / 企业 ID
            max_per_hour: Max sends per hour / 每小时最大发送量

        Raises:
            EmailRateLimitError: Rate exceeded / 频率超限
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
            logger.error("EmailRateLimiter error: {}", str(exc))

    @staticmethod
    def validate_recipients(recipients: list[str]) -> None:
        """
        Validate recipient count / 校验收件人数量

        Args:
            recipients: Recipient list / 收件人列表

        Raises:
            ToolInputValidationError: Exceeded limit / 超过上限
        """
        if len(recipients) > EmailRateLimiter.MAX_RECIPIENTS:
            raise ToolInputValidationError(
                _(
                    "tool.error.too_many_recipients",
                    max=EmailRateLimiter.MAX_RECIPIENTS,
                    got=len(recipients),
                )
            )

    @staticmethod
    def validate_attachment_size(total_bytes: int) -> None:
        """
        Validate total attachment size / 校验附件总大小

        Args:
            total_bytes: Total attachment bytes / 附件总字节数

        Raises:
            ToolInputValidationError: Size limit exceeded / 超过大小限制
        """
        if total_bytes > EmailRateLimiter.MAX_ATTACHMENT_SIZE:
            max_mb = EmailRateLimiter.MAX_ATTACHMENT_SIZE / (1024 * 1024)
            raise ToolInputValidationError(
                _("tool.error.attachment_too_large", max_mb=f"{max_mb:.0f}")
            )


__all__ = [
    # Exceptions / 异常
    "ToolSecurityError",
    "ToolInputValidationError",
    "ToolExecutionLimitExceeded",
    "SSRFBlockedError",
    "SqlInjectionBlockedError",
    "EmailRateLimitError",
    # Validators / 校验器
    "InputValidator",
    "OutputSanitizer",
    "ExecutionLimiter",
    "UrlValidator",
    "SqlValidator",
    "EmailRateLimiter",
]
