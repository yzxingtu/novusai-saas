"""
平台管理端仪表盘 API

提供 Dashboard 统计数据：租户总数、活跃租户、用户总数、今日登录
"""

from datetime import datetime, timezone

from fastapi import APIRouter
from sqlalchemy import func, select

from app.core.deps import DbSession, ActiveAdmin
from app.core.response import success
from app.models.tenant.tenant import Tenant
from app.models.tenant.tenant_admin import TenantAdmin
from app.rbac.decorators import auth_only


router = APIRouter(prefix="/dashboard", tags=["Dashboard (Platform)"])


@router.get("/stats", summary="获取仪表盘统计数据")
@auth_only
async def get_dashboard_stats(
    db: DbSession,
    _current_admin: ActiveAdmin,
):
    """
    获取平台管理端仪表盘统计：
    - total_tenants: 租户总数
    - active_tenants: 活跃租户数
    - total_users: 租户管理员总数
    - today_login: 今日登录数（预留）
    """
    # 租户总数（未软删除）
    total_tenants_q = select(func.count()).select_from(Tenant).where(
        Tenant.deleted_at.is_(None)
    )
    total_tenants = (await db.execute(total_tenants_q)).scalar() or 0

    # 活跃租户数
    active_tenants_q = select(func.count()).select_from(Tenant).where(
        Tenant.deleted_at.is_(None),
        Tenant.is_active.is_(True),
    )
    active_tenants = (await db.execute(active_tenants_q)).scalar() or 0

    # 租户管理员总数
    total_users_q = select(func.count()).select_from(TenantAdmin).where(
        TenantAdmin.deleted_at.is_(None)
    )
    total_users = (await db.execute(total_users_q)).scalar() or 0

    # 今日登录数（使用 TenantAdmin.last_login_at）
    today_start = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    today_login_q = select(func.count()).select_from(TenantAdmin).where(
        TenantAdmin.deleted_at.is_(None),
        TenantAdmin.last_login_at >= today_start,
    )
    today_login = (await db.execute(today_login_q)).scalar() or 0

    return success(data={
        "total_tenants": total_tenants,
        "active_tenants": active_tenants,
        "total_users": total_users,
        "today_login": today_login,
    })


__all__ = ["router"]
