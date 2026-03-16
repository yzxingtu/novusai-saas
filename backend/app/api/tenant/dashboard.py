"""
企业端仪表盘 API / Tenant Dashboard API

提供企业 Dashboard 统计数据 / Provides tenant dashboard statistics:
- B1: 真实 AI 调用统计（替换硬编码 0） / Real AI call statistics (replaces hardcoded 0)
- B2: AI 使用趋势（近7天每日调用量+Token量） / AI usage trend (daily calls + tokens for last 7 days)
- B3: 存储使用详情（配额/已用/文件分类分布） / Storage usage details (quota/used/file type distribution)
- B4: 近期活动（最近20条操作日志） / Recent activities (last 20 operation logs)
"""

from fastapi import APIRouter, Query

from app.core.deps import ActiveTenantAdmin, DbSession
from app.core.i18n import _
from app.core.response import success
from app.rbac.decorators import auth_only
from app.services.system.dashboard_service import TenantDashboardService

router = APIRouter(prefix="/dashboard", tags=["Dashboard (Tenant)"])


@router.get("/stats", summary="获取企业仪表盘统计数据")
@auth_only
async def get_tenant_dashboard_stats(
    db: DbSession,
    current_admin: ActiveTenantAdmin,
):
    """
    获取企业端仪表盘统计（增强版） / Get tenant dashboard statistics (enhanced):
    - total_users: 企业下管理员总数 / Total admins under tenant
    - active_users: 活跃用户数 / Active user count
    - api_calls: 真实 AI 调用数 / Real AI call count
    - total_tokens: AI Token 总量 / Total AI tokens
    - total_cost: AI 费用总计 / Total AI cost
    - storage_used_bytes/mb: 存储使用量 / Storage usage
    """
    service = TenantDashboardService(db, current_admin.tenant_id)
    data = await service.get_stats()
    return success(data=data)


@router.get("/ai-trend", summary="AI 使用趋势")
@auth_only
async def get_ai_trend(
    db: DbSession,
    current_admin: ActiveTenantAdmin,
    days: int = Query(7, ge=1, le=90, description=_("api.param.days")),
):
    """B2: 近 N 天每日 AI 调用量 + Token 量 / Last N days daily AI calls + token usage"""
    service = TenantDashboardService(db, current_admin.tenant_id)
    data = await service.get_ai_trend(days=days)
    return success(data=data)


@router.get("/storage-detail", summary="存储使用详情")
@auth_only
async def get_storage_detail(
    db: DbSession,
    current_admin: ActiveTenantAdmin,
):
    """B3: 已用大小/文件数/MIME 类型分布 / Used size/file count/MIME type distribution"""
    service = TenantDashboardService(db, current_admin.tenant_id)
    data = await service.get_storage_detail()
    return success(data=data)


@router.get("/recent-activities", summary="近期活动")
@auth_only
async def get_recent_activities(
    db: DbSession,
    current_admin: ActiveTenantAdmin,
    limit: int = Query(20, ge=1, le=100, description=_("api.param.limit")),
):
    """B4: 最近 N 条操作日志 / Last N operation logs"""
    service = TenantDashboardService(db, current_admin.tenant_id)
    data = await service.get_recent_activities(limit=limit)
    return success(data=data)


__all__ = ["router"]
