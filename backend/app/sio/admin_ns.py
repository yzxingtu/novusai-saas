"""
Socket.IO /admin Namespace

Platform admin real-time communication namespace.
Handles connection auth, room management, and online status broadcast.
平台管理员实时通信 namespace。
处理连接认证、房间管理、在线状态广播。
"""

import uuid

import socketio

from app.core.logging import LogManager
from app.middleware.trace import trace_id_var
from app.core.security import (
    TOKEN_SCOPE_ADMIN,
    TokenExpiredError,
    verify_token_with_scope,
)
from app.sio.page_session import PageSessionMixin

logger = LogManager.get_logger("app")


class AdminNamespace(PageSessionMixin, socketio.AsyncNamespace):
    """
    /admin namespace — Platform admins / 平台管理员

    Rooms:
    - user:{user_id} — All devices of specified admin / 指定管理员的所有设备
    - admins — All platform admins / 所有平台管理员
    - page_session:{id} — Page operation targeting (dynamic join) / 页面操作定位（动态加入）
    """

    # sid → session backup, prevents inability to clean up presence when get_session fails / sid → session 备份，防止 get_session 失败时无法清理 presence
    _sid_sessions: dict[str, dict] = {}

    async def on_connect(self, sid: str, environ: dict, auth: dict | None = None) -> None:
        """
        连接认证 / Connection authentication.

        Extracts JWT from auth.token, verifies scope=admin.
        On success, saves session and joins rooms.
        从 auth.token 提取 JWT，验证 scope=admin。
        成功则保存 session 并加入 rooms。
        """
        # 为 WebSocket 连接生成追踪 ID / Generate trace ID for WebSocket connection
        trace_id_var.set(str(uuid.uuid4()))
        _ = environ
        # Check real-time communication master switch / 检查实时通信总开关
        from app.sio.ws_config import get_ws_configs
        ws_cfg = await get_ws_configs("ws_enabled", "ws_max_connections_per_user")
        if not ws_cfg.get("ws_enabled", True):
            raise ConnectionRefusedError("websocket_disabled")

        if not auth or not auth.get("token"):
            raise ConnectionRefusedError("token_required")

        token = str(auth["token"]).removeprefix("Bearer ").strip()
        if not token:
            raise ConnectionRefusedError("token_required")

        try:
            user_id_str, scope = await verify_token_with_scope(
                token, TOKEN_SCOPE_ADMIN, raise_on_expired=True,
            )
        except TokenExpiredError:
            raise ConnectionRefusedError("token_expired")

        if not user_id_str:
            raise ConnectionRefusedError("authentication_failed")

        user_id = int(user_id_str)

        # Connection rate limiting / 连接频率限制
        from app.sio.presence import check_connect_rate
        if not await check_connect_rate("admin", user_id):
            raise ConnectionRefusedError("rate_limited")

        # Per-user max connection limit / 单用户最大连接数限制
        from app.sio.presence import PresenceManager
        max_conn = int(ws_cfg.get("ws_max_connections_per_user", 5))
        current_conn = await PresenceManager.get_user_connection_count("admin", user_id)
        if current_conn >= max_conn:
            raise ConnectionRefusedError("max_connections_exceeded")

        # Verify admin exists and is active / 验证管理员是否存在且激活
        from sqlalchemy import select

        from app.core.database import async_session_factory
        from app.models import Admin

        async with async_session_factory() as db:
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
            # Extract needed values within session to avoid DetachedInstanceError / 在 session 内提取所需值，避免 DetachedInstanceError
            username = admin.username

        # Save session / 保存 session
        session_data = {
            "user_id": user_id,
            "user_type": "admin",
            "tenant_id": None,
            "username": username,
        }
        await self.save_session(sid, session_data)
        self._sid_sessions[sid] = session_data

        # Join rooms / 加入 rooms
        await self.enter_room(sid, f"user:{user_id}")
        await self.enter_room(sid, "admins")

        # Update online status / 更新在线状态
        connections = await PresenceManager.set_online("admin", user_id)

        # Broadcast online event on first connection / 首次连接时广播上线事件
        if connections == 1:
            await self.emit(
                "presence:online",
                {"user_id": user_id, "user_type": "admin"},
                room="admins",
                skip_sid=sid,
            )

        # Send online list to current connection / 向当前连接发送在线列表
        online_ids = await PresenceManager.get_online_ids("admin")
        await self.emit("presence:list", {"online_ids": online_ids}, to=sid)

        logger.info(
            "SIO /admin connected: sid={} user_id={} username={} connections={}",
            sid, user_id, username, connections,
        )

    async def on_disconnect(self, sid: str, reason: str = "") -> None:
        """Disconnect, update online status / 断开连接，更新在线状态"""
        user_id = None
        try:
            session = await self.get_session(sid)
            user_id = session.get("user_id")
        except Exception as e:
            logger.warning(
                "SIO /admin get_session failed on disconnect: sid={} error={}",
                sid, e,
            )
            # fallback: get from backup mapping / 从备份映射获取
            fallback = self._sid_sessions.get(sid)
            if fallback:
                user_id = fallback.get("user_id")
                logger.info("SIO /admin using fallback session for sid={} user_id={}", sid, user_id)

        if user_id:
            try:
                from app.sio.presence import PresenceManager
                connections = await PresenceManager.set_offline("admin", user_id)
                if connections == 0:
                    await self.emit(
                        "presence:offline",
                        {"user_id": user_id, "user_type": "admin"},
                        room="admins",
                        skip_sid=sid,
                    )
            except Exception as e:
                logger.error(
                    "SIO /admin presence cleanup failed: sid={} user_id={} error={}",
                    sid, user_id, e,
                )

        # Clean up fallback mapping / 清理 fallback 映射
        self._sid_sessions.pop(sid, None)

        logger.info(
            "SIO /admin disconnected: sid={} user_id={} reason={}",
            sid, user_id, reason,
        )
