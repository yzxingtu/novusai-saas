"""
平台管理端通知偏好 API / Platform Admin Notification Preferences API

管理员可设置各通知分类的渠道偏好（WS/收件箱/邮件）。
Admins can set channel preferences (WS/inbox/email) for each notification category.
"""

from fastapi import APIRouter

from app.core.deps import ActiveAdmin, DbSession
from app.core.i18n import _
from app.core.response import success
from app.rbac.decorators import auth_only
from app.services.common.notification_preference_service import (
    NotificationPreferenceService,
)

router = APIRouter(prefix="/notification-preferences", tags=["通知偏好"])


@router.get("", summary="获取通知偏好列表")
@auth_only
async def get_preferences(
    db: DbSession,
    admin: ActiveAdmin,
):
    """获取当前管理员的所有通知偏好设置 / Get all notification preference settings for current admin"""
    service = NotificationPreferenceService(db)
    prefs = await service.get_all_preferences("admin", admin.id)
    return success(data=prefs)


@router.put("", summary="保存通知偏好")
@auth_only
async def save_preferences(
    db: DbSession,
    admin: ActiveAdmin,
    data: list[dict],
):
    """批量保存管理员的通知偏好设置 / Batch save admin notification preference settings"""
    service = NotificationPreferenceService(db)
    await service.save_preferences("admin", admin.id, data)
    await db.commit()
    return success(message=_("common.success"))


__all__ = ["router"]
