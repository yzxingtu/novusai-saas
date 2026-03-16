"""
企业端偏好设置 API / Tenant Preferences API

企业全局偏好管理（企业所有者）和企业管理员个人偏好覆盖。
Tenant global preference management (tenant owner) and tenant admin individual preference overrides.
"""

from fastapi import APIRouter
from pydantic import BaseModel as PydanticBase

from app.core.deps import ActiveTenantAdmin, DbSession, TenantOwner
from app.core.i18n import _
from app.core.logging import LogManager
from app.core.response import success
from app.core.socketio_server import sio
from app.rbac.decorators import auth_only
from app.services.common.user_preference_service import (
    SCOPE_TENANT_ADMIN,
    SCOPE_TENANT_GLOBAL,
    SYSTEM_DEFAULTS,
    UserPreferenceService,
)

logger = LogManager.get_logger("app")

router = APIRouter(prefix="/preferences", tags=["偏好设置 / Preferences"])


class PreferenceUpdateSchema(PydanticBase):
    """偏好更新请求体 / Preference update request body"""
    preferences: dict


# ── 全局偏好 / Global preferences ──


@router.get("/global", summary="获取企业全局偏好 / Get tenant global preferences")
@auth_only
async def get_global_preferences(
    db: DbSession,
    tenant_admin: TenantOwner,
):
    """获取企业全局偏好设置（含系统默认补全） / Get tenant global preferences with system defaults"""
    service = UserPreferenceService(db)
    data = await service.get_global_with_defaults(SCOPE_TENANT_GLOBAL, tenant_admin.tenant_id)
    return success(data=data)


@router.put("/global", summary="更新企业全局偏好 / Update tenant global preferences")
@auth_only
async def update_global_preferences(
    db: DbSession,
    tenant_admin: TenantOwner,
    body: PreferenceUpdateSchema,
):
    """
    更新企业全局偏好，变更的 key 会从该企业所有管理员的个人覆盖中清除 / Update tenant global preferences; changed keys cleared from tenant admin overrides.
    """
    service = UserPreferenceService(db)
    data, changed = await service.update_global(SCOPE_TENANT_GLOBAL, tenant_admin.tenant_id, body.preferences)
    await db.commit()

    if changed:
        room = f"tenant:{tenant_admin.tenant_id}"
        await sio.emit(
            "preference:global_updated",
            {"preferences": changed},
            room=room,
            namespace="/tenant",
        )
        logger.info(
            "Emitted preference:global_updated to room={} ({} keys)",
            room,
            len(changed),
        )

    return success(data=data, message=_("common.success"))


# ── 个人偏好 / Individual preferences ──


@router.get("/me", summary="获取当前企业管理员生效偏好 / Get current tenant admin effective preferences")
@auth_only
async def get_my_preferences(
    db: DbSession,
    tenant_admin: ActiveTenantAdmin,
):
    """获取当前企业管理员合并后的生效偏好 / Get current tenant admin's merged effective preferences"""
    service = UserPreferenceService(db)
    data = await service.get_effective(SCOPE_TENANT_ADMIN, tenant_admin.tenant_id, tenant_admin.id)
    return success(data=data)


@router.put("/me", summary="更新当前企业管理员个人偏好 / Update current tenant admin individual preferences")
@auth_only
async def update_my_preferences(
    db: DbSession,
    tenant_admin: ActiveTenantAdmin,
    body: PreferenceUpdateSchema,
):
    """更新当前企业管理员的个人偏好覆盖 / Update current tenant admin's individual preference overrides"""
    service = UserPreferenceService(db)
    data = await service.update_individual(
        SCOPE_TENANT_ADMIN, tenant_admin.tenant_id, tenant_admin.id, body.preferences,
    )
    await db.commit()
    return success(data=data, message=_("common.success"))


@router.delete("/me", summary="重置当前企业管理员偏好 / Reset current tenant admin preferences")
@auth_only
async def reset_my_preferences(
    db: DbSession,
    tenant_admin: ActiveTenantAdmin,
):
    """重置当前企业管理员的个人偏好（恢复为全局默认） / Reset current tenant admin preferences to global defaults"""
    service = UserPreferenceService(db)
    data = await service.reset_individual(SCOPE_TENANT_ADMIN, tenant_admin.tenant_id, tenant_admin.id)
    await db.commit()
    return success(data=data, message=_("common.success"))


@router.get("/defaults", summary="获取系统默认偏好 / Get system default preferences")
@auth_only
async def get_defaults(
    tenant_admin: ActiveTenantAdmin,
):
    """获取系统内置默认偏好值 / Get system built-in default preference values"""
    return success(data=SYSTEM_DEFAULTS)


__all__ = ["router"]
