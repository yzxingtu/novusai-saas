"""
平台管理端仪表盘 API

提供 Dashboard 统计数据：租户总数、活跃租户、用户总数、今日登录
"""

from fastapi import APIRouter

from app.core.deps import DbSession, ActiveAdmin
from app.core.response import success
from app.rbac.decorators import auth_only
from app.services.system.dashboard_service import AdminDashboardService


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
    - today_login: 今日登录数
    """
    service = AdminDashboardService(db)
    data = await service.get_stats()
    return success(data=data)


__all__ = ["router"]
