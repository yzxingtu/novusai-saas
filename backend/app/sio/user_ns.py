"""
Socket.IO /user Namespace

租户业务用户实时通信 namespace。
处理连接认证、房间管理、在线状态广播。
"""

import socketio

from app.core.logging import LogManager
from app.core.security import (
    TOKEN_SCOPE_TENANT_USER,
    TokenExpiredError,
    verify_token_with_scope,
)
from app.sio.page_session import PageSessionMixin

logger = LogManager.get_logger("app")


class UserNamespace(PageSessionMixin, socketio.AsyncNamespace):
    """
    /user namespace — 租户业务用户

    Rooms:
    - user:{user_id} — 指定用户的所有设备
    - tenant:{tenant_id} — 该租户的所有在线业务用户
    - page_session:{id} — 页面操作定位（动态加入）
    """

    # sid → session 备份，防止 get_session 失败时无法清理 presence
    _sid_sessions: dict[str, dict] = {}

    async def on_connect(self, sid: str, environ: dict, auth: dict | None = None) -> None:
        """
        连接认证

        从 auth.token 提取 JWT，验证 scope=tenant_user。
        从 DB 查询 TenantUser 获取 tenant_id。
        """
        _ = environ
        # 检查实时通信总开关
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
            user_id_str, scope = verify_token_with_scope(
                token, TOKEN_SCOPE_TENANT_USER, raise_on_expired=True,
            )
        except TokenExpiredError:
            raise ConnectionRefusedError("token_expired")

        if not user_id_str:
            raise ConnectionRefusedError("authentication_failed")

        user_id = int(user_id_str)

        # 连接频率限制
        from app.sio.presence import check_connect_rate
        if not await check_connect_rate("tenant_user", user_id):
            raise ConnectionRefusedError("rate_limited")

        # 单用户最大连接数限制
        from app.sio.presence import PresenceManager
        max_conn = int(ws_cfg.get("ws_max_connections_per_user", 5))
        current_conn = await PresenceManager.get_user_connection_count("tenant_user", user_id)
        if current_conn >= max_conn:
            raise ConnectionRefusedError("max_connections_exceeded")

        # 查询租户用户获取 tenant_id
        from sqlalchemy import select

        from app.core.database import async_session_factory
        from app.models import TenantUser

        async with async_session_factory() as db:
            result = await db.execute(
                select(TenantUser).where(
                    TenantUser.id == user_id,
                    TenantUser.is_deleted.is_(False),
                    TenantUser.is_active.is_(True),
                )
            )
            tenant_user = result.scalar_one_or_none()
            if not tenant_user:
                raise ConnectionRefusedError("account_not_found")
            # 在 session 内提取所需值，避免 DetachedInstanceError
            tenant_id = tenant_user.tenant_id
            username = tenant_user.username

        # 保存 session
        session_data = {
            "user_id": user_id,
            "user_type": "tenant_user",
            "tenant_id": tenant_id,
            "username": username,
        }
        await self.save_session(sid, session_data)
        self._sid_sessions[sid] = session_data

        # 加入 rooms
        await self.enter_room(sid, f"user:{user_id}")
        await self.enter_room(sid, f"tenant:{tenant_id}")

        # 更新在线状态
        connections = await PresenceManager.set_online("tenant_user", user_id, tenant_id)

        if connections == 1:
            await self.emit(
                "presence:online",
                {"user_id": user_id, "user_type": "tenant_user", "tenant_id": tenant_id},
                room=f"tenant:{tenant_id}",
                skip_sid=sid,
            )
            # 通知 /tenant namespace，让租户管理员看到业务用户上线
            from app.core.socketio_server import get_sio
            await get_sio().emit(
                "user_presence:online",
                {"user_id": user_id, "user_type": "tenant_user", "tenant_id": tenant_id},
                room=f"tenant:{tenant_id}",
                namespace="/tenant",
            )

        online_ids = await PresenceManager.get_online_ids("tenant_user", tenant_id)
        await self.emit("presence:list", {"online_ids": online_ids}, to=sid)

        logger.info(
            "SIO /user connected: sid=%s user_id=%d tenant_id=%d username=%s connections=%d",
            sid, user_id, tenant_id, username, connections,
        )

    async def on_disconnect(self, sid: str, reason: str = "") -> None:
        """断开连接，更新在线状态"""
        user_id = None
        tenant_id = None
        try:
            session = await self.get_session(sid)
            user_id = session.get("user_id")
            tenant_id = session.get("tenant_id")
        except Exception as e:
            logger.warning(
                "SIO /user get_session failed on disconnect: sid=%s error=%s",
                sid, e,
            )
            # fallback: 从备份映射获取
            fallback = self._sid_sessions.get(sid)
            if fallback:
                user_id = fallback.get("user_id")
                tenant_id = fallback.get("tenant_id")
                logger.info("SIO /user using fallback session for sid=%s user_id=%s", sid, user_id)

        if user_id and tenant_id:
            try:
                from app.sio.presence import PresenceManager
                connections = await PresenceManager.set_offline("tenant_user", user_id, tenant_id)
                if connections == 0:
                    await self.emit(
                        "presence:offline",
                        {"user_id": user_id, "user_type": "tenant_user", "tenant_id": tenant_id},
                        room=f"tenant:{tenant_id}",
                        skip_sid=sid,
                    )
                    # 通知 /tenant namespace，让租户管理员看到业务用户下线
                    from app.core.socketio_server import get_sio
                    await get_sio().emit(
                        "user_presence:offline",
                        {"user_id": user_id, "user_type": "tenant_user", "tenant_id": tenant_id},
                        room=f"tenant:{tenant_id}",
                        namespace="/tenant",
                    )
            except Exception as e:
                logger.error(
                    "SIO /user presence cleanup failed: sid=%s user_id=%s error=%s",
                    sid, user_id, e,
                )

        # 清理 fallback 映射
        self._sid_sessions.pop(sid, None)

        logger.info(
            "SIO /user disconnected: sid=%s user_id=%s tenant_id=%s reason=%s",
            sid, user_id, tenant_id, reason,
        )
