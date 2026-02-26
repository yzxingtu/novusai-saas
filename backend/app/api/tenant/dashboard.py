"""
租户端仪表盘 API

提供租户 Dashboard 统计数据：用户总数、活跃用户、API 调用、资源使用
"""

from fastapi import APIRouter

from app.core.deps import DbSession, ActiveTenantAdmin
from app.core.response import success
from app.rbac.decorators import auth_only
from app.services.system.dashboard_service import TenantDashboardService


router = APIRouter(prefix="/dashboard", tags=["Dashboard (Tenant)"])


@router.get("/stats", summary="获取租户仪表盘统计数据")
@auth_only
async def get_tenant_dashboard_stats(
    db: DbSession,
    current_admin: ActiveTenantAdmin,
):
    """
    获取租户端仪表盘统计：
    - total_users: 租户下管理员总数
    - active_users: 活跃用户数（有登录记录）
    - api_calls: API 调用数（预留）
    - resource_usage: 资源使用（预留）
    """
    service = TenantDashboardService(db, current_admin.tenant_id)
    data = await service.get_stats()
    return success(data=data)


__all__ = ["router"]
