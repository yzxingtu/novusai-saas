"""
Webhook 通知渠道（预留骨架） / Webhook Notification Channel (skeleton)

用于对接企业微信、钉钉、Slack 等外部 Webhook 通知。
For integrating with WeCom, DingTalk, Slack and other external Webhook notifications.
当前为空实现，is_enabled() 返回 False。
后续启用时需：
1. 添加系统配置项 webhook_enabled / webhook_url
2. 实现 deliver() 中的 HTTP POST 逻辑
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import LogManager
from app.services.common.channels.base import NotificationChannel

logger = LogManager.get_logger("app")


class WebhookChannel(NotificationChannel):
    """Webhook 渠道 — 企业微信/钉钉/Slack 等（预留） / Webhook channel — WeCom/DingTalk/Slack (reserved)."""

    @property
    def channel_code(self) -> str:
        return "webhook"

    @property
    def channel_name(self) -> str:
        return "Webhook"

    async def is_enabled(self) -> bool:
        """预留渠道，默认关闭 / Reserved channel, disabled by default."""
        return False

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
        """预留：后续实现 HTTP POST 到配置的 Webhook URL / Reserved: HTTP POST to configured webhook URL."""
        _ = (
            db,
            user_type,
            user_id,
            title,
            body,
            data,
            link,
            priority,
            template_code,
            tenant_id,
            kwargs,
        )
        logger.debug("WebhookChannel: not implemented, skip")
        return False


__all__ = ["WebhookChannel"]
