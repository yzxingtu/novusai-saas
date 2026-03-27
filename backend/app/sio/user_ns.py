"""
Socket.IO /user Namespace

Tenant business user real-time communication namespace.
Handles connection auth, room management, and online status broadcast.
企业业务用户实时通信 namespace。
处理连接认证、房间管理、在线状态广播。
"""

import uuid

import socketio
from socketio.exceptions import ConnectionRefusedError as SocketConnectionRefusedError

from app.core.logging import LogManager
from app.core.security import (
    TOKEN_SCOPE_TENANT_USER,
    TokenExpiredError,
    verify_token_with_scope,
)
from app.middleware.trace import trace_id_var
from app.sio.error_utils import socket_connect_refusal
from app.sio.page_session import PageSessionMixin

logger = LogManager.get_logger("app")


class UserNamespace(PageSessionMixin, socketio.AsyncNamespace):
    """
    /user namespace — Tenant business users / 企业业务用户

    Rooms:
    - user:{user_id} — All devices of specified user / 指定用户的所有设备
    - tenant:{tenant_id} — All online business users of this tenant / 该企业的所有在线业务用户
    - page_session:{id} — Page operation targeting (dynamic join) / 页面操作定位（动态加入）
    """

    # sid → session backup, prevents inability to clean up presence when get_session fails / sid → session 备份，防止 get_session 失败时无法清理 presence
    _sid_sessions: dict[str, dict] = {}

    async def on_connect(self, sid: str, environ: dict, auth: dict | None = None) -> None:
        """
        连接认证 / Connection authentication.

        Extracts JWT from auth.token, verifies scope=tenant_user.
        Queries TenantUser from DB to get tenant_id.
        从 auth.token 提取 JWT，验证 scope=tenant_user。
        从 DB 查询 TenantUser 获取 tenant_id。
        """
        await self.bind_socket_trace(sid, auth, default_trace_id=str(uuid.uuid4()))
        try:
            _ = environ
            # Check real-time communication master switch / 检查实时通信总开关
            from app.sio.ws_config import get_ws_configs
            ws_cfg = await get_ws_configs("ws_enabled", "ws_max_connections_per_user")
            if not ws_cfg.get("ws_enabled", True):
                raise socket_connect_refusal("websocket_disabled")

            if not auth or not auth.get("token"):
                raise socket_connect_refusal("token_required")

            token = str(auth["token"]).removeprefix("Bearer ").strip()
            if not token:
                raise socket_connect_refusal("token_required")

            try:
                user_id_str, scope = await verify_token_with_scope(
                    token, TOKEN_SCOPE_TENANT_USER, raise_on_expired=True,
                )
            except TokenExpiredError as exc:
                raise socket_connect_refusal("token_expired") from exc

            if not user_id_str:
                raise socket_connect_refusal("authentication_failed")

            user_id = int(user_id_str)

            # Connection rate limiting / 连接频率限制
            from app.sio.presence import check_connect_rate
            if not await check_connect_rate("tenant_user", user_id):
                raise socket_connect_refusal("rate_limited")

            # Per-user max connection limit / 单用户最大连接数限制
            from app.sio.presence import PresenceManager
            max_conn = int(ws_cfg.get("ws_max_connections_per_user", 5))
            current_conn = await PresenceManager.get_user_connection_count("tenant_user", user_id)
            if current_conn >= max_conn:
                raise socket_connect_refusal("max_connections_exceeded")

            # Query tenant user to get tenant_id / 查询企业用户获取 tenant_id
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
                    raise socket_connect_refusal("account_not_found")
                # Extract needed values within session to avoid DetachedInstanceError / 在 session 内提取所需值，避免 DetachedInstanceError
                tenant_id = tenant_user.tenant_id
                username = tenant_user.username

            # Save session / 保存 session
            session_data = {
                "user_id": user_id,
                "user_type": "tenant_user",
                "tenant_id": tenant_id,
                "username": username,
                "trace_id": trace_id_var.get(),
            }
            await self.save_session(sid, session_data)
            self._sid_sessions[sid] = session_data

            # Join rooms / 加入 rooms
            await self.enter_room(sid, f"user:{user_id}")
            await self.enter_room(sid, f"tenant:{tenant_id}")

            # Update online status / 更新在线状态
            connections = await PresenceManager.set_online("tenant_user", user_id, tenant_id)

            if connections == 1:
                await self.emit(
                    "presence:online",
                    {"user_id": user_id, "user_type": "tenant_user", "tenant_id": tenant_id},
                    room=f"tenant:{tenant_id}",
                    skip_sid=sid,
                )
                # Notify /tenant namespace so tenant admins see business user online / 通知 /tenant namespace，让企业管理员看到业务用户上线
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
                "SIO /user connected: sid={} user_id={} tenant_id={} username={} connections={}",
                sid, user_id, tenant_id, username, connections,
            )
        except SocketConnectionRefusedError:
            raise
        except Exception as exc:
            logger.error("SIO /user connect failed: sid={} error={}", sid, exc, exc_info=True)
            raise socket_connect_refusal("connection_failed", exc=exc) from exc
        finally:
            trace_id_var.set("")

    async def on_disconnect(self, sid: str, reason: str = "") -> None:
        """Disconnect, update online status / 断开连接，更新在线状态"""
        session = await self.bind_socket_trace(sid, default_trace_id=str(uuid.uuid4()))
        try:
            self.cleanup_page_sessions_for_disconnect(sid)
            user_id = None
            tenant_id = None
            if session:
                user_id = session.get("user_id")
                tenant_id = session.get("tenant_id")

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
                        # Notify /tenant namespace so tenant admins see business user offline / 通知 /tenant namespace，让企业管理员看到业务用户下线
                        from app.core.socketio_server import get_sio
                        await get_sio().emit(
                            "user_presence:offline",
                            {"user_id": user_id, "user_type": "tenant_user", "tenant_id": tenant_id},
                            room=f"tenant:{tenant_id}",
                            namespace="/tenant",
                        )
                except Exception as e:
                    logger.error(
                        "SIO /user presence cleanup failed: sid={} user_id={} error={}",
                        sid, user_id, e,
                    )

            # Clean up fallback mapping / 清理 fallback 映射
            self._sid_sessions.pop(sid, None)

            logger.info(
                "SIO /user disconnected: sid={} user_id={} tenant_id={} reason={}",
                sid, user_id, tenant_id, reason,
            )
        finally:
            trace_id_var.set("")
