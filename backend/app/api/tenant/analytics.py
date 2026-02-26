"""
Tenant 数据分析 API

提供 Tenant 端 ECharts 图表所需的聚合分析数据端点：
- 调用趋势（折线/面积图）
- 模型分布（饼图）
- Agent 调用排行（柱状图）
- 费用趋势（折线图）
"""

from datetime import date

from fastapi import APIRouter, Query

from app.core.deps import DbSession, ActiveTenantAdmin
from app.core.response import success
from app.rbac.decorators import auth_only
from app.services.ai.tenant_analytics_service import TenantAnalyticsService


router = APIRouter(prefix="/analytics", tags=["Analytics (Tenant)"])


@router.get("/call-trend", summary="AI 调用趋势")
@auth_only
async def get_call_trend(
    db: DbSession,
    admin: ActiveTenantAdmin,
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
):
    """按天聚合：调用量/Token/费用/成功/失败"""
    svc = TenantAnalyticsService(db, admin.tenant_id)
    data = await svc.get_call_trend(start_date, end_date)
    return success(data=data)


@router.get("/model-distribution", summary="模型调用分布")
@auth_only
async def get_model_distribution(
    db: DbSession,
    admin: ActiveTenantAdmin,
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
):
    """模型调用次数/Token/费用分布（饼图）"""
    svc = TenantAnalyticsService(db, admin.tenant_id)
    data = await svc.get_model_distribution(start_date, end_date)
    return success(data=data)


@router.get("/agent-ranking", summary="Agent 调用排行")
@auth_only
async def get_agent_ranking(
    db: DbSession,
    admin: ActiveTenantAdmin,
    top_n: int = Query(10, ge=1, le=50),
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
):
    """Agent Top N 调用量/Token/费用排行（柱状图）"""
    svc = TenantAnalyticsService(db, admin.tenant_id)
    data = await svc.get_agent_ranking(top_n, start_date, end_date)
    return success(data=data)


@router.get("/cost-trend", summary="费用趋势")
@auth_only
async def get_cost_trend(
    db: DbSession,
    admin: ActiveTenantAdmin,
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
):
    """按天聚合费用趋势"""
    svc = TenantAnalyticsService(db, admin.tenant_id)
    data = await svc.get_cost_trend(start_date, end_date)
    return success(data=data)


__all__ = ["router"]
