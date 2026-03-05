"""
插件 Socket.IO 鉴权包装器

为插件注册的 Socket.IO namespace 提供统一的 JWT 认证、
租户隔离、连接限流能力。通过代理模式包装插件自定义的
AsyncNamespace，在 on_connect 前注入鉴权逻辑。
"""

from __future__ import annotations

import contextlib
from typing import Any

import socketio

from app.core.logging import LogManager

logger = LogManager.get_logger("plugin.sio")

# scope 常量映射（与 app.core.security 保持一致）
_SCOPE_MAP = {
    "admin": "admin",
    "tenant_admin": "tenant_admin",
    "tenant_user": "tenant_user",
}


class PluginAuthNamespaceWrapper(socketio.AsyncNamespace):
    """
    插件 Socket.IO namespace 鉴权代理

    包装插件自定义的 AsyncNamespace 子类，在 on_connect 前
    注入 JWT 验证 + scope 校验 + 租户隔离 + 连接限流。

    鉴权通过后，将 session_data（user_id, user_type, tenant_id）
    保存到 SIO session，插件 handler 可通过 get_session(sid) 获取。

    所有非 connect/disconnect 事件直接委托给插件 handler。
    """

    def __init__(
        self,
        delegate: socketio.AsyncNamespace,
        plugin_name: str,
        auth_scopes: list[str] | None = None,
    ) -> None:
        # 使用 delegate 的 namespace 路径
        super().__init__(delegate.namespace)
        self._delegate = delegate
        self._plugin_name = plugin_name
        self._auth_scopes = auth_scopes or ["tenant_admin"]
        # 将 delegate 的 server 引用指向自身（注册后由 server 设置）
        self._delegate_event_handlers: dict[str, Any] = {}
        # sid → session 备份（实例级，避免跨插件 sid 键名冲突）
        self._sid_sessions: dict[str, dict] = {}

    def _set_server(self, server: Any) -> None:
        """server 注册回调 — 同步设置 delegate 的 server"""
        super()._set_server(server)
        if hasattr(self._delegate, "_set_server"):
            self._delegate._set_server(server)

    async def on_connect(
        self, sid: str, environ: dict, auth: dict | None = None
    ) -> None:
        """
        连接鉴权

        1. 检查 WS 总开关
        2. 提取并验证 JWT token + scope
        3. 连接频率限制
        4. 单用户最大连接数限制
        5. 查询用户信息（确认存在且激活）
        6. 保存 session，加入 rooms
        7. 委托给插件 handler 的 on_connect（如有）
        """
        # 1. WS 总开关
        from app.sio.ws_config import get_ws_configs

        ws_cfg = await get_ws_configs("ws_enabled", "ws_max_connections_per_user")
        if not ws_cfg.get("ws_enabled", True):
            raise ConnectionRefusedError("websocket_disabled")

        # 2. JWT 认证
        if not auth or not auth.get("token"):
            raise ConnectionRefusedError("token_required")

        token = str(auth["token"]).removeprefix("Bearer ").strip()
        if not token:
            raise ConnectionRefusedError("token_required")

        from app.core.security import TokenExpiredError, verify_token_with_scope

        user_id_str = None
        matched_scope = None

        for scope_name in self._auth_scopes:
            scope_const = _SCOPE_MAP.get(scope_name)
            if not scope_const:
                continue
            try:
                from app.core.security import (
                    TOKEN_SCOPE_ADMIN,
                    TOKEN_SCOPE_TENANT_ADMIN,
                    TOKEN_SCOPE_TENANT_USER,
                )

                scope_value = {
                    "admin": TOKEN_SCOPE_ADMIN,
                    "tenant_admin": TOKEN_SCOPE_TENANT_ADMIN,
                    "tenant_user": TOKEN_SCOPE_TENANT_USER,
                }.get(scope_const)
                if scope_value is None:
                    continue

                uid, _ = verify_token_with_scope(
                    token, scope_value, raise_on_expired=True,
                )
                if uid:
                    user_id_str = uid
                    matched_scope = scope_name
                    break
            except TokenExpiredError:
                raise ConnectionRefusedError("token_expired")
            except Exception:
                continue

        if not user_id_str or not matched_scope:
            raise ConnectionRefusedError("authentication_failed")

        user_id = int(user_id_str)

        # 3. 连接频率限制
        from app.sio.presence import check_connect_rate

        rate_key = f"plugin_{self._plugin_name}_{matched_scope}"
        if not await check_connect_rate(rate_key, user_id):
            raise ConnectionRefusedError("rate_limited")

        # 4. 单用户最大连接数限制
        from app.sio.presence import PresenceManager

        max_conn = int(ws_cfg.get("ws_max_connections_per_user", 5))
        current_conn = await PresenceManager.get_user_connection_count(
            rate_key, user_id,
        )
        if current_conn >= max_conn:
            raise ConnectionRefusedError("max_connections_exceeded")

        # 5. 查询用户 + tenant_id
        tenant_id = None
        username = ""

        from sqlalchemy import select

        from app.core.database import async_session_factory

        async with async_session_factory() as db:
            if matched_scope == "admin":
                from app.models import Admin

                result = await db.execute(
                    select(Admin).where(
                        Admin.id == user_id,
                        Admin.is_deleted.is_(False),
                        Admin.is_active.is_(True),
                    )
                )
                admin = result.scalar_one_or_none()
                if not admin:
                    raise ConnectionRefusedError("account_not_found")
                username = admin.username

            elif matched_scope == "tenant_admin":
                from app.models import TenantAdmin

                result = await db.execute(
                    select(TenantAdmin).where(
                        TenantAdmin.id == user_id,
                        TenantAdmin.is_deleted.is_(False),
                        TenantAdmin.is_active.is_(True),
                    )
                )
                ta = result.scalar_one_or_none()
                if not ta:
                    raise ConnectionRefusedError("account_not_found")
                tenant_id = ta.tenant_id
                username = ta.username

            elif matched_scope == "tenant_user":
                from app.models import TenantUser

                result = await db.execute(
                    select(TenantUser).where(
                        TenantUser.id == user_id,
                        TenantUser.is_deleted.is_(False),
                        TenantUser.is_active.is_(True),
                    )
                )
                tu = result.scalar_one_or_none()
                if not tu:
                    raise ConnectionRefusedError("account_not_found")
                tenant_id = tu.tenant_id
                username = tu.username

        # 6. 保存 session
        session_data = {
            "user_id": user_id,
            "user_type": matched_scope,
            "tenant_id": tenant_id,
            "username": username,
            "plugin_name": self._plugin_name,
        }
        await self.save_session(sid, session_data)
        self._sid_sessions[sid] = session_data

        # 加入标准 rooms
        await self.enter_room(sid, f"user:{user_id}")
        if tenant_id:
            await self.enter_room(sid, f"tenant:{tenant_id}")

        # 在线状态
        await PresenceManager.set_online(rate_key, user_id, tenant_id)

        logger.info(
            "Plugin SIO %s connected: sid=%s user_id=%d scope=%s tenant_id=%s",
            self.namespace, sid, user_id, matched_scope, tenant_id,
        )

        # 7. 委托给插件 handler 的 on_connect（如有）
        if hasattr(self._delegate, "on_connect"):
            await self._delegate.on_connect(sid, environ, auth)

    async def on_disconnect(self, sid: str, reason: str = "") -> None:
        """断开连接，清理在线状态，委托给插件 handler"""
        session = self._sid_sessions.pop(sid, None)
        if not session:
            with contextlib.suppress(Exception):
                session = await self.get_session(sid)

        if session:
            user_id = session.get("user_id")
            tenant_id = session.get("tenant_id")
            matched_scope = session.get("user_type", "")
            rate_key = f"plugin_{self._plugin_name}_{matched_scope}"

            if user_id:
                try:
                    from app.sio.presence import PresenceManager

                    await PresenceManager.set_offline(
                        rate_key, user_id, tenant_id,
                    )
                except Exception as exc:
                    logger.warning(
                        "Plugin SIO %s presence cleanup failed: %s",
                        self.namespace, exc,
                    )

        logger.info(
            "Plugin SIO %s disconnected: sid=%s reason=%s",
            self.namespace, sid, reason,
        )

        # 委托给插件 handler 的 on_disconnect（如有）
        if hasattr(self._delegate, "on_disconnect"):
            await self._delegate.on_disconnect(sid, reason)

    async def _trigger_event(self, event: str, *args: Any) -> Any:
        """
        事件分发 — 非 connect/disconnect 事件委托给插件 handler。

        python-socketio 的 AsyncNamespace 在收到事件时调用 _trigger_event。
        覆盖此方法，将自定义事件路由到插件 delegate。
        """
        # connect/disconnect 已由本类处理
        if event in ("connect", "disconnect"):
            return await super()._trigger_event(event, *args)

        # 委托给插件 handler（兼容 async/sync）
        handler = getattr(self._delegate, f"on_{event}", None)
        if handler:
            import asyncio
            if asyncio.iscoroutinefunction(handler):
                return await handler(*args)
            return handler(*args)

        # 无匹配 handler — 忽略
        return None


__all__ = ["PluginAuthNamespaceWrapper"]
