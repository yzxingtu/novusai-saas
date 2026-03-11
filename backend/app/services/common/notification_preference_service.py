"""
通知偏好服务 / Notification Preference Service

管理用户的通知渠道偏好设置（CRUD）。自动补全缺失分类的默认值。
Manages user notification channel preferences (CRUD). Auto-fills missing categories with defaults.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import LogManager
from app.models.common.notification_preference import NotificationPreference

logger = LogManager.get_logger("app")

CATEGORIES = ["system", "ai", "task", "biz", "audit"]

DEFAULT_PREF = {
    "channel_ws": True,
    "channel_inbox": True,
    "channel_email": False,
}


class NotificationPreferenceService:
    """通知偏好 CRUD 服务"""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_all_preferences(
        self,
        user_type: str,
        user_id: int,
    ) -> list[dict]:
        """
        获取用户所有分类的偏好设置

        自动补全缺失分类的默认值。
        """
        result = await self.db.execute(
            select(NotificationPreference).where(
                NotificationPreference.user_type == user_type,
                NotificationPreference.user_id == user_id,
            )
        )
        existing = {p.category: p for p in result.scalars().all()}

        prefs = []
        for cat in CATEGORIES:
            if cat in existing:
                p = existing[cat]
                prefs.append({
                    "category": cat,
                    "channel_ws": p.channel_ws,
                    "channel_inbox": p.channel_inbox,
                    "channel_email": p.channel_email,
                })
            else:
                prefs.append({"category": cat, **DEFAULT_PREF})

        return prefs

    async def save_preferences(
        self,
        user_type: str,
        user_id: int,
        data: list[dict],
    ) -> None:
        """
        批量保存偏好设置（upsert 语义）
        """
        result = await self.db.execute(
            select(NotificationPreference).where(
                NotificationPreference.user_type == user_type,
                NotificationPreference.user_id == user_id,
            )
        )
        existing = {p.category: p for p in result.scalars().all()}

        for item in data:
            cat = item.get("category")
            if not cat or cat not in CATEGORIES:
                continue

            if cat in existing:
                pref = existing[cat]
                pref.channel_ws = item.get("channel_ws", True)
                pref.channel_inbox = item.get("channel_inbox", True)
                pref.channel_email = item.get("channel_email", False)
            else:
                pref = NotificationPreference(
                    user_type=user_type,
                    user_id=user_id,
                    category=cat,
                    channel_ws=item.get("channel_ws", True),
                    channel_inbox=item.get("channel_inbox", True),
                    channel_email=item.get("channel_email", False),
                )
                self.db.add(pref)


__all__ = ["NotificationPreferenceService"]
