"""
企业用户身份辅助 API（平台端） / Tenant user identity helper API (Admin).

提供平台端跨企业的人物身份详情与远程选择辅助能力。
Provides admin-side cross-tenant identity detail and select helpers.
"""

from fastapi import APIRouter, Query

from app.api.common.identity import serialize_tenant_user_identity_detail
from app.core.deps import ActiveAdmin, DbSession
from app.core.i18n import _
from app.core.response import success
from app.rbac.decorators import auth_only
from app.services.tenant.tenant_user_service import TenantUserService

router = APIRouter(prefix="/tenants/{tenant_id}/users", tags=["Tenant User Identity"])


@router.get("/select", summary="获取企业用户下拉选项")
@auth_only
async def select_tenant_users(
    db: DbSession,
    current_admin: ActiveAdmin,
    tenant_id: int,
    search: str = Query("", description=_("api.param.search")),
    page: int = Query(1, ge=1, description=_("api.param.page")),
    page_size: int = Query(20, ge=1, le=100, description=_("api.param.page_size")),
):
    """
    获取指定企业的企业用户分页下拉选项 / Get paginated tenant-user select options.
    """
    _current_admin = current_admin
    response = await TenantUserService(
        db,
        tenant_id,
    ).get_identity_select_options(
        search=search,
        page=page,
        page_size=page_size,
    )
    return success(data=response, message=_("common.success"))


@router.get("/{user_id}", summary="获取企业用户详情")
@auth_only
async def get_tenant_user_detail(
    db: DbSession,
    current_admin: ActiveAdmin,
    tenant_id: int,
    user_id: int,
):
    """
    获取指定企业的企业用户身份详情 / Get tenant user identity detail.
    """
    _current_admin = current_admin
    user = await TenantUserService(db, tenant_id).get_identity_detail(user_id)
    return success(
        data=serialize_tenant_user_identity_detail(user),
        message=_("common.success"),
    )


__all__ = ["router"]
