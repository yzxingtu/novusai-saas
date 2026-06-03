"""
平台管理端偏好设置 API / Platform Admin Preferences API

全局偏好管理（超级管理员）和个人偏好覆盖。
Global preference management (super admin) and individual preference overrides.
"""

from fastapi import APIRouter
from pydantic import BaseModel as PydanticBase

from app.core.deps import ActiveAdmin, DbSession, SuperAdmin
from app.core.i18n import _
from app.core.logging import LogManager
from app.core.response import success
from app.core.socketio_server import sio
from app.rbac.decorators import auth_only
from app.services.common.user_preference_service import (
    PLATFORM_TENANT_ID,
    SCOPE_ADMIN,
    SCOPE_PLATFORM_GLOBAL,
    SYSTEM_DEFAULTS,
    UserPreferenceService,
)

logger = LogManager.get_logger("app")

router = APIRouter(prefix="/preferences", tags=["偏好设置 / Preferences"])


class PreferenceUpdateSchema(PydanticBase):
    """偏好更新请求体 / Preference update request body"""

    preferences: dict


# ── 全局偏好 / Global preferences ──


@router.get("/global", summary="获取平台全局偏好 / Get platform global preferences")
@auth_only
async def get_global_preferences(
    db: DbSession,
    admin: SuperAdmin,
):
    """获取平台全局偏好设置（含系统默认补全） / Get platform global preferences with system defaults"""
    service = UserPreferenceService(db)
    data = await service.get_global_with_defaults(
        SCOPE_PLATFORM_GLOBAL, PLATFORM_TENANT_ID
    )
    return success(data=data)


@router.put("/global", summary="更新平台全局偏好 / Update platform global preferences")
@auth_only
async def update_global_preferences(
    db: DbSession,
    admin: SuperAdmin,
    body: PreferenceUpdateSchema,
):
    """
    更新平台全局偏好，变更的 key 会从所有管理员个人覆盖中清除 / Update platform global preferences; changed keys cleared from admin overrides.
    """
    service = UserPreferenceService(db)
    data, changed = await service.update_global(
        SCOPE_PLATFORM_GLOBAL, PLATFORM_TENANT_ID, body.preferences
    )
    await db.commit()

    if changed:
        await sio.emit(
            "preference:global_updated",
            {"preferences": changed},
            room="admins",
            namespace="/admin",
        )
        logger.info(
            "Emitted preference:global_updated to room=admins ({} keys)", len(changed)
        )

    return success(data=data, message=_("common.success"))


# ── 个人偏好 / Individual preferences ──


@router.get(
    "/me", summary="获取当前管理员生效偏好 / Get current admin effective preferences"
)
@auth_only
async def get_my_preferences(
    db: DbSession,
    admin: ActiveAdmin,
):
    """获取当前管理员合并后的生效偏好 / Get current admin's merged effective preferences"""
    service = UserPreferenceService(db)
    data = await service.get_effective(SCOPE_ADMIN, PLATFORM_TENANT_ID, admin.id)
    return success(data=data)


@router.put(
    "/me",
    summary="更新当前管理员个人偏好 / Update current admin individual preferences",
)
@auth_only
async def update_my_preferences(
    db: DbSession,
    admin: ActiveAdmin,
    body: PreferenceUpdateSchema,
):
    """更新当前管理员的个人偏好覆盖 / Update current admin's individual preference overrides"""
    service = UserPreferenceService(db)
    data = await service.update_individual(
        SCOPE_ADMIN, PLATFORM_TENANT_ID, admin.id, body.preferences
    )
    await db.commit()
    return success(data=data, message=_("common.success"))


@router.delete("/me", summary="重置当前管理员偏好 / Reset current admin preferences")
@auth_only
async def reset_my_preferences(
    db: DbSession,
    admin: ActiveAdmin,
):
    """重置当前管理员的个人偏好（恢复为全局默认） / Reset current admin preferences to global defaults"""
    service = UserPreferenceService(db)
    data = await service.reset_individual(SCOPE_ADMIN, PLATFORM_TENANT_ID, admin.id)
    await db.commit()
    return success(data=data, message=_("common.success"))


@router.get("/defaults", summary="获取系统默认偏好 / Get system default preferences")
@auth_only
async def get_defaults(
    admin: ActiveAdmin,
):
    """获取系统内置默认偏好值 / Get system built-in default preference values"""
    return success(data=SYSTEM_DEFAULTS)


__all__ = ["router"]
