"""
租户端通知偏好 API / Tenant Notification Preferences API

租户管理员可设置各通知分类的渠道偏好（WS/收件箱/邮件）。
Tenant admins can set channel preferences (WS/Inbox/Email) for each notification category.
"""

from fastapi import APIRouter

from app.core.deps import ActiveTenantAdmin, DbSession
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
    tenant_admin: ActiveTenantAdmin,
):
    """获取当前租户管理员的所有通知偏好设置 / Get all notification preference settings for current tenant admin"""
    service = NotificationPreferenceService(db)
    prefs = await service.get_all_preferences("tenant_admin", tenant_admin.id)
    return success(data=prefs)


@router.put("", summary="保存通知偏好")
@auth_only
async def save_preferences(
    db: DbSession,
    tenant_admin: ActiveTenantAdmin,
    data: list[dict],
):
    """批量保存租户管理员的通知偏好设置 / Batch save notification preference settings for tenant admin"""
    service = NotificationPreferenceService(db)
    await service.save_preferences("tenant_admin", tenant_admin.id, data)
    await db.commit()
    return success(message=_("common.success"))


__all__ = ["router"]
