"""
插件沙箱上下文

PluginContext 是插件与核心系统交互的唯一入口。
所有方法在执行前检查能力授权（capabilities）。
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING, Any

from dataclasses import dataclass, field

from app.core.logging import get_logger
from app.enums.plugin import PluginLicenseTypeEnum
from app.plugins.exceptions import PluginSecurityError

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.plugins.manifest import PluginManifest

logger = get_logger(__name__)


@dataclass(frozen=True)
class RequestContext:
    """
    请求上下文 — 从 HTTP 请求 / WebSocket 连接中提取的身份信息。

    在 API dispatcher 层创建，注入到 PluginContext。
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
    数据库代理 — 限制插件只能操作 px_{name}_* 表

    包装 AsyncSession，拦截 execute() 检查表名前缀。
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
        """禁止暴露原始 session，避免绕过沙箱检查。"""
        raise PluginSecurityError(
            message="Access to raw session is forbidden in plugin sandbox",
        )

    async def execute(self, statement: Any, *args: Any, **kwargs: Any) -> Any:
        """执行 SQL，检查表名前缀"""
        sql_text = str(statement)
        self._check_table_access(sql_text)
        return await self._db.execute(statement, *args, **kwargs)

    async def flush(self) -> None:
        await self._db.flush()

    async def commit(self) -> None:
        await self._db.commit()

    async def rollback(self) -> None:
        await self._db.rollback()

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
        """检查 SQL 是否只涉及插件自有表（基础检查）"""
        sql_lower = sql_text.lower()
        # 跳过空语句和参数化查询占位
        if not sql_lower.strip():
            return
        # 检查常见的表操作关键字后的表名
        for keyword in ("from ", "join ", "into ", "update ", "table "):
            pos = 0
            while True:
                idx = sql_lower.find(keyword, pos)
                if idx == -1:
                    break
                table_start = idx + len(keyword)
                # 提取表名（去除引号和空格）
                rest = sql_lower[table_start:].lstrip().lstrip('"').lstrip("'")
                # 取到空格或括号为止
                table_end = len(rest)
                for ch in (" ", "(", ")", ",", ";", "\n", "\t", '"', "'"):
                    ch_pos = rest.find(ch)
                    if 0 <= ch_pos < table_end:
                        table_end = ch_pos
                table_name = rest[:table_end].strip()

                # 允许的表：插件自有表、声明依赖插件表、alembic 元表
                if table_name and not self._is_allowed_table(table_name):
                    if table_name not in ("alembic_version", "information_schema"):
                        raise PluginSecurityError(
                            message=f"Plugin can only access tables with prefixes "
                            f"{self._allowed_prefixes}, attempted: '{table_name}'",
                        )
                pos = table_start


