"""
插件沙箱上下文

PluginContext 是插件与核心系统交互的唯一入口。
所有方法在执行前检查能力授权（capabilities）。
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from app.core.logging import get_logger
from app.plugins.exceptions import PluginSecurityError

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.plugins.manifest import PluginManifest

logger = get_logger(__name__)


class PluginDbProxy:
    """
    数据库代理 — 限制插件只能操作 px_{name}_* 表

    包装 AsyncSession，拦截 execute() 检查表名前缀。
    """

    def __init__(self, db: AsyncSession, plugin_name: str) -> None:
        self._db = db
        self._table_prefix = f"px_{plugin_name.replace('-', '_')}_"

    @property
    def session(self) -> AsyncSession:
        """获取原始 session（仅框架内部使用）"""
        return self._db

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
        table_name = getattr(instance.__class__, "__tablename__", "")
        if table_name and not table_name.startswith(self._table_prefix):
            raise PluginSecurityError(
                message=f"Plugin can only operate on tables with prefix '{self._table_prefix}', "
                f"got '{table_name}'",
            )
        self._db.add(instance)

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

                # 允许的表：插件自有表、alembic 版本表、空表名
                if table_name and not table_name.startswith(self._table_prefix):
                    if table_name not in ("alembic_version", "information_schema"):
                        raise PluginSecurityError(
                            message=f"Plugin can only access tables with prefix "
                            f"'{self._table_prefix}', attempted: '{table_name}'",
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
    ) -> None:
        self.plugin_name = plugin_name
        self.manifest = manifest
        self._db = db
        self._granted_capabilities = set(granted_capabilities or [])
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
        from app.models.system.plugin_tenant_assignment import PluginTenantAssignment

        result = await self._db.execute(
            select(PluginTenantAssignment.config).join(
                Plugin, Plugin.id == PluginTenantAssignment.plugin_id
            ).where(
                Plugin.name == self.plugin_name,
                PluginTenantAssignment.tenant_id == tenant_id,
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
        """返回限制只能操作 px_{name}_* 表的数据库代理，需 db:own_tables 能力"""
        self._require("db:own_tables")
        return PluginDbProxy(self._db, self.plugin_name)

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

    async def call_ai_feature(
        self, feature_code: str, messages: list[dict]
    ) -> str:
        """
        调用 AI 功能，需 ai:call 能力。

        通过 SystemAgentAssignment 查找绑定的 Agent，
        然后调用 AgentChatService 进行对话。

        Args:
            feature_code: 功能代码（不含 plugin.{name}. 前缀）
            messages: 对话消息列表（[{"role": "user", "content": "..."}]）

        Returns:
            AI 响应文本
        """
        self._require("ai:call")

        from sqlalchemy import select

        from app.models.system.agent_assignment import SystemAgentAssignment

        # 构建完整的 feature_code
        full_code = f"plugin.{self.plugin_name}.{feature_code}"

        # 查找绑定的 Agent（优先租户覆盖 → 全局默认）
        tenant_id = self.get_current_tenant_id()
        query = select(
            SystemAgentAssignment.agent_id,
            SystemAgentAssignment.tenant_id,
        ).where(
            SystemAgentAssignment.feature_code == full_code,
            SystemAgentAssignment.is_active.is_(True),
            SystemAgentAssignment.is_deleted.is_(False),
        ).order_by(
            # tenant_id IS NOT NULL 优先（租户覆盖 > 全局默认）
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

        # 查找 Agent 的 tenant_id（Agent 可能是全局的 tenant_id=NULL）
        from app.models.ai.agent import Agent
        agent_result = await self._db.execute(
            select(Agent.tenant_id).where(Agent.id == agent_id)
        )
        agent_tenant_id = agent_result.scalar_one_or_none()
        # 使用 Agent 所属租户，若全局则用插件上下文的租户
        effective_tenant_id = agent_tenant_id or resolved_tenant_id or 0

        # 调用 AgentChatService
        from app.services.ai.agent_chat_service import AgentChatService

        chat_service = AgentChatService(self._db, effective_tenant_id)
        # 取最后一条 user message 作为输入
        user_message = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                user_message = msg.get("content", "")
                break
        if not user_message and messages:
            user_message = messages[-1].get("content", "")

        response = await chat_service.chat(
            agent_id=agent_id,
            message=user_message,
        )
        return response.message

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
        触发自定义钩子点 plugin.{name}.{event_name}

        通过 HookRegistry 触发已注册的钩子处理器，传递 data 作为上下文。

        Args:
            event_name: 事件名称（不含 plugin.{name}. 前缀）
            data: 传递给钩子处理器的上下文数据

        Returns:
            钩子处理后的上下文字典
        """
        from app.ai.events.hooks import HookRegistry

        hook_point = f"plugin.{self.plugin_name}.{event_name}"
        registry = HookRegistry.get_instance()

        context = dict(data or {})
        context["plugin_name"] = self.plugin_name
        context["event_name"] = event_name

        if registry.has_hooks(hook_point):
            context = await registry.trigger(hook_point, **context)
            logger.info(
                "Plugin %s emitted event '%s' (%d hooks triggered)",
                self.plugin_name, event_name,
                len(registry._hooks.get(hook_point, [])),
            )
        else:
            logger.debug(
                "Plugin %s emitted event '%s' (no hooks registered)",
                self.plugin_name, event_name,
            )

        return context

    # ── 系统 ──

    def get_platform_version(self) -> str:
        """获取平台版本"""
        from app.core.config import settings

        return settings.APP_VERSION

    def get_current_tenant_id(self) -> int | None:
        """获取当前请求的租户 ID（如有）"""
        # 在实际请求上下文中会从 middleware 获取
        return None

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
