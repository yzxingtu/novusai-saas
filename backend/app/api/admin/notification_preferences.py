"""
平台管理端通知偏好 API / Platform Admin Notification Preferences API

管理员可设置各通知分类的渠道偏好（WS/收件箱/邮件）。
全局偏好管理（超级管理员）和个人偏好覆盖。
"""

from fastapi import APIRouter

from app.configs.service import PLATFORM_TENANT_ID

from app.core.deps import ActiveAdmin, DbSession, SuperAdmin
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


@router.get("/global", summary="获取平台全局通知偏好")
@auth_only
async def get_global_preferences(
    db: DbSession,
    admin: SuperAdmin,
):
    """获取平台全局通知偏好设置 / Get platform global notification preferences"""
    service = NotificationPreferenceService(db)
    prefs = await service.get_global_preferences("platform_global", tenant_id=PLATFORM_TENANT_ID)
    return success(data=prefs)


@router.put("/global", summary="更新平台全局通知偏好")
@auth_only
async def update_global_preferences(
    db: DbSession,
    admin: SuperAdmin,
    data: list[dict],
):
    """
    更新平台全局通知偏好，变更的分类会从所有管理员个人覆盖中清除 / Update platform global notification preferences; changed categories cleared from admin overrides.
    """
    service = NotificationPreferenceService(db)
    await service.update_global_preferences("platform_global", tenant_id=PLATFORM_TENANT_ID, data=data)
    await db.commit()

    await sio.emit(
        "notification_preference:global_updated",
        {},
        room="admins",
        namespace="/admin",
    )
    logger.info("Emitted notification_preference:global_updated to room=admins")

    return success(message=_("common.success"))


# ── 个人偏好 / Individual preferences ──


@router.get("", summary="获取通知偏好列表")
@auth_only
async def get_preferences(
    db: DbSession,
    admin: ActiveAdmin,
):
    """获取当前管理员的所有通知偏好设置（含全局回退） / Get all notification preferences for current admin"""
    service = NotificationPreferenceService(db)
    prefs = await service.get_all_preferences("admin", admin.id, tenant_id=PLATFORM_TENANT_ID)
    return success(data=prefs)


@router.put("", summary="保存通知偏好")
@auth_only
async def save_preferences(
    db: DbSession,
    admin: ActiveAdmin,
    data: list[dict],
):
    """批量保存管理员的通知偏好设置 / Batch save admin notification preferences"""
    service = NotificationPreferenceService(db)
    await service.save_preferences("admin", admin.id, data, tenant_id=PLATFORM_TENANT_ID)
    await db.commit()
    return success(message=_("common.success"))


@router.delete("", summary="重置通知偏好")
@auth_only
async def reset_preferences(
    db: DbSession,
    admin: ActiveAdmin,
):
    """重置管理员通知偏好（恢复为全局默认） / Reset admin notification preferences to global defaults"""
    service = NotificationPreferenceService(db)
    await service.reset_individual_preferences("admin", admin.id, tenant_id=PLATFORM_TENANT_ID)
    await db.commit()
    return success(message=_("common.success"))


__all__ = ["router"]
