"""
租户端仪表盘 API

提供租户 Dashboard 统计数据：
- B1: 真实 AI 调用统计（替换硬编码 0）
- B2: AI 使用趋势（近7天每日调用量+Token量）
- B3: 存储使用详情（配额/已用/文件分类分布）
- B4: 近期活动（最近20条操作日志）
"""

from fastapi import APIRouter, Query

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
    获取租户端仪表盘统计（增强版）：
    - total_users: 租户下管理员总数
    - active_users: 活跃用户数
    - api_calls: 真实 AI 调用数
    - total_tokens: AI Token 总量
    - total_cost: AI 费用总计
    - storage_used_bytes/mb: 存储使用量
    """
    service = TenantDashboardService(db, current_admin.tenant_id)
    data = await service.get_stats()
    return success(data=data)


@router.get("/ai-trend", summary="AI 使用趋势")
@auth_only
async def get_ai_trend(
    db: DbSession,
    current_admin: ActiveTenantAdmin,
    days: int = Query(7, ge=1, le=90, description="天数"),
):
    """B2: 近 N 天每日 AI 调用量 + Token 量"""
    service = TenantDashboardService(db, current_admin.tenant_id)
    data = await service.get_ai_trend(days=days)
    return success(data=data)


@router.get("/storage-detail", summary="存储使用详情")
@auth_only
async def get_storage_detail(
    db: DbSession,
    current_admin: ActiveTenantAdmin,
):
    """B3: 已用大小/文件数/MIME 类型分布"""
    service = TenantDashboardService(db, current_admin.tenant_id)
    data = await service.get_storage_detail()
    return success(data=data)


@router.get("/recent-activities", summary="近期活动")
@auth_only
async def get_recent_activities(
    db: DbSession,
    current_admin: ActiveTenantAdmin,
    limit: int = Query(20, ge=1, le=100, description="返回条数"),
):
    """B4: 最近 N 条操作日志"""
    service = TenantDashboardService(db, current_admin.tenant_id)
    data = await service.get_recent_activities(limit=limit)
    return success(data=data)


__all__ = ["router"]
