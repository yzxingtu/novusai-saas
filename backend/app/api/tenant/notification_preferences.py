"""
企业端通知偏好 API / Tenant Notification Preferences API

企业管理员可设置各通知分类的渠道偏好（WS/收件箱/邮件）。
全局偏好管理（企业所有者）和个人偏好覆盖。
"""

from fastapi import APIRouter

from app.core.deps import ActiveTenantAdmin, DbSession, TenantOwner
from app.core.i18n import _
from app.core.logging import LogManager
from app.core.response import success
from app.core.socketio_server import sio
from app.rbac.decorators import auth_only
from app.services.common.notification_preference_service import (
    NotificationPreferenceService,
)

logger = LogManager.get_logger("app")

router = APIRouter(prefix="/notification-preferences", tags=["通知偏好"])


# ── 全局偏好 / Global preferences ──


@router.get("/global", summary="获取企业全局通知偏好")
@auth_only
async def get_global_preferences(
    db: DbSession,
    tenant_admin: TenantOwner,
):
    """获取企业全局通知偏好设置 / Get tenant global notification preferences"""
    service = NotificationPreferenceService(db)
    prefs = await service.get_global_preferences("tenant_global", tenant_id=tenant_admin.tenant_id)
    return success(data=prefs)


@router.put("/global", summary="更新企业全局通知偏好")
@auth_only
async def update_global_preferences(
    db: DbSession,
    tenant_admin: TenantOwner,
    data: list[dict],
):
    """
    更新企业全局通知偏好，变更的分类会从该企业所有管理员的个人覆盖中清除
    Update tenant global notification preferences; changed categories are cleared from all tenant admin overrides
    """
    service = NotificationPreferenceService(db)
    await service.update_global_preferences(
        "tenant_global", tenant_id=tenant_admin.tenant_id, data=data,
    )
    await db.commit()

    room = f"tenant:{tenant_admin.tenant_id}"
    await sio.emit(
        "notification_preference:global_updated",
        {},
        room=room,
        namespace="/tenant",
    )
    logger.info("Emitted notification_preference:global_updated to room=%s", room)

    return success(message=_("common.success"))


# ── 个人偏好 / Individual preferences ──


@router.get("", summary="获取通知偏好列表")
@auth_only
async def get_preferences(
    db: DbSession,
    tenant_admin: ActiveTenantAdmin,
):
    """获取当前企业管理员的所有通知偏好设置（含全局回退） / Get all notification preferences for current tenant admin"""
    service = NotificationPreferenceService(db)
    prefs = await service.get_all_preferences("tenant_admin", tenant_admin.id, tenant_id=tenant_admin.tenant_id)
    return success(data=prefs)


@router.put("", summary="保存通知偏好")
@auth_only
async def save_preferences(
    db: DbSession,
    tenant_admin: ActiveTenantAdmin,
    data: list[dict],
):
    """批量保存企业管理员的通知偏好设置 / Batch save notification preferences for tenant admin"""
    service = NotificationPreferenceService(db)
    await service.save_preferences("tenant_admin", tenant_admin.id, data, tenant_id=tenant_admin.tenant_id)
    await db.commit()
    return success(message=_("common.success"))


@router.delete("", summary="重置通知偏好")
@auth_only
async def reset_preferences(
    db: DbSession,
    tenant_admin: ActiveTenantAdmin,
):
    """重置企业管理员通知偏好（恢复为全局默认） / Reset tenant admin notification preferences to global defaults"""
    service = NotificationPreferenceService(db)
    await service.reset_individual_preferences("tenant_admin", tenant_admin.id, tenant_id=tenant_admin.tenant_id)
    await db.commit()
    return success(message=_("common.success"))


__all__ = ["router"]
