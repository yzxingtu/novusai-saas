"""
Plugin sandbox context / 插件沙箱上下文

PluginContext is the sole entry point for plugins to interact with the core system.
All methods check capability authorization before execution.
/
PluginContext 是插件与核心系统交互的唯一入口。
所有方法在执行前检查能力授权（capabilities）。
"""

from __future__ import annotations

import inspect
import json
import logging
import re as _re
import time
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from app.core.logging import get_logger
from app.enums.agent import (
    MemoryChannelEnum,
    MemorySceneEnum,
)
from app.enums.plugin import PluginLicenseTypeEnum
from app.plugins.exceptions import PluginSecurityError

# Precompiled: match SQL keywords followed by table names (including \t \n whitespace separators)
# / 预编译：匹配 SQL 关键字后跟表名（含 \t \n 等空白分隔符）
_TABLE_KEYWORD_RE = _re.compile(
    r'\b(?:from|join|into|update|table)\s+["\']?([a-z0-9_][a-z0-9_.]*)',
    _re.IGNORECASE,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.plugins.manifest import PluginManifest

logger = get_logger(__name__)


@dataclass(frozen=True)
class RequestContext:
    """
    Request context — identity info extracted from HTTP request / WebSocket connection.
    / 请求上下文 — 从 HTTP 请求 / WebSocket 连接中提取的身份信息。

    Created in API dispatcher layer, injected into PluginContext.
    Lifecycle hook scenarios (on_enable/on_disable, etc.) have no request context,
    in which case it is None and PluginContext methods return safe defaults.
    / 在 API dispatcher 层创建，注入到 PluginContext。
    lifecycle hook 场景（on_enable/on_disable 等）无请求上下文，
    此时为 None，PluginContext 方法返回安全默认值。
    """

    tenant_id: int | None = None
    user_id: int | None = None
    user_role: str = ""  # "admin" / "tenant_admin" / "tenant_user"
    permissions: list[str] = field(default_factory=list)
    request_id: str = ""


class PluginDbProxy:
    """
    Database proxy — restricts plugins to only operate on px_{name}_* tables
    / 数据库代理 — 限制插件只能操作 px_{name}_* 表

    Wraps AsyncSession, intercepts execute() to check table name prefixes.
    / 包装 AsyncSession，拦截 execute() 检查表名前缀。
    """

    def __init__(
        self,
        db: AsyncSession,
        plugin_name: str,
        allowed_table_prefixes: list[str] | None = None,
    ) -> None:
        self._db = db
        own_prefix = f"px_{plugin_name.replace('-', '_')}_"
        prefixes = allowed_table_prefixes or [own_prefix]
        if own_prefix not in prefixes:
            prefixes = [own_prefix, *prefixes]
        self._allowed_prefixes = tuple(dict.fromkeys(prefixes))

    @property
    def session(self) -> AsyncSession:
        """Forbidden: do not expose raw session to avoid bypassing sandbox checks. / 禁止暴露原始 session，避免绕过沙箱检查。"""
        raise PluginSecurityError(
            message="Access to raw session is forbidden in plugin sandbox",
        )

    async def execute(self, statement: Any, *args: Any, **kwargs: Any) -> Any:
        """Execute SQL with table name prefix check / 执行 SQL，检查表名前缀"""
        sql_text = str(statement)
        self._check_table_access(sql_text)
        return await self._db.execute(statement, *args, **kwargs)

    async def flush(self) -> None:
        await self._db.flush()

    async def commit(self) -> None:
        """
        Flush plugin data within the current transaction (does not commit outer transaction).
        / 在当前事务内 flush 插件数据（不提交外层事务）。

        Note: To protect lifecycle transaction atomicity, this method is equivalent to flush().
        For cross-session visibility, use flush() in the plugin's final response path;
        the lifecycle framework will commit uniformly at request end.
        / 注意：为保护生命周期事务原子性，此方法等同于 flush()。
        若需要确保跨会话可见性，请在插件代码的最终响应路径使用 flush()；
        生命周期框架会在请求结束时统一 commit。
        """
        await self._db.flush()

    async def rollback(self) -> None:
        """
        Plugins cannot rollback the entire database session.
        / 禁止插件回滚整个数据库会话。

        Calling rollback() would undo all lifecycle changes (e.g. plugin.status=ENABLED),
        causing the system to enter an inconsistent state. To undo plugin's own writes,
        avoid writing to DB in on_enable hooks or use business logic checks.
        / 调用 rollback() 会撤销所有生命周期变更（如 plugin.status=ENABLED），
        导致系统进入不一致状态。如需撤销插件自身写入，
        请避免在 on_enable 等 Hook 中写入 DB 或使用业务逻辑判断。
        """
        raise PluginSecurityError(
            message="Plugins cannot rollback the database session — "
            "this would undo lifecycle changes. Use flush() to persist your data.",
        )

    def add(self, instance: Any) -> None:
        self._check_instance_access(instance)
        self._db.add(instance)

    def add_all(self, instances: list[Any]) -> None:
        for instance in instances:
            self._check_instance_access(instance)
        self._db.add_all(instances)

    async def delete(self, instance: Any) -> None:
        self._check_instance_access(instance)
        await self._db.delete(instance)

    async def refresh(self, instance: Any, *args: Any, **kwargs: Any) -> None:
        self._check_instance_access(instance)
        await self._db.refresh(instance, *args, **kwargs)

    async def get(self, entity: Any, ident: Any, **kwargs: Any) -> Any:
        table_name = getattr(entity, "__tablename__", "")
        if table_name and not self._is_allowed_table(table_name):
            raise PluginSecurityError(
                message=f"Plugin can only operate on allowed table prefixes {self._allowed_prefixes}, "
                f"got '{table_name}'",
            )
        return await self._db.get(entity, ident, **kwargs)

    @staticmethod
    def text(sql: str) -> Any:
        from sqlalchemy import text

        return text(sql)

    def _check_instance_access(self, instance: Any) -> None:
        table_name = getattr(instance.__class__, "__tablename__", "")
        if table_name and not self._is_allowed_table(table_name):
            raise PluginSecurityError(
                message=f"Plugin can only operate on allowed table prefixes {self._allowed_prefixes}, "
                f"got '{table_name}'",
            )

    def _is_allowed_table(self, table_name: str) -> bool:
        return any(table_name.startswith(prefix) for prefix in self._allowed_prefixes)

    def _check_table_access(self, sql_text: str) -> None:
        """Check if SQL only involves plugin-owned tables (basic check + CTE detection)
        / 检查 SQL 是否只涉及插件自有表（基础检查 + CTE 检测）

        Known limitations (defense-in-depth, not a perfect sandbox) / 已知限制：
        - String constants with "FROM xxx" may trigger false checks / 字符串常量中的 "FROM xxx" 可能误触发检查
        - Does not check function calls in raw SQL (e.g. pg_catalog.*) / 不检查 raw SQL 中的函数调用
        - SQLAlchemy ORM queries have extra _check_instance_access protection via add/execute
          / SQLAlchemy ORM 查询经过 add/execute 时有额外 _check_instance_access 保护
        - CTE inner table names detected via FROM|JOIN|INTO|UPDATE|TABLE keywords (M52-T6)
          / CTE 内部的表名已通过关键字检测
        - Strongly recommend PostgreSQL RLS as the final defense in production
          / 生产环境强烈建议通过 PostgreSQL RLS 做最终防线

        Note: real_table in WITH cte AS (SELECT ... FROM real_table ...) is captured
        by the internal FROM keyword scan, so CTE itself needs no extra handling.
        / 注意：CTE 中的 real_table 会被内部 FROM 关键字扫描捕获，故不需额外处理。
        """
        sql_lower = sql_text.lower()
        # Skip empty statements and parameterized query placeholders / 跳过空语句和参数化查询占位
        if not sql_lower.strip():
            return

        # Allow list: alembic metadata tables + system schemas / 允许名单：alembic 元数据表 + 系统 schema
        _ALLOW_LIST = {"alembic_version", "information_schema", "pg_catalog", "dual"}

        # Check table names after common table operation keywords (including CTE internal FROM/JOIN refs)
        # _TABLE_KEYWORD_RE defined at module level, handles \t/\n whitespace separators
        # / 检查常见的表操作关键字后的表名（含 CTE 内部通过 FROM/JOIN 引用的表）
        # _TABLE_KEYWORD_RE 定义在模块级，处理 \t/\n 等任意空白分隔符
        for match in _TABLE_KEYWORD_RE.finditer(sql_lower):
            table_name = match.group(1).strip('"\'')
            # Allowed tables: plugin-owned tables (limited by allowed_prefixes) + allow list
            # / 允许的表：插件自有表（由 allowed_prefixes 限定）+ 允许名单
            if table_name and not self._is_allowed_table(table_name) and table_name not in _ALLOW_LIST:
                raise PluginSecurityError(
                    message=f"Plugin can only access tables with prefixes "
                    f"{self._allowed_prefixes}, attempted: '{table_name}'",
                )


class PluginContext:
    """
    Plugin sandbox context / 插件沙箱上下文

    The ctx parameter type for plugin lifecycle hooks. Provides controlled system access APIs.
    / 插件生命周期钩子的 ctx 参数类型。提供受控的系统访问 API。
    """

    def __init__(
        self,
        plugin_name: str,
        manifest: PluginManifest,
        db: AsyncSession,
        granted_capabilities: list[str] | None = None,
        request_context: RequestContext | None = None,
    ) -> None:
        self.plugin_name = plugin_name
        self.manifest = manifest
        self._db = db
        self._granted_capabilities = set(granted_capabilities or [])
        self._request_context = request_context
        self._logger: logging.Logger | None = None

    # ── Capability checks / 能力检查 ──

    def _require(self, cap: str) -> None:
        """Check if plugin has the specified capability, raise PluginSecurityError if not / 检查插件是否拥有指定能力，无则抛出 PluginSecurityError"""
        if cap not in self._granted_capabilities:
            raise PluginSecurityError(
                message=f"Plugin '{self.plugin_name}' requires capability '{cap}' "
                f"which has not been granted",
            )

    def has_capability(self, cap: str) -> bool:
        """Check if plugin has the specified capability / 检查插件是否拥有指定能力"""
        return cap in self._granted_capabilities

    # ── Config / 配置 ──

    async def get_config(self) -> dict:
        """
        Get plugin global config (auto-decrypt sensitive fields)
        / 获取插件全局配置（自动解密敏感字段）

        Reads from Plugin.config, auto-decrypts fields marked with x-encrypted in manifest.config_schema.
        / 从 Plugin.config 读取，根据 manifest.config_schema 中的 x-encrypted 标记自动解密。
        """
        from sqlalchemy import select

        from app.models.system.plugin import Plugin

        result = await self._db.execute(
            select(Plugin.config, Plugin.manifest).where(
                Plugin.name == self.plugin_name,
                Plugin.is_deleted.is_(False),
            )
        )
        row = result.one_or_none()
        if not row:
            return {}

        config = row[0] or {}
        manifest_data = row[1] or {}
        config_schema = manifest_data.get("config_schema")
        if config_schema:
            from app.plugins.crypto import decrypt_plugin_config

            config = decrypt_plugin_config(config, config_schema)
        return config

    async def get_tenant_config(self, tenant_id: int) -> dict:
        """Get tenant-level config / 获取租户级配置"""
        from sqlalchemy import select

        from app.models.system.plugin import Plugin
        from app.models.system.resource_tenant_assignment import (
            ResourceTenantAssignment,
        )

        result = await self._db.execute(
            select(ResourceTenantAssignment.config).join(
                Plugin, Plugin.id == ResourceTenantAssignment.resource_id
            ).where(
                ResourceTenantAssignment.resource_type == "plugin",
                Plugin.name == self.plugin_name,
                ResourceTenantAssignment.tenant_id == tenant_id,
                Plugin.is_deleted.is_(False),
            )
        )
        row = result.scalar_one_or_none()
        return row or {}

    async def update_config(self, config: dict) -> None:
        """Update plugin global config (auto-encrypt sensitive fields), requires config:write capability / 更新插件全局配置（自动加密敏感字段），需 config:write 能力"""
        self._require("config:write")

        from sqlalchemy import select, update

        from app.models.system.plugin import Plugin

        result = await self._db.execute(
            select(Plugin.manifest).where(
                Plugin.name == self.plugin_name,
                Plugin.is_deleted.is_(False),
            )
        )
        manifest_data = result.scalar_one_or_none() or {}
        config_schema = manifest_data.get("config_schema")

        if config_schema:
            from app.plugins.crypto import encrypt_plugin_config

            config = encrypt_plugin_config(config, config_schema)

        await self._db.execute(
            update(Plugin).where(
                Plugin.name == self.plugin_name,
                Plugin.is_deleted.is_(False),
            ).values(config=config)
        )
        await self._db.flush()

    # ── Database / 数据库 ──

    def get_db(self) -> PluginDbProxy:
        """Return database proxy (only allows current plugin's own tables), requires db:own_tables capability / 返回数据库代理（仅允许当前插件自有表），需 db:own_tables 能力"""
        self._require("db:own_tables")

        own_prefix = f"px_{self.plugin_name.replace('-', '_')}_"
        extra_prefixes = getattr(self.manifest, "db_table_prefixes", None) or []
        allowed_prefixes = [own_prefix, *extra_prefixes]
        return PluginDbProxy(
            self._db,
            self.plugin_name,
            allowed_table_prefixes=allowed_prefixes,
        )

    async def get_own_license_status(self) -> dict[str, Any]:
        """
        Get current plugin's license status (controlled read-only).
        / 获取当前插件的许可证状态（受控只读）。

        Only allows reading the current plugin's own license, does not expose arbitrary system table access.
        / 仅允许读取当前插件自身的 license，不暴露任意系统表访问能力。
        """
        from sqlalchemy import select

        from app.core.base_model import utc_now
        from app.models.system.plugin import Plugin
        from app.models.system.plugin_license import PluginLicense

        plugin_id_result = await self._db.execute(
            select(Plugin.id).where(
                Plugin.name == self.plugin_name,
                Plugin.is_deleted.is_(False),
            )
        )
        plugin_id = plugin_id_result.scalar_one_or_none()
        if not plugin_id:
            return {
                "status": "invalid",
                "license_type": None,
                "is_valid": False,
                "message": f"Plugin '{self.plugin_name}' not found",
            }

        result = await self._db.execute(
            select(PluginLicense).where(
                PluginLicense.plugin_id == plugin_id,
                PluginLicense.is_deleted.is_(False),
            ).order_by(PluginLicense.created_at.desc()).limit(1)
        )
        license_record = result.scalars().first()

        if not license_record:
            return {
                "status": "invalid",
                "license_type": None,
                "is_valid": False,
                "message": "No license found",
            }

        now = utc_now()
        _TRIAL = PluginLicenseTypeEnum.TRIAL.value
        license_type = getattr(license_record, "license_type", None)
        trial_expires_at = getattr(license_record, "trial_expires_at", None)
        expires_at = getattr(license_record, "expires_at", None)
        activated_at = getattr(license_record, "activated_at", None)
        is_valid = bool(getattr(license_record, "is_valid", False))

        if license_type == _TRIAL:
            if trial_expires_at and now < trial_expires_at:
                remaining = (trial_expires_at - now).days
                return {
                    "status": "trial",
                    "license_type": _TRIAL,
                    "is_valid": True,
                    "trial_days_remaining": remaining,
                    "expires_at": trial_expires_at.isoformat() if trial_expires_at else None,
                }
            return {
                "status": "expired",
                "license_type": _TRIAL,
                "is_valid": False,
                "message": "Trial period expired",
            }

        if is_valid:
            # Check if paid license has expired / 检查付费 License 是否过期
            if expires_at and now >= expires_at:
                return {
                    "status": "expired",
                    "license_type": license_type,
                    "is_valid": False,
                    "message": "License expired",
                    "expires_at": expires_at.isoformat() if expires_at else None,
                }
            remaining_days = None
            if expires_at:
                remaining_days = (expires_at - now).days
            return {
                "status": "active",
                "license_type": license_type,
                "is_valid": True,
                "license_key": "****",
                "activated_at": activated_at.isoformat() if activated_at else None,
                "expires_at": expires_at.isoformat() if expires_at else None,
                "remaining_days": remaining_days,
            }

        return {
            "status": "expired",
            "license_type": license_type,
            "is_valid": False,
            "message": "License expired or revoked",
        }

    # ── Logging / 日志 ──

    def get_logger(self) -> logging.Logger:
        """Return plugin-specific Logger / 返回插件专属 Logger"""
        if self._logger is None:
            self._logger = get_logger(f"plugin.{self.plugin_name}")
        return self._logger

    # ── Storage / 存储 ──

    async def get_storage(self) -> Any:
        """
        Return storage driver scoped to plugins/{name}/ namespace.
        / 返回路径限定在 plugins/{name}/ 命名空间的存储驱动。

        Requires storage:read or storage:write capability.
        / 需要 storage:read 或 storage:write 能力。
        """
        if not (self.has_capability("storage:read") or self.has_capability("storage:write")):
            raise PluginSecurityError(
                message=f"Plugin '{self.plugin_name}' requires 'storage:read' or "
                f"'storage:write' capability for storage access",
            )
        from app.services.common.config_service import ConfigService
        from app.storage.base import StorageConfig
        from app.storage.manager import storage_manager

        config_service = ConfigService(self._db)
        driver_name = await config_service.get_value("storage_driver") or "local"
        storage_conf = StorageConfig(driver=driver_name)
        driver = storage_manager.get_driver(storage_conf)
        return _NamespacedStorageProxy(driver, f"plugins/{self.plugin_name}")

    # ── HTTP / HTTP 请求 ──

    async def http_request(
        self,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> dict:
        """
        Send HTTP request, requires http:outbound capability.
        / 发送 HTTP 请求，需 http:outbound 能力。

        Auto-adds 30-second timeout protection.
        SSRF protection: blocks access to private network segments and cloud-metadata endpoints.
        / 自动添加 30 秒超时保护。
        SSRF 防护：禁止访问私有网络段和 cloud-metadata 端点。
        """
        self._require("http:outbound")
        self._check_ssrf(url)
        import httpx

        kwargs.setdefault("timeout", 30.0)
        # Force-disable follow_redirects to prevent malicious redirects bypassing SSRF checks
        # / 强制禁止 follow_redirects，防止恶意重定向绕过 SSRF 检查
        # (e.g., external URL → redirect → 169.254.169.254)
        kwargs["follow_redirects"] = False
        async with httpx.AsyncClient() as client:
            response = await client.request(method, url, **kwargs)
            return {
                "status_code": response.status_code,
                "headers": dict(response.headers),
                "body": response.text,
            }

    @staticmethod
    def _check_ssrf(url: str) -> None:
        """
        SSRF protection: parse target URL, deny access to private/reserved IP segments.
        / SSRF 防护：解析目标 URL，拒绝访问私有/保留 IP 段。

        Blocks / 阻断：
        - 127.x.x.x / ::1 — localhost
        - 10.x.x.x — private class A / 私有 A 类
        - 172.16–31.x.x — private class B / 私有 B 类
        - 192.168.x.x — private class C / 私有 C 类
        - 169.254.x.x — link-local / cloud metadata (AWS IMDS, etc.)
        - 0.x.x.x — reserved / 保留
        - file:// / gopher:// / ftp:// — non-HTTP protocols / 非 HTTP 协议
        """
        import ipaddress
        import urllib.parse

        parsed = urllib.parse.urlparse(url)
        scheme = (parsed.scheme or "").lower()
        if scheme not in ("http", "https"):
            raise PluginSecurityError(
                message=f"Plugin http_request only supports http/https (got '{scheme}')",
            )

        host = parsed.hostname or ""
        if not host:
            raise PluginSecurityError(message="Invalid URL: missing host")

        try:
            addr = ipaddress.ip_address(host)
            # IPv4-mapped IPv6 (e.g., ::ffff:127.0.0.1) — Python's is_loopback/is_private
            # returns False for these, so we unwrap to the embedded IPv4 address first.
            if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped is not None:
                addr = addr.ipv4_mapped
            if (
                addr.is_private
                or addr.is_loopback
                or addr.is_link_local
                or addr.is_reserved
                or addr.is_unspecified
                or addr.is_multicast
            ):
                raise PluginSecurityError(
                    message=f"SSRF blocked: plugin http_request cannot access private/reserved IP '{host}'",
                )
        except ValueError:
            # host is a domain name (not an IP literal) — allow it
            # Note: DNS rebinding attacks are still possible; for stronger protection
            # use an egress proxy with IP-level filtering at the network layer.
            blocked_domains = ("localhost", "metadata.google.internal")
            if host.lower() in blocked_domains or host.lower().endswith(".local"):
                raise PluginSecurityError(
                    message=f"SSRF blocked: plugin http_request cannot access '{host}'",
                )

    # ── AI / AI 功能 ──

    async def _resolve_ai_assignment(
        self, feature_code: str,
    ) -> tuple[int, int]:
        """
        Resolve AI feature binding: find agent_id and effective_tenant_id.
        / 解析 AI 功能绑定：查找 agent_id 和 effective_tenant_id。

        Args:
            feature_code: Feature code (without plugin.{name}. prefix) / 功能代码（不含 plugin.{name}. 前缀）

        Returns:
            (agent_id, effective_tenant_id)

        Raises:
            PluginError: Agent not bound / 未绑定 Agent
        """
        from sqlalchemy import select

        from app.models.system.agent_assignment import SystemAgentAssignment

        full_code = f"plugin.{self.plugin_name}.{feature_code}"

        tenant_id = self.get_current_tenant_id()
        query = select(
            SystemAgentAssignment.agent_id,
            SystemAgentAssignment.tenant_id,
        ).where(
            SystemAgentAssignment.feature_code == full_code,
            SystemAgentAssignment.is_active.is_(True),
            SystemAgentAssignment.is_deleted.is_(False),
        ).order_by(
            SystemAgentAssignment.tenant_id.is_(None).asc(),
        )
        result = await self._db.execute(query)
        rows = result.all()

        agent_id = None
        resolved_tenant_id = tenant_id
        for row in rows:
            if tenant_id and row[1] == tenant_id:
                agent_id = row[0]
                break
            if row[1] is None:
                agent_id = row[0]

        if not agent_id:
            from app.plugins.exceptions import PluginError

            raise PluginError(
                message=f"AI feature '{feature_code}' is not bound to any Agent. "
                f"Please configure it in plugin management.",
            )

        # Verify the bound Agent still exists and is published / 校验绑定的 Agent 仍然存在且已发布
        from app.enums.agent import AgentStatusEnum
        from app.models.ai.agent import Agent

        agent_check = await self._db.execute(
            select(Agent.id).where(
                Agent.id == agent_id,
                Agent.is_deleted.is_(False),
                Agent.status == AgentStatusEnum.PUBLISHED.value,
            )
        )
        if not agent_check.scalar_one_or_none():
            from app.plugins.exceptions import PluginError

            raise PluginError(
                message=f"AI feature '{feature_code}' is bound to Agent #{agent_id} "
                f"which is no longer available (deleted or unpublished).",
            )

        # effective_tenant_id used for AgentChatService to create conversation records
        # Always use requester's tenant_id (even if agent is global with tenant_id=NULL)
        # / effective_tenant_id 用于 AgentChatService 创建对话记录
        # 始终使用请求者的 tenant_id（即使 agent 是全局的 tenant_id=NULL）
        effective_tenant_id = resolved_tenant_id or 0

        return agent_id, effective_tenant_id

    @staticmethod
    def _extract_user_message(messages: list[dict]) -> str:
        """Extract the last user message content from the message list / 从消息列表中提取最后一条 user 消息内容"""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                return msg.get("content", "")
        if messages:
            return messages[-1].get("content", "")
        return ""

    @staticmethod
    def _filter_callable_kwargs(callable_obj: Any, kwargs: dict[str, Any]) -> dict[str, Any]:
        """
        Filter kwargs based on callable signature, compatible with new params unsupported by old implementations.
        / 根据可调用对象签名过滤 kwargs，兼容旧实现不支持的新参数。
        """
        try:
            sig = inspect.signature(callable_obj)
        except (TypeError, ValueError):
            return kwargs

        params = sig.parameters.values()
        if any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params):
            return kwargs

        accepted = set(sig.parameters.keys())
        return {k: v for k, v in kwargs.items() if k in accepted}

    async def call_ai_feature(
        self, feature_code: str, messages: list[dict]
    ) -> str:
        """
        Call AI feature (non-streaming), requires ai:call capability.
        / 调用 AI 功能（非流式），需 ai:call 能力。

        Finds the bound Agent via SystemAgentAssignment, then calls AgentChatService for conversation.
        / 通过 SystemAgentAssignment 查找绑定的 Agent，然后调用 AgentChatService 进行对话。

        Args:
            feature_code: Feature code (without plugin.{name}. prefix) / 功能代码（不含 plugin.{name}. 前缀）
            messages: Conversation message list / 对话消息列表（[{"role": "user", "content": "..."}]）

        Returns:
            AI response text / AI 响应文本
        """
        self._require("ai:call")

        agent_id, effective_tenant_id = await self._resolve_ai_assignment(
            feature_code,
        )

        from app.services.ai.agent_chat_service import AgentChatService

        chat_service = AgentChatService(self._db, effective_tenant_id)
        user_message = self._extract_user_message(messages)

        chat_kwargs = {
            "agent_id": agent_id,
            "message": user_message,
            "memory_scene": MemorySceneEnum.PLUGIN.value,
            "memory_channel": MemoryChannelEnum.PLUGIN.value,
            "memory_source": f"plugin.{self.plugin_name}",
        }
        chat_kwargs = self._filter_callable_kwargs(chat_service.chat, chat_kwargs)
        response = await chat_service.chat(**chat_kwargs)
        return response.message

    async def call_ai_feature_stream(
        self,
        feature_code: str,
        messages: list[dict],
    ) -> AsyncGenerator[str, None]:
        """
        Call AI feature (streaming), requires ai:call capability.
        / 调用 AI 功能（流式），需 ai:call 能力。

        Finds the bound Agent via SystemAgentAssignment,
        calls AgentChatService.stream_chat to get SSE stream,
        parses and only yields text deltas.
        / 通过 SystemAgentAssignment 查找绑定的 Agent，
        调用 AgentChatService.stream_chat 获取 SSE 流，
        解析并仅 yield 文本增量（delta）。

        SSE event format / SSE 事件格式：
        - message event: yield delta text / message 事件: yield delta 文本
        - done event: stream ends normally / done 事件: 流正常结束
        - error event: raise PluginError / error 事件: 抛出 PluginError
        - other events (tool_call, thinking, etc.): skip / 其他事件: 跳过

        Falls back to non-streaming call_ai_feature if upstream doesn't support streaming.
        / 如果上游模型不支持流式或 stream_chat 异常，自动降级为非流式。

        Args:
            feature_code: Feature code (without plugin.{name}. prefix) / 功能代码
            messages: Conversation message list / 对话消息列表

        Yields:
            Text delta strings (content only, without SSE wrapping) / 文本增量字符串
        """
        self._require("ai:call")

        start_time = time.perf_counter()
        chunk_count = 0
        is_fallback = False

        agent_id, effective_tenant_id = await self._resolve_ai_assignment(
            feature_code,
        )
        user_message = self._extract_user_message(messages)

        try:
            from app.services.ai.agent_chat_service import AgentChatService

            chat_service = AgentChatService(self._db, effective_tenant_id)
            stream_kwargs = {
                "agent_id": agent_id,
                "message": user_message,
                "memory_scene": MemorySceneEnum.PLUGIN.value,
                "memory_channel": MemoryChannelEnum.PLUGIN.value,
                "memory_source": f"plugin.{self.plugin_name}",
            }
            stream_kwargs = self._filter_callable_kwargs(chat_service.stream_chat, stream_kwargs)
            sse_response = await chat_service.stream_chat(**stream_kwargs)

            async for raw_chunk in sse_response.body_iterator:
                text = raw_chunk if isinstance(raw_chunk, str) else raw_chunk.decode("utf-8")
                for line in text.split("\n"):
                    line = line.strip()
                    if not line.startswith("data: "):
                        continue
                    payload = line[6:]
                    if payload == "[DONE]":
                        return
                    try:
                        event = json.loads(payload)
                    except (json.JSONDecodeError, ValueError):
                        continue

                    if event.get("error"):
                        from app.plugins.exceptions import PluginError
                        raise PluginError(
                            message=event.get("message", "AI execution error"),
                        )

                    if event.get("event") == "message":
                        delta = event.get("delta", "")
                        if delta:
                            chunk_count += 1
                            yield delta

        except Exception as exc:
            from app.plugins.exceptions import PluginError

            if isinstance(exc, PluginError):
                raise

            logger.warning(
                "Plugin %s AI stream failed: %s",
                self.plugin_name, exc,
            )
            is_fallback = True
            try:
                full_text = await self.call_ai_feature(feature_code, messages)
                if full_text:
                    chunk_count = 1
                    yield full_text
            except Exception as fallback_exc:
                logger.error("Plugin %s AI fallback also failed: %s", self.plugin_name, fallback_exc)
                raise PluginError(message=f"AI call failed: {exc}") from exc

        finally:
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            logger.info(
                "plugin_ai_stream: plugin=%s feature=%s agent_id=%d "
                "tenant_id=%d chunks=%d latency_ms=%d fallback=%s",
                self.plugin_name,
                feature_code,
                agent_id,
                effective_tenant_id,
                chunk_count,
                latency_ms,
                is_fallback,
            )

    async def is_ai_feature_configured(self, feature_code: str) -> bool:
        """Check if AI feature is configured (auto-adds plugin.{name}. prefix) / 检查 AI 功能是否已配置（自动添加 plugin.{name}. 前缀）"""
        from sqlalchemy import select

        from app.models.system.agent_assignment import SystemAgentAssignment

        full_code = f"plugin.{self.plugin_name}.{feature_code}"
        result = await self._db.execute(
            select(SystemAgentAssignment.id).where(
                SystemAgentAssignment.feature_code == full_code,
                SystemAgentAssignment.is_active.is_(True),
                SystemAgentAssignment.is_deleted.is_(False),
            )
        )
        return result.scalar_one_or_none() is not None

    # ── Notifications / 通知 ──

    async def send_notification(
        self,
        tenant_id: int,
        user_ids: list[int],
        template_code: str,
        variables: dict | None = None,
    ) -> None:
        """Send notification, requires notifications:send capability / 发送通知，需 notifications:send 能力"""
        _ = tenant_id
        self._require("notifications:send")
        from app.services.common.notification_service import notify

        recipients = [("tenant_admin", uid) for uid in user_ids]
        await notify(self._db, template_code, recipients, variables or {})

    # ── Events / 事件 ──

    async def emit_event(self, event_name: str, data: dict | None = None) -> dict:
        """
        Publish cross-plugin event + trigger same-name hook points.
        / 发布跨插件事件 + 触发同名钩子点。

        Triggers two channels simultaneously / 同时触发两个通道：
        1. PluginEventBus — async notification (read-only, handler errors don't affect publisher)
           / 异步通知（只读，handler 异常不影响发布方）
        2. HookRegistry — sync interception (can modify context, for BEFORE_*/AFTER_*)
           / 同步拦截（可修改 context，用于 BEFORE_*/AFTER_*）

        Event name / 事件名：plugin.{name}.{event_name}

        Args:
            event_name: Event name (without plugin.{name}. prefix) / 事件名称
            data: Event data / 事件数据

        Returns:
            Context dict after hook processing (PluginEventBus doesn't modify data)
            / 钩子处理后的上下文字典
        """
        full_event = f"plugin.{self.plugin_name}.{event_name}"

        context = dict(data or {})
        context["plugin_name"] = self.plugin_name
        context["event_name"] = event_name

        # 1. PluginEventBus — async notification (non-blocking, doesn't modify context)
        # / PluginEventBus — 异步通知（不阻塞、不修改 context）
        from app.plugins.event_bus import get_plugin_event_bus

        bus = get_plugin_event_bus()
        if bus.has_subscribers(full_event):
            bus_result = await bus.publish(
                full_event, context, source_plugin=self.plugin_name,
            )
            logger.info(
                "Plugin %s event '%s': bus delivered=%d failed=%d",
                self.plugin_name, event_name,
                bus_result["delivered"], bus_result["failed"],
            )

        # 2. HookRegistry — sync interception (can modify context)
        # / HookRegistry — 同步拦截（可修改 context）
        from app.ai.events.hooks import HookRegistry

        hook_registry = HookRegistry.get_instance()
        if hook_registry.has_hooks(full_event):
            context = await hook_registry.trigger(full_event, **context)
            logger.info(
                "Plugin %s event '%s': %d hooks triggered",
                self.plugin_name, event_name,
                len(hook_registry._hooks.get(full_event, [])),
            )

        return context

    def subscribe_event(
        self,
        event_name: str,
        handler: Any,
        priority: int = 100,
    ) -> None:
        """
        Subscribe to other plugins' events (cross-plugin communication).
        / 订阅其他插件的事件（跨插件通信）。

        Args:
            event_name: Full event name (e.g. "plugin.novusdoc.document_saved") / 完整事件名
            handler: Async handler function, signature (event_name: str, payload: dict) -> None
            priority: Priority (lower number = higher priority) / 优先级（数字越小越优先）
        """
        from app.plugins.event_bus import get_plugin_event_bus

        bus = get_plugin_event_bus()
        bus.subscribe(
            event_name, handler,
            plugin_name=self.plugin_name,
            priority=priority,
        )

    # ── System / 系统 ──

    def get_platform_version(self) -> str:
        """Get platform version / 获取平台版本"""
        from app.core.config import settings

        return settings.APP_VERSION

    def get_current_tenant_id(self) -> int | None:
        """Get current request's tenant ID (injected from RequestContext) / 获取当前请求的租户 ID（从 RequestContext 注入）"""
        if self._request_context:
            return self._request_context.tenant_id
        return None

    def get_current_user_id(self) -> int | None:
        """Get current request's user ID (injected from RequestContext) / 获取当前请求的用户 ID（从 RequestContext 注入）"""
        if self._request_context:
            return self._request_context.user_id
        return None

    def get_current_user_role(self) -> str:
        """Get current request's user role (admin / tenant_admin / tenant_user) / 获取当前请求的用户角色"""
        if self._request_context:
            return self._request_context.user_role
        return ""

    def get_request_id(self) -> str:
        """Get current request ID (for trace linking) / 获取当前请求 ID（用于链路追踪）"""
        if self._request_context:
            return self._request_context.request_id
        return ""

    async def push_to_user(
        self,
        user_id: int,
        event: str,
        data: dict | None = None,
        side: str = "tenant",
    ) -> bool:
        """
        Push data to a specific user in real-time via Socket.IO.
        / 通过 Socket.IO 向指定用户实时推送数据。

        Requires notifications:send capability. / 需 notifications:send 能力。

        Args:
            user_id: Target user ID / 目标用户 ID
            event:   Event name (frontend listens on this); framework auto-adds plugin.{name}. prefix
                     / 事件名；框架自动添加 plugin.{name}. 前缀防止冲突
            data:    Data dict to push / 要推送的数据字典
            side:    Target side "admin" | "tenant" (determines SIO namespace)
                     / 目标端（决定 SIO namespace /admin 或 /tenant）

        Returns:
            True = push succeeded, False = SIO unavailable (non-blocking degradation)
            / True = 推送成功，False = SIO 不可用（非阻塞降级）
        """
        self._require("notifications:send")
        full_event = f"plugin.{self.plugin_name}.{event}"
        namespace = "/admin" if side == "admin" else "/tenant"
        room = f"user:{user_id}"
        payload = {**(data or {}), "plugin": self.plugin_name, "event": event}
        try:
            from app.core.socketio_server import get_sio
            sio = get_sio()
            await sio.emit(full_event, payload, room=room, namespace=namespace)
            logger.debug(
                "Plugin %s: pushed event '%s' to user %d (%s)",
                self.plugin_name, event, user_id, side,
            )
            return True
        except Exception as exc:
            logger.warning(
                "Plugin %s: push_to_user failed (user=%d event=%s): %s",
                self.plugin_name, user_id, event, exc,
            )
            return False

    async def is_feature_enabled(self, feature_code: str) -> bool:
        """
        Check if a Feature Flag is enabled.
        / 检查 Feature Flag 是否启用。

        Reads toggle state from Plugin.config['_feature_flags'].
        Unconfigured features default to manifest.features' default value.
        / 从 Plugin.config['_feature_flags'] 读取开关状态。
        未配置的功能默认按 manifest.features 的 default 值。
        """
        from sqlalchemy import select

        from app.models.system.plugin import Plugin

        result = await self._db.execute(
            select(Plugin.config, Plugin.manifest).where(
                Plugin.name == self.plugin_name,
                Plugin.is_deleted.is_(False),
            )
        )
        row = result.one_or_none()
        if not row:
            return True

        config = row[0] or {}
        flags = config.get("_feature_flags", {})

        # If already set, return directly / 如果已设置，直接返回
        if feature_code in flags:
            return bool(flags[feature_code])

        # Not set, check manifest.features default value / 未设置，查 manifest.features 的 default 值
        manifest_data = row[1] or {}
        features = manifest_data.get("features", [])
        for feat in features:
            if feat.get("code") == feature_code:
                return feat.get("default", True)

        return True  # Undeclared features default to enabled / 未声明的功能默认启用


class _NamespacedStorageProxy:
    """Storage proxy — restricts plugins to only access files under plugins/{name}/ path
    / 存储代理 — 限制插件只能访问 plugins/{name}/ 路径下的文件

    Method signatures align with StorageDriver base class, but paths are auto-prefixed with plugins/{name}/.
    / 方法签名与 StorageDriver 基类对齐，但路径自动加 plugins/{name}/ 前缀。
    """

    def __init__(self, driver: Any, namespace: str) -> None:
        self._driver = driver
        self._namespace = namespace

    def _ns_path(self, path: str) -> str:
        """Normalize path and ensure it doesn't escape namespace (prevent ../ path traversal) / 规范化路径并确保不逃逸命名空间（防止 ../ 路径遍历）"""
        import posixpath

        stripped = path.lstrip("/")
        if not stripped:
            return self._namespace
        normalized = posixpath.normpath(stripped)
        if normalized.startswith("..") or normalized == ".":
            from app.plugins.exceptions import PluginSecurityError
            raise PluginSecurityError(
                message=f"Path traversal attempt detected in storage access: '{path}'",
            )
        return f"{self._namespace}/{normalized}"

    async def put(
        self,
        path: str,
        content: Any,
        mime_type: str | None = None,
        **kwargs: Any,
    ) -> Any:
        return await self._driver.put(self._ns_path(path), content, mime_type=mime_type, **kwargs)

    async def get(self, path: str) -> Any:
        return await self._driver.get(self._ns_path(path))

    async def delete(self, path: str) -> bool:
        return await self._driver.delete(self._ns_path(path))

    async def exists(self, path: str) -> bool:
        return await self._driver.exists(self._ns_path(path))

    async def get_url(self, path: str, expires: int = 3600, **kwargs: Any) -> str:
        return await self._driver.get_url(self._ns_path(path), expires=expires, **kwargs)

    async def get_info(self, path: str) -> Any:
        return await self._driver.get_info(self._ns_path(path))
