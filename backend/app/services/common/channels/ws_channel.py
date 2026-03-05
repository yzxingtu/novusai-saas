"""
WebSocket 实时推送通知渠道

通过 Socket.IO 实时推送通知到已连接的客户端。
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import LogManager
from app.services.common.channels.base import NotificationChannel

logger = LogManager.get_logger("app")


class WSChannel(NotificationChannel):
    """WebSocket 渠道 — Socket.IO 实时推送"""

    @property
    def channel_code(self) -> str:
        return "ws"

    @property
    def channel_name(self) -> str:
        return "WebSocket"

    async def is_enabled(self) -> bool:
        """WS 跟随通知系统总开关"""
        try:
            from app.sio.ws_config import get_ws_config
            return bool(await get_ws_config("notification_enabled"))
        except Exception:
            return True

    async def deliver(
        self,
        db: AsyncSession,
        user_type: str,
        user_id: int,
        title: str,
        body: str | None,
        data: dict[str, Any] | None,
        link: str | None,
        priority: str,
        template_code: str,
        tenant_id: int | None = None,
        **kwargs: Any,
    ) -> bool:
        _ = (db, tenant_id, kwargs)
        try:
            from app.core.socketio_server import sio

            ns_map = {
                "admin": "/admin",
                "tenant_admin": "/tenant",
                "tenant_user": "/user",
            }
            namespace = ns_map.get(user_type, "/admin")

            category = template_code.split(".")[0] if "." in template_code else "system"

            await sio.emit(
                "notification",
                {
                    "type": template_code,
                    "category": category,
                    "title": title,
                    "body": body,
                    "data": data,
                    "link": link,
                    "priority": priority,
                },
                room=f"user:{user_id}",
                namespace=namespace,
            )
            return True
        except Exception as e:
            logger.warning("WSChannel deliver failed: %s", str(e))
            return False


__all__ = ["WSChannel"]
