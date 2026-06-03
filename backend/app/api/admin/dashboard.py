"""
平台管理端仪表盘 API / Platform Admin Dashboard API

提供 Dashboard 统计数据 / Provides dashboard statistics:
- A1: 系统健康状态 / System health status
- A2: AI 使用概览 / AI usage overview
- A3: 存储使用概览 / Storage usage overview
- A4: 插件状态概览 / Plugin status overview
- A5: 企业增长趋势 / Tenant growth trend
- A6: 近期活动时间线 / Recent activity timeline
"""

from fastapi import APIRouter, Query

from app.core.deps import ActiveAdmin, DbSession
from app.core.i18n import _
from app.core.response import success
from app.rbac.decorators import auth_only
from app.services.system.dashboard_service import AdminDashboardService

router = APIRouter(prefix="/dashboard", tags=["Dashboard (Platform)"])


@router.get("/overview", summary="平台仪表盘总览")
@auth_only
async def get_dashboard_overview(
    db: DbSession,
    _current_admin: ActiveAdmin,
):
    """聚合平台端 dashboard 所需真实数据 / Aggregate platform dashboard snapshot."""
    service = AdminDashboardService(db)
    data = await service.get_overview()
    return success(data=data)


@router.get("/stats", summary="获取仪表盘统计数据")
@auth_only
async def get_dashboard_stats(
    db: DbSession,
    _current_admin: ActiveAdmin,
):
    """
    获取平台管理端仪表盘统计 / Get platform admin dashboard statistics:
    - total_tenants: 企业总数 / Total tenants
    - active_tenants: 活跃企业数 / Active tenants
    - total_users: 企业管理员总数 / Total tenant admins
    - today_login: 今日登录数 / Today's logins
    """
    service = AdminDashboardService(db)
    data = await service.get_stats()
    return success(data=data)


@router.get("/health", summary="系统健康状态")
@auth_only
async def get_system_health(
    db: DbSession,
    _current_admin: ActiveAdmin,
):
    """A1: Redis/Celery/DB 连通性 + 内存 + 运行时间 / Redis/Celery/DB connectivity + memory + uptime"""
    service = AdminDashboardService(db)
    data = await service.get_system_health()
    return success(data=data)


@router.get("/ai-overview", summary="AI 使用概览")
@auth_only
async def get_ai_overview(
    db: DbSession,
    _current_admin: ActiveAdmin,
):
    """A2: 总调用/Token/活跃供应商/今日调用/成功率 / Total calls/tokens/active providers/today's calls/success rate"""
    service = AdminDashboardService(db)
    data = await service.get_ai_overview()
    return success(data=data)


@router.get("/storage-overview", summary="存储使用概览")
@auth_only
async def get_storage_overview(
    db: DbSession,
    _current_admin: ActiveAdmin,
):
    """A3: 总文件数/总大小/驱动分布 / Total files/total size/driver distribution"""
    service = AdminDashboardService(db)
    data = await service.get_storage_overview()
    return success(data=data)


@router.get("/plugin-overview", summary="插件状态概览")
@auth_only
async def get_plugin_overview(
    db: DbSession,
    _current_admin: ActiveAdmin,
):
    """A4: 已安装/已启用/已禁用/错误数 / Installed/enabled/disabled/error count"""
    service = AdminDashboardService(db)
    data = await service.get_plugin_overview()
    return success(data=data)


@router.get("/tenant-growth", summary="企业增长趋势")
@auth_only
async def get_tenant_growth(
    db: DbSession,
    _current_admin: ActiveAdmin,
    days: int = Query(30, ge=1, le=365, description=_("api.param.days")),
):
    """A5: 近 N 天每日新增企业数 / Daily new tenants in last N days"""
    service = AdminDashboardService(db)
    data = await service.get_tenant_growth(days=days)
    return success(data=data)


@router.get("/recent-activities", summary="近期活动时间线")
@auth_only
async def get_recent_activities(
    db: DbSession,
    _current_admin: ActiveAdmin,
    limit: int = Query(20, ge=1, le=100, description=_("api.param.limit")),
):
    """A6: 最近 N 条操作日志 / Last N operation logs"""
    service = AdminDashboardService(db)
    data = await service.get_recent_activities(limit=limit)
    return success(data=data)


@router.get("/system-info", summary="详细系统信息")
@auth_only
async def get_system_info(
    db: DbSession,
    _current_admin: ActiveAdmin,
):
    """C2: Python 版本、FastAPI 版本、DB 版本、环境变量、插件数等 / Python version, FastAPI version, DB version, env vars, plugin count, etc."""
    import platform
    import sys

    from app.core.config import settings

    service = AdminDashboardService(db)
    health = await service.get_system_health()
    plugin_overview = await service.get_plugin_overview()

    data = {
        "python_version": sys.version,
        "platform": platform.platform(),
        "app_env": settings.APP_ENV,
        "debug": settings.DEBUG,
        "health": health,
        "plugins": plugin_overview,
    }
    return success(data=data)


__all__ = ["router"]
