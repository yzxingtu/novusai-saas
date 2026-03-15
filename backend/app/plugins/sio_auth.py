"""
Plugin Socket.IO auth wrapper. / 插件 Socket.IO 鉴权包装器。

Provides unified JWT authentication, tenant isolation, and connection rate limiting
for plugin-registered Socket.IO namespaces. Wraps plugin-custom AsyncNamespace
via proxy pattern, injecting auth logic before on_connect.
/ 为插件注册的 Socket.IO namespace 提供统一的 JWT 认证、企业隔离、连接限流能力。
"""

from __future__ import annotations

import contextlib
from typing import Any

import socketio

from app.core.logging import LogManager

logger = LogManager.get_logger("plugin.sio")

# Scope constant mapping (consistent with app.core.security)
# / scope 常量映射
_SCOPE_MAP = {
    "admin": "admin",
    "tenant_admin": "tenant_admin",
    "tenant_user": "tenant_user",
}


class PluginAuthNamespaceWrapper(socketio.AsyncNamespace):
    """
    Plugin Socket.IO namespace auth proxy.
    / 插件 Socket.IO namespace 鉴权代理

    Wraps plugin-custom AsyncNamespace subclass, injecting JWT validation +
    scope check + tenant isolation + connection rate limiting before on_connect.
    / 包装插件自定义的 AsyncNamespace 子类，注入鉴权逻辑。

    After auth passes, session_data (user_id, user_type, tenant_id) is saved
    to SIO session; plugin handler can access via get_session(sid).
    / 鉴权通过后保存 session_data 到 SIO session。

    All non connect/disconnect events are delegated directly to plugin handler.
    / 所有非 connect/disconnect 事件直接委托给插件 handler。
    """

    def __init__(
        self,
        delegate: socketio.AsyncNamespace,
        plugin_name: str,
        auth_scopes: list[str] | None = None,
    ) -> None:
        # Use delegate's namespace path / 使用 delegate 的 namespace 路径
        super().__init__(delegate.namespace)
        self._delegate = delegate
        self._plugin_name = plugin_name
        self._auth_scopes = auth_scopes or ["tenant_admin"]
        # Point delegate's server reference to self (set by server after registration)
        # / 将 delegate 的 server 引用指向自身
        self._delegate_event_handlers: dict[str, Any] = {}
        # sid → session backup (instance-level, avoid cross-plugin sid key conflicts)
        # / sid → session 备份
        self._sid_sessions: dict[str, dict] = {}

    def _set_server(self, server: Any) -> None:
        """Server registration callback — sync set delegate's server
        / server 注册回调"""
        super()._set_server(server)
        if hasattr(self._delegate, "_set_server"):
            self._delegate._set_server(server)

    async def on_connect(
        self, sid: str, environ: dict, auth: dict | None = None
    ) -> None:
        """
        Connection authentication.
        / 连接鉴权

        1. Check WS master switch / 检查 WS 总开关
        2. Extract and verify JWT token + scope / 提取并验证 JWT
        3. Connection rate limiting / 连接频率限制
        4. Per-user max connection limit / 单用户最大连接数限制
        5. Query user info (confirm exists and active) / 查询用户信息
        6. Save session, join rooms / 保存 session，加入 rooms
        7. Delegate to plugin handler's on_connect (if any) / 委托给插件 handler
        """
        # 1. WS master switch / WS 总开关
        from app.sio.ws_config import get_ws_configs

        ws_cfg = await get_ws_configs("ws_enabled", "ws_max_connections_per_user")
        if not ws_cfg.get("ws_enabled", True):
            raise ConnectionRefusedError("websocket_disabled")

        # 2. JWT authentication / JWT 认证
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

        # 3. Connection rate limiting / 连接频率限制
        from app.sio.presence import check_connect_rate

        rate_key = f"plugin_{self._plugin_name}_{matched_scope}"
        if not await check_connect_rate(rate_key, user_id):
            raise ConnectionRefusedError("rate_limited")

        # 4. Per-user max connection limit / 单用户最大连接数限制
        from app.sio.presence import PresenceManager

        max_conn = int(ws_cfg.get("ws_max_connections_per_user", 5))
        current_conn = await PresenceManager.get_user_connection_count(
            rate_key, user_id,
        )
        if current_conn >= max_conn:
            raise ConnectionRefusedError("max_connections_exceeded")

        # 5. Query user + tenant_id / 查询用户
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

        # 6. Save session / 保存 session
        session_data = {
            "user_id": user_id,
            "user_type": matched_scope,
            "tenant_id": tenant_id,
            "username": username,
            "plugin_name": self._plugin_name,
        }
        await self.save_session(sid, session_data)
        self._sid_sessions[sid] = session_data

        # Join standard rooms / 加入标准 rooms
        await self.enter_room(sid, f"user:{user_id}")
        if tenant_id:
            await self.enter_room(sid, f"tenant:{tenant_id}")

        # Online status / 在线状态
        await PresenceManager.set_online(rate_key, user_id, tenant_id)

        logger.info(
            "Plugin SIO %s connected: sid=%s user_id=%d scope=%s tenant_id=%s",
            self.namespace, sid, user_id, matched_scope, tenant_id,
        )

        # 7. Delegate to plugin handler's on_connect (if any)
        # / 委托给插件 handler
        if hasattr(self._delegate, "on_connect"):
            await self._delegate.on_connect(sid, environ, auth)

    async def on_disconnect(self, sid: str, reason: str = "") -> None:
        """Disconnect, clean up online status, delegate to plugin handler
        / 断开连接，清理在线状态，委托给插件 handler"""
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

        # Delegate to plugin handler's on_disconnect (if any)
        # / 委托给插件 handler
        if hasattr(self._delegate, "on_disconnect"):
            await self._delegate.on_disconnect(sid, reason)

    async def _trigger_event(self, event: str, *args: Any) -> Any:
        """
        Event dispatch — delegate non connect/disconnect events to plugin handler.
        / 事件分发 — 非 connect/disconnect 事件委托给插件 handler。

        python-socketio's AsyncNamespace calls _trigger_event when receiving events.
        Override this method to route custom events to plugin delegate.
        / 覆盖此方法，将自定义事件路由到插件 delegate。
        """
        # connect/disconnect already handled by this class
        # / connect/disconnect 已由本类处理
        if event in ("connect", "disconnect"):
            return await super()._trigger_event(event, *args)

        # Delegate to plugin handler (compatible with async/sync)
        # / 委托给插件 handler
        handler = getattr(self._delegate, f"on_{event}", None)
        if handler:
            import asyncio
            if asyncio.iscoroutinefunction(handler):
                return await handler(*args)
            return handler(*args)

        # No matching handler — ignore / 无匹配 handler
        return None


__all__ = ["PluginAuthNamespaceWrapper"]