class PluginContext:
    """
    插件沙箱上下文

    插件生命周期钩子的 ctx 参数类型。提供受控的系统访问 API。
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

    # ── 能力检查 ──

    def _require(self, cap: str) -> None:
        """检查插件是否拥有指定能力，无则抛出 PluginSecurityError"""
        if cap not in self._granted_capabilities:
            raise PluginSecurityError(
                message=f"Plugin '{self.plugin_name}' requires capability '{cap}' "
                f"which has not been granted",
            )

    def has_capability(self, cap: str) -> bool:
        """检查插件是否拥有指定能力"""
        return cap in self._granted_capabilities

    # ── 配置 ──

    async def get_config(self) -> dict:
        """
        获取插件全局配置（自动解密敏感字段）

        从 Plugin.config 读取，根据 manifest.config_schema 中的
        x-encrypted 标记自动解密。
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
        """获取租户级配置"""
        from sqlalchemy import select

        from app.models.system.plugin import Plugin
        from app.models.system.resource_tenant_assignment import ResourceTenantAssignment

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
        """更新插件全局配置（自动加密敏感字段），需 config:write 能力"""
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

    # ── 数据库 ──

    def get_db(self) -> PluginDbProxy:
        """返回数据库代理（默认仅自有表；可扩展到声明依赖插件表），需 db:own_tables 能力"""
        self._require("db:own_tables")

        own_prefix = f"px_{self.plugin_name.replace('-', '_')}_"
        allowed_prefixes = [own_prefix]
        dependencies = getattr(getattr(self.manifest, "dependencies", None), "plugins", []) or []
        for dep_name in dependencies:
            allowed_prefixes.append(f"px_{str(dep_name).replace('-', '_')}_")

        return PluginDbProxy(
            self._db,
            self.plugin_name,
            allowed_table_prefixes=allowed_prefixes,
        )

    async def get_own_license_status(self) -> dict[str, Any]:
        """
        获取当前插件的许可证状态（受控只读）。

        仅允许读取当前插件自身的 license，不暴露任意系统表访问能力。
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
        if license_record.license_type == _TRIAL:
            if license_record.trial_expires_at and now < license_record.trial_expires_at:
                remaining = (license_record.trial_expires_at - now).days
                return {
                    "status": "trial",
                    "license_type": _TRIAL,
                    "is_valid": True,
                    "trial_days_remaining": remaining,
                    "expires_at": str(license_record.trial_expires_at),
                }
            return {
                "status": "expired",
                "license_type": _TRIAL,
                "is_valid": False,
                "message": "Trial period expired",
            }

        if license_record.is_valid:
            return {
                "status": "active",
                "license_type": license_record.license_type,
                "is_valid": True,
                "license_key": "****",
                "activated_at": str(license_record.activated_at) if license_record.activated_at else None,
            }

        return {
            "status": "expired",
            "license_type": license_record.license_type,
            "is_valid": False,
            "message": "License expired or revoked",
        }

    # ── 日志 ──

    def get_logger(self) -> logging.Logger:
        """返回插件专属 Logger"""
        if self._logger is None:
            self._logger = get_logger(f"plugin.{self.plugin_name}")
        return self._logger

    # ── 存储 ──

    async def get_storage(self) -> Any:
        """
        返回路径限定在 plugins/{name}/ 命名空间的存储驱动。

        需要 storage:read 或 storage:write 能力。
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

    # ── HTTP ──

    async def http_request(
        self,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> dict:
        """
        发送 HTTP 请求，需 http:outbound 能力。

        自动添加 30 秒超时保护。
        """
        self._require("http:outbound")
        import httpx

        kwargs.setdefault("timeout", 30.0)
        async with httpx.AsyncClient() as client:
            response = await client.request(method, url, **kwargs)
            return {
                "status_code": response.status_code,
                "headers": dict(response.headers),
                "body": response.text,
            }

    # ── AI ──

    async def _resolve_ai_assignment(
        self, feature_code: str,
    ) -> tuple[int, int]:
        """
        解析 AI 功能绑定：查找 agent_id 和 effective_tenant_id。

        Args:
            feature_code: 功能代码（不含 plugin.{name}. 前缀）

        Returns:
            (agent_id, effective_tenant_id)

        Raises:
            PluginError: 未绑定 Agent
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

        # 校验绑定的 Agent 仍然存在且已发布
        from app.models.ai.agent import Agent
        from app.enums.agent import AgentStatusEnum

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

        # effective_tenant_id 用于 AgentChatService 创建对话记录
        # 始终使用请求者的 tenant_id（即使 agent 是全局的 tenant_id=NULL）
        effective_tenant_id = resolved_tenant_id or 0

        return agent_id, effective_tenant_id

    @staticmethod
    def _extract_user_message(messages: list[dict]) -> str:
        """从消息列表中提取最后一条 user 消息内容"""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                return msg.get("content", "")
        if messages:
            return messages[-1].get("content", "")
        return ""

    async def call_ai_feature(
        self, feature_code: str, messages: list[dict]
    ) -> str:
        """
        调用 AI 功能（非流式），需 ai:call 能力。

        通过 SystemAgentAssignment 查找绑定的 Agent，
        然后调用 AgentChatService 进行对话。

        Args:
            feature_code: 功能代码（不含 plugin.{name}. 前缀）
            messages: 对话消息列表（[{"role": "user", "content": "..."}]）

        Returns:
            AI 响应文本
        """
        self._require("ai:call")

        agent_id, effective_tenant_id = await self._resolve_ai_assignment(
            feature_code,
        )

        from app.services.ai.agent_chat_service import AgentChatService

        chat_service = AgentChatService(self._db, effective_tenant_id)
        user_message = self._extract_user_message(messages)

        response = await chat_service.chat(
            agent_id=agent_id,
            message=user_message,
        )
        return response.message

    async def call_ai_feature_stream(
        self,
        feature_code: str,
        messages: list[dict],
    ) -> AsyncGenerator[str, None]:
        """
        调用 AI 功能（流式），需 ai:call 能力。

        通过 SystemAgentAssignment 查找绑定的 Agent，
        调用 AgentChatService.stream_chat 获取 SSE 流，
        解析并仅 yield 文本增量（delta）。

        SSE 事件格式：
        - message 事件: yield delta 文本
        - done 事件: 流正常结束
        - error 事件: 抛出 PluginError
        - 其他事件（tool_call, thinking 等）: 跳过

        如果上游模型不支持流式或 stream_chat 异常，
        自动降级为非流式 call_ai_feature 并将完整内容
        作为单个 chunk yield。

        Args:
            feature_code: 功能代码（不含 plugin.{name}. 前缀）
            messages: 对话消息列表（[{"role": "user", "content": "..."}]）

        Yields:
            文本增量字符串（仅内容部分，不含 SSE 包装）
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
            sse_response = await chat_service.stream_chat(
                agent_id=agent_id,
                message=user_message,
            )

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
        """检查 AI 功能是否已配置（自动添加 plugin.{name}. 前缀）"""
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

    # ── 通知 ──

    async def send_notification(
        self,
        tenant_id: int,
        user_ids: list[int],
        template_code: str,
        variables: dict | None = None,
    ) -> None:
        """发送通知，需 notifications:send 能力"""
        self._require("notifications:send")
        from app.services.common.notification_service import notify

        recipients = [("tenant_admin", uid) for uid in user_ids]
        await notify(self._db, template_code, recipients, variables or {})

    # ── 事件 ──

    async def emit_event(self, event_name: str, data: dict | None = None) -> dict:
        """
        发布跨插件事件 + 触发同名钩子点。

        同时触发两个通道：
        1. PluginEventBus — 异步通知（只读，handler 异常不影响发布方）
        2. HookRegistry — 同步拦截（可修改 context，用于 BEFORE_*/AFTER_*）

        事件名：plugin.{name}.{event_name}

        Args:
            event_name: 事件名称（不含 plugin.{name}. 前缀）
            data: 事件数据

        Returns:
            钩子处理后的上下文字典（PluginEventBus 不修改数据）
        """
        full_event = f"plugin.{self.plugin_name}.{event_name}"

        context = dict(data or {})
        context["plugin_name"] = self.plugin_name
        context["event_name"] = event_name

        # 1. PluginEventBus — 异步通知（不阻塞、不修改 context）
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

        # 2. HookRegistry — 同步拦截（可修改 context）
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
        订阅其他插件的事件（跨插件通信）。

        Args:
            event_name: 完整事件名（如 "plugin.novusdoc.document_saved"）
            handler: async 处理函数，签名 (event_name: str, payload: dict) -> None
            priority: 优先级（数字越小越优先）
        """
        from app.plugins.event_bus import get_plugin_event_bus

        bus = get_plugin_event_bus()
        bus.subscribe(
            event_name, handler,
            plugin_name=self.plugin_name,
            priority=priority,
        )

    # ── 系统 ──

    def get_platform_version(self) -> str:
        """获取平台版本"""
        from app.core.config import settings

        return settings.APP_VERSION

    def get_current_tenant_id(self) -> int | None:
        """获取当前请求的租户 ID（从 RequestContext 注入）"""
        if self._request_context:
            return self._request_context.tenant_id
        return None

    def get_current_user_id(self) -> int | None:
        """获取当前请求的用户 ID（从 RequestContext 注入）"""
        if self._request_context:
            return self._request_context.user_id
        return None

    def get_current_user_role(self) -> str:
        """获取当前请求的用户角色（admin / tenant_admin / tenant_user）"""
        if self._request_context:
            return self._request_context.user_role
        return ""

    def get_request_id(self) -> str:
        """获取当前请求 ID（用于链路追踪）"""
        if self._request_context:
            return self._request_context.request_id
        return ""

    async def is_feature_enabled(self, feature_code: str) -> bool:
        """
        检查 Feature Flag 是否启用。

        从 Plugin.config['_feature_flags'] 读取开关状态。
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

        # 如果已设置，直接返回
        if feature_code in flags:
            return bool(flags[feature_code])

        # 未设置，查 manifest.features 的 default 值
        manifest_data = row[1] or {}
        features = manifest_data.get("features", [])
        for feat in features:
            if feat.get("code") == feature_code:
                return feat.get("default", True)

        return True  # 未声明的功能默认启用


class _NamespacedStorageProxy:
    """存储代理 — 限制插件只能访问 plugins/{name}/ 路径下的文件"""

    def __init__(self, driver: Any, namespace: str) -> None:
        self._driver = driver
        self._namespace = namespace

    def _ns_path(self, path: str) -> str:
        return f"{self._namespace}/{path.lstrip('/')}"

    async def put(self, path: str, content: bytes, **kwargs: Any) -> str:
        return await self._driver.put(self._ns_path(path), content, **kwargs)

    async def get(self, path: str) -> bytes:
        return await self._driver.get(self._ns_path(path))

    async def delete(self, path: str) -> bool:
        return await self._driver.delete(self._ns_path(path))

    async def exists(self, path: str) -> bool:
        return await self._driver.exists(self._ns_path(path))

    async def url(self, path: str, expires: int = 3600) -> str:
        return await self._driver.url(self._ns_path(path), expires)
