"""
通知偏好服务 / Notification Preference Service

管理用户的通知渠道偏好设置，支持全局默认 -> 个人覆盖的分层继承。
Manages user notification channel preferences with global default -> individual override layered inheritance.
"""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.configs.service import PLATFORM_TENANT_ID
from app.core.logging import LogManager
from app.models.common.notification_preference import NotificationPreference

logger = LogManager.get_logger("app")

CATEGORIES = ["system", "ai", "task", "biz", "audit"]

DEFAULT_PREF = {
    "channel_ws": True,
    "channel_inbox": True,
    "channel_email": False,
}

GLOBAL_TYPE_MAP = {
    "admin": "platform_global",
    "tenant_admin": "tenant_global",
}

INDIVIDUAL_TYPE_MAP = {
    "platform_global": "admin",
    "tenant_global": "tenant_admin",
}


class NotificationPreferenceService:
    """通知偏好 CRUD 服务（含全局继承） / Notification preference CRUD (with global inheritance)."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # 全局偏好 CRUD
    # ------------------------------------------------------------------

    async def get_global_preferences(
        self,
        global_user_type: str,
        tenant_id: int = PLATFORM_TENANT_ID,
    ) -> list[dict]:
        """
        获取全局通知偏好列表（缺失的 category 用硬编码默认补全）/ Get global notification preferences (fill missing with defaults).

        :param global_user_type: 'platform_global' | 'tenant_global'
        :param tenant_id: 租户 ID（平台级为 PLATFORM_TENANT_ID）
        """
        result = await self.db.execute(
            select(NotificationPreference).where(
                NotificationPreference.user_type == global_user_type,
                NotificationPreference.tenant_id == tenant_id,
                NotificationPreference.user_id.is_(None),
            )
        )
        existing = {p.category: p for p in result.scalars().all()}

        prefs = []
        for cat in CATEGORIES:
            if cat in existing:
                p = existing[cat]
                prefs.append(
                    {
                        "category": cat,
                        "channel_ws": p.channel_ws,
                        "channel_inbox": p.channel_inbox,
                        "channel_email": p.channel_email,
                    }
                )
            else:
                prefs.append({"category": cat, **DEFAULT_PREF})
        return prefs

    async def update_global_preferences(
        self,
        global_user_type: str,
        tenant_id: int,
        data: list[dict],
    ) -> None:
        """
        更新全局通知偏好 + 精确清除受影响的个人行 / Update global preferences and clear affected user overrides.

        :param global_user_type: 'platform_global' | 'tenant_global'
        :param tenant_id: 租户 ID
        :param data: [{category, channel_ws, channel_inbox, channel_email}, ...]
        """
        result = await self.db.execute(
            select(NotificationPreference).where(
                NotificationPreference.user_type == global_user_type,
                NotificationPreference.tenant_id == tenant_id,
                NotificationPreference.user_id.is_(None),
            )
        )
        existing = {p.category: p for p in result.scalars().all()}

        changed_categories: set[str] = set()

        for item in data:
            cat = item.get("category")
            if not cat or cat not in CATEGORIES:
                continue

            ws = item.get("channel_ws", True)
            inbox = item.get("channel_inbox", True)
            email = item.get("channel_email", False)

            old = existing.get(cat)
            has_change = (
                old is None
                or old.channel_ws != ws
                or old.channel_email != email
                or old.channel_inbox != inbox
            )

            if has_change:
                changed_categories.add(cat)

            if cat in existing:
                pref = existing[cat]
                pref.channel_ws = ws
                pref.channel_inbox = inbox
                pref.channel_email = email
            else:
                pref = NotificationPreference(
                    user_type=global_user_type,
                    tenant_id=tenant_id,
                    user_id=None,
                    category=cat,
                    channel_ws=ws,
                    channel_inbox=inbox,
                    channel_email=email,
                )
                self.db.add(pref)

        if changed_categories:
            ind_user_type = INDIVIDUAL_TYPE_MAP.get(global_user_type)
            if ind_user_type:
                await self.db.execute(
                    delete(NotificationPreference).where(
                        NotificationPreference.user_type == ind_user_type,
                        NotificationPreference.tenant_id == tenant_id,
                        NotificationPreference.category.in_(changed_categories),
                        NotificationPreference.user_id.isnot(None),
                    )
                )
                logger.info(
                    "Cleared individual notification prefs for changed categories: {} "
                    "(global_type={}, tenant_id={})",
                    changed_categories,
                    global_user_type,
                    tenant_id,
                )

    # ------------------------------------------------------------------
    # 个人偏好 CRUD（含全局回退）
    # ------------------------------------------------------------------

    async def get_all_preferences(
        self,
        user_type: str,
        user_id: int,
        tenant_id: int = PLATFORM_TENANT_ID,
    ) -> list[dict]:
        """
        获取用户所有分类的偏好设置（个人 -> 全局 -> 硬编码默认）/ Get user preferences per category (user -> global -> default).
        """
        ind_result = await self.db.execute(
            select(NotificationPreference).where(
                NotificationPreference.user_type == user_type,
                NotificationPreference.user_id == user_id,
                NotificationPreference.tenant_id == tenant_id,
            )
        )
        individual = {p.category: p for p in ind_result.scalars().all()}

        global_user_type = GLOBAL_TYPE_MAP.get(user_type)
        global_map: dict[str, NotificationPreference] = {}
        if global_user_type:
            gl_result = await self.db.execute(
                select(NotificationPreference).where(
                    NotificationPreference.user_type == global_user_type,
                    NotificationPreference.tenant_id == tenant_id,
                    NotificationPreference.user_id.is_(None),
                )
            )
            global_map = {p.category: p for p in gl_result.scalars().all()}

        prefs = []
        for cat in CATEGORIES:
            if cat in individual:
                p = individual[cat]
                prefs.append(
                    {
                        "category": cat,
                        "channel_ws": p.channel_ws,
                        "channel_inbox": p.channel_inbox,
                        "channel_email": p.channel_email,
                        "is_custom": True,
                    }
                )
            elif cat in global_map:
                p = global_map[cat]
                prefs.append(
                    {
                        "category": cat,
                        "channel_ws": p.channel_ws,
                        "channel_inbox": p.channel_inbox,
                        "channel_email": p.channel_email,
                        "is_custom": False,
                    }
                )
            else:
                prefs.append({"category": cat, **DEFAULT_PREF, "is_custom": False})

        return prefs

    async def save_preferences(
        self,
        user_type: str,
        user_id: int,
        data: list[dict],
        tenant_id: int = PLATFORM_TENANT_ID,
    ) -> None:
        """
        批量保存个人偏好设置（upsert 语义）/ Batch save user preferences (upsert).
        """
        result = await self.db.execute(
            select(NotificationPreference).where(
                NotificationPreference.user_type == user_type,
                NotificationPreference.user_id == user_id,
                NotificationPreference.tenant_id == tenant_id,
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
                    tenant_id=tenant_id,
                    category=cat,
                    channel_ws=item.get("channel_ws", True),
                    channel_inbox=item.get("channel_inbox", True),
                    channel_email=item.get("channel_email", False),
                )
                self.db.add(pref)

    async def reset_individual_preferences(
        self,
        user_type: str,
        user_id: int,
        tenant_id: int = PLATFORM_TENANT_ID,
    ) -> None:
        """
        清除个人通知偏好（恢复为全局默认）/ Clear user notification preferences (restore to global default).
        """
        await self.db.execute(
            delete(NotificationPreference).where(
                NotificationPreference.user_type == user_type,
                NotificationPreference.user_id == user_id,
                NotificationPreference.tenant_id == tenant_id,
            )
        )


__all__ = ["NotificationPreferenceService"]
