"""
收件箱通知渠道 / Inbox Notification Channel

将通知写入 notifications 表，用户可在通知面板中查看。
Writes notifications to the notifications table for viewing in the notification panel.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import LogManager
from app.services.common.channels.base import NotificationChannel

logger = LogManager.get_logger("app")


class InboxChannel(NotificationChannel):
    """收件箱渠道 — 写入 DB notifications 表 / Inbox channel — writes to DB notifications table."""

    @property
    def channel_code(self) -> str:
        return "inbox"

    @property
    def channel_name(self) -> str:
        return "Inbox"

    async def is_enabled(self) -> bool:
        """收件箱跟随通知系统总开关 / Inbox follows notification system master switch."""
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
        _ = kwargs
        try:
            from app.models.common.notification import Notification

            notification = Notification(
                tenant_id=tenant_id,
                recipient_type=user_type,
                recipient_id=user_id,
                template_code=template_code,
                category=template_code.split(".")[0] if "." in template_code else "system",
                title=title,
                body=body,
                data=data,
                link=link,
                priority=priority,
            )
            db.add(notification)
            return True
        except Exception as e:
            logger.warning("InboxChannel deliver failed: {}", str(e))
            return False


__all__ = ["InboxChannel"]
