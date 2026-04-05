"""
企业管理员身份选择 API（企业端） / Tenant admin identity select API.

提供企业管理员远程选择器接口
Provides tenant admin remote identity select endpoint.
"""

from fastapi import APIRouter, Query

from app.core.deps import ActiveTenantAdmin, DbSession
from app.core.i18n import _
from app.core.response import success
from app.api.common.identity import serialize_tenant_admin_identity_detail
from app.rbac.decorators import auth_only
from app.services.tenant.tenant_admin_service import TenantAdminService

router = APIRouter(prefix="/admins", tags=["Tenant Admin Identity"])


@router.get("/select", summary="获取企业管理员下拉选项")
@auth_only
async def select_tenant_admins(
    db: DbSession,
    current_admin: ActiveTenantAdmin,
    search: str = Query("", description=_("api.param.search")),
    page: int = Query(1, ge=1, description=_("api.param.page")),
    page_size: int = Query(20, ge=1, le=100, description=_("api.param.page_size")),
):
    """
    获取企业管理员分页下拉选项 / Get paginated tenant admin select options.
    """
    response = await TenantAdminService(
        db,
        current_admin.tenant_id,
    ).get_identity_select_options(
        search=search,
        page=page,
        page_size=page_size,
    )
    return success(data=response, message=_("common.success"))


@router.get("/{admin_id}", summary="获取企业管理员详情")
@auth_only
async def get_tenant_admin_detail(
    db: DbSession,
    current_admin: ActiveTenantAdmin,
    admin_id: int,
):
    """
    获取企业管理员详情 / Get tenant admin identity detail.
    """
    admin = await TenantAdminService(
        db,
        current_admin.tenant_id,
    ).get_identity_detail(admin_id)
    return success(
        data=serialize_tenant_admin_identity_detail(admin),
        message=_("common.success"),
    )


__all__ = ["router"]
