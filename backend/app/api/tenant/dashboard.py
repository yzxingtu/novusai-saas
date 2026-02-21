"""
租户端仪表盘 API

提供租户 Dashboard 统计数据：用户总数、活跃用户、API 调用、资源使用
"""

from datetime import datetime, timezone

from fastapi import APIRouter
from sqlalchemy import func, select

from app.core.deps import DbSession, ActiveTenantAdmin
from app.core.response import success
from app.models.tenant.tenant_admin import TenantAdmin
from app.rbac.decorators import auth_only


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
    tenant_id = current_admin.tenant_id

    # 租户下管理员总数
    total_users_q = select(func.count()).select_from(TenantAdmin).where(
        TenantAdmin.deleted_at.is_(None),
        TenantAdmin.tenant_id == tenant_id,
    )
    total_users = (await db.execute(total_users_q)).scalar() or 0

    # 活跃用户（最近 30 天有登录）
    thirty_days_ago = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    from datetime import timedelta
    thirty_days_ago = thirty_days_ago - timedelta(days=30)

    active_users_q = select(func.count()).select_from(TenantAdmin).where(
        TenantAdmin.deleted_at.is_(None),
        TenantAdmin.tenant_id == tenant_id,
        TenantAdmin.last_login_at >= thirty_days_ago,
    )
    active_users = (await db.execute(active_users_q)).scalar() or 0

    return success(data={
        "total_users": total_users,
        "active_users": active_users,
        "api_calls": 0,
        "resource_usage": 0,
    })


__all__ = ["router"]
