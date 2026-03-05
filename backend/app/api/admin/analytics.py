"""
Admin 数据分析 API

提供 ECharts 图表所需的聚合分析数据端点：
- 调用趋势（折线/面积图）
- 模型分布（饼图）
- 供应商性能（雷达图）
- 租户排行（柱状图）
- 延迟分布（直方图）
- 成功率趋势（折线图）
"""

from datetime import date

from fastapi import APIRouter, Query

from app.core.deps import ActiveAdmin, DbSession
from app.core.response import success
from app.rbac.decorators import auth_only
from app.services.ai.analytics_service import AnalyticsService

router = APIRouter(prefix="/analytics", tags=["Analytics (Platform)"])


@router.get("/call-trend", summary="AI 调用趋势")
@auth_only
async def get_call_trend(
    db: DbSession,
    _admin: ActiveAdmin,
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    tenant_id: int | None = Query(None),
):
    """按天聚合：调用量/Token/费用/成功/失败"""
    svc = AnalyticsService(db)
    data = await svc.get_call_trend(start_date, end_date, tenant_id)
    return success(data=data)


@router.get("/model-distribution", summary="模型调用分布")
@auth_only
async def get_model_distribution(
    db: DbSession,
    _admin: ActiveAdmin,
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    tenant_id: int | None = Query(None),
):
    """模型调用次数/Token/费用分布（饼图）"""
    svc = AnalyticsService(db)
    data = await svc.get_model_distribution(start_date, end_date, tenant_id)
    return success(data=data)


@router.get("/provider-performance", summary="供应商性能对比")
@auth_only
async def get_provider_performance(
    db: DbSession,
    _admin: ActiveAdmin,
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
):
    """供应商调用量/延迟/成功率/Token/费用对比（雷达图）"""
    svc = AnalyticsService(db)
    data = await svc.get_provider_performance(start_date, end_date)
    return success(data=data)


@router.get("/tenant-ranking", summary="租户使用排行")
@auth_only
async def get_tenant_ranking(
    db: DbSession,
    _admin: ActiveAdmin,
    top_n: int = Query(10, ge=1, le=50),
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
):
    """租户 Top N 调用量/Token/费用排行（柱状图）"""
    svc = AnalyticsService(db)
    data = await svc.get_tenant_ranking(top_n, start_date, end_date)
    return success(data=data)


@router.get("/latency-distribution", summary="延迟分布")
@auth_only
async def get_latency_distribution(
    db: DbSession,
    _admin: ActiveAdmin,
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    tenant_id: int | None = Query(None),
):
    """请求延迟区间分布（直方图）"""
    svc = AnalyticsService(db)
    data = await svc.get_latency_distribution(start_date, end_date, tenant_id)
    return success(data=data)


@router.get("/success-rate-trend", summary="成功率趋势")
@auth_only
async def get_success_rate_trend(
    db: DbSession,
    _admin: ActiveAdmin,
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    tenant_id: int | None = Query(None),
):
    """按天成功率趋势（折线图）"""
    svc = AnalyticsService(db)
    data = await svc.get_success_rate_trend(start_date, end_date, tenant_id)
    return success(data=data)


__all__ = ["router"]
