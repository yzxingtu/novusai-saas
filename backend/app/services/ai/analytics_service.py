"""
AI 数据分析服务 / AI Analytics Service

提供 Admin 端 ECharts 图表所需的聚合分析数据：
Provides aggregated analytics data for Admin ECharts dashboards:
- T2: AI 调用趋势（按天聚合）
- T3: 模型调用分布（饼图）
- T4: 供应商性能对比（雷达图）
- T5: 企业 Top N 排行
- T6: 延迟分布（直方图）
- 成功率趋势
- Token 消耗趋势
- 费用趋势
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_model import utc_now
from app.core.logging import LogManager
from app.enums.ai import CallStatusEnum
from app.models.ai.call_log import AICallLog

logger = LogManager.get_logger("ai")


class AnalyticsService:
    """Admin 端 AI 数据分析服务 / Admin AI analytics service."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── T2: AI 调用趋势（按天聚合） ──

    async def get_call_trend(
        self,
        start_date: date | None = None,
        end_date: date | None = None,
        tenant_id: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        按天聚合的调用量 + Token + 费用趋势 / Daily aggregated call/token/cost trend.

        Returns:
            [{"date", "calls", "tokens", "cost", "success", "failed"}, ...]
        """
        if not start_date:
            start_date = (utc_now() - timedelta(days=30)).date()
        if not end_date:
            end_date = utc_now().date()

        stmt = select(
            func.date(AICallLog.created_at).label("date"),
            func.count(AICallLog.id).label("calls"),
            func.coalesce(func.sum(AICallLog.total_tokens), 0).label("tokens"),
            func.coalesce(func.sum(AICallLog.input_tokens), 0).label("input_tokens"),
            func.coalesce(func.sum(AICallLog.output_tokens), 0).label("output_tokens"),
            func.coalesce(func.sum(AICallLog.cost), 0).label("cost"),
            func.sum(case(
                (AICallLog.status == CallStatusEnum.SUCCESS.value, 1), else_=0
            )).label("success"),
            func.sum(case(
                (AICallLog.status == CallStatusEnum.FAILED.value, 1), else_=0
            )).label("failed"),
        ).where(
            AICallLog.created_at >= start_date,
            AICallLog.created_at <= end_date + timedelta(days=1),
        )

        if tenant_id:
            stmt = stmt.where(AICallLog.tenant_id == tenant_id)

        stmt = stmt.group_by(func.date(AICallLog.created_at)).order_by(func.date(AICallLog.created_at))

        result = await self.db.execute(stmt)
        return [
            {
                "date": str(r.date),
                "calls": r.calls or 0,
                "tokens": int(r.tokens),
                "input_tokens": int(r.input_tokens),
                "output_tokens": int(r.output_tokens),
                "cost": float(r.cost),
                "success": int(r.success or 0),
                "failed": int(r.failed or 0),
            }
            for r in result.all()
        ]

    # ── T3: 模型调用分布（饼图） ──

    async def get_model_distribution(
        self,
        start_date: date | None = None,
        end_date: date | None = None,
        tenant_id: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        模型调用分布 / Model call distribution.

        Returns:
            [{"model_id", "model_name", "calls", "tokens", "cost"}, ...]
        """
        from app.models.ai.model import AIModel

        stmt = select(
            AICallLog.model_id,
            func.count(AICallLog.id).label("calls"),
            func.coalesce(func.sum(AICallLog.total_tokens), 0).label("tokens"),
            func.coalesce(func.sum(AICallLog.cost), 0).label("cost"),
        )

        filters = self._date_filters(start_date, end_date)
        if tenant_id:
            filters.append(AICallLog.tenant_id == tenant_id)

        stmt = stmt.where(*filters).group_by(AICallLog.model_id).order_by(func.count(AICallLog.id).desc()).limit(20)

        result = await self.db.execute(stmt)
        rows = result.all()

        # Fetch model names
        model_ids = [r.model_id for r in rows]
        model_names: dict[int, str] = {}
        if model_ids:
            name_result = await self.db.execute(
                select(AIModel.id, AIModel.name).where(AIModel.id.in_(model_ids))
            )
            model_names = {r.id: r.name for r in name_result.all()}

        return [
            {
                "model_id": r.model_id,
                "model_name": model_names.get(r.model_id, f"Model #{r.model_id}"),
                "calls": r.calls,
                "tokens": int(r.tokens),
                "cost": float(r.cost),
            }
            for r in rows
        ]

    # ── T4: 供应商性能对比（雷达图） ──

    async def get_provider_performance(
        self,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[dict[str, Any]]:
        """
        供应商性能对比 / Provider performance comparison.

        Returns:
            [{"provider_id", "provider_name", "calls", "avg_latency", "success_rate", "avg_tokens", "total_cost"}, ...]
        """
        from app.models.ai.provider import AIProvider

        stmt = select(
            AICallLog.provider_id,
            func.count(AICallLog.id).label("calls"),
            func.avg(AICallLog.latency_ms).label("avg_latency"),
            func.avg(AICallLog.total_tokens).label("avg_tokens"),
            func.coalesce(func.sum(AICallLog.cost), 0).label("total_cost"),
            func.sum(case(
                (AICallLog.status == CallStatusEnum.SUCCESS.value, 1), else_=0
            )).label("success_count"),
        )

        filters = self._date_filters(start_date, end_date)
        stmt = stmt.where(*filters).group_by(AICallLog.provider_id)

        result = await self.db.execute(stmt)
        rows = result.all()

        # Fetch provider names
        provider_ids = [r.provider_id for r in rows]
        provider_names: dict[int, str] = {}
        if provider_ids:
            name_result = await self.db.execute(
                select(AIProvider.id, AIProvider.name).where(AIProvider.id.in_(provider_ids))
            )
            provider_names = {r.id: r.name for r in name_result.all()}

        return [
            {
                "provider_id": r.provider_id,
                "provider_name": provider_names.get(r.provider_id, f"Provider #{r.provider_id}"),
                "calls": r.calls,
                "avg_latency": round(float(r.avg_latency or 0), 1),
                "success_rate": round((r.success_count or 0) / max(r.calls, 1) * 100, 1),
                "avg_tokens": round(float(r.avg_tokens or 0), 0),
                "total_cost": float(r.total_cost),
            }
            for r in rows
        ]

    # ── T5: 企业 Top N 使用排行 ──

    async def get_tenant_ranking(
        self,
        top_n: int = 10,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[dict[str, Any]]:
        """
        企业 Top N 使用排行 / Tenant Top N usage ranking.

        Returns:
            [{"tenant_id", "tenant_name", "calls", "tokens", "cost"}, ...]
        """
        from app.models.tenant.tenant import Tenant

        stmt = select(
            AICallLog.tenant_id,
            func.count(AICallLog.id).label("calls"),
            func.coalesce(func.sum(AICallLog.total_tokens), 0).label("tokens"),
            func.coalesce(func.sum(AICallLog.cost), 0).label("cost"),
        )

        filters = self._date_filters(start_date, end_date)
        stmt = stmt.where(*filters).group_by(AICallLog.tenant_id).order_by(func.count(AICallLog.id).desc()).limit(top_n)

        result = await self.db.execute(stmt)
        rows = result.all()

        # Fetch tenant names
        tenant_ids = [r.tenant_id for r in rows if r.tenant_id]
        tenant_names: dict[int, str] = {}
        if tenant_ids:
            name_result = await self.db.execute(
                select(Tenant.id, Tenant.name).where(Tenant.id.in_(tenant_ids))
            )
            tenant_names = {r.id: r.name for r in name_result.all()}

        return [
            {
                "tenant_id": r.tenant_id,
                "tenant_name": tenant_names.get(r.tenant_id, f"Tenant #{r.tenant_id}") if r.tenant_id else "Platform",
                "calls": r.calls,
                "tokens": int(r.tokens),
                "cost": float(r.cost),
            }
            for r in rows
        ]

    # ── T6: 延迟分布（直方图） ──

    async def get_latency_distribution(
        self,
        start_date: date | None = None,
        end_date: date | None = None,
        tenant_id: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        延迟分布（按区间聚合，单次 CASE WHEN 查询）/ Latency distribution (bucket aggregation, single CASE WHEN).

        Returns:
            [{"range": "0-200ms", "count": 150}, {"range": "200-500ms", "count": 80}, ...]
        """
        from sqlalchemy import case, literal_column

        buckets = [
            (0, 200, "0-200ms"),
            (200, 500, "200-500ms"),
            (500, 1000, "500ms-1s"),
            (1000, 2000, "1-2s"),
            (2000, 5000, "2-5s"),
            (5000, 999999, "5s+"),
        ]

        filters = self._date_filters(start_date, end_date)
        if tenant_id:
            filters.append(AICallLog.tenant_id == tenant_id)
        filters.append(AICallLog.latency_ms.isnot(None))

        columns = []
        for low, high, label in buckets:
            col = func.sum(
                case(
                    (
                        (AICallLog.latency_ms >= low) & (AICallLog.latency_ms < high),
                        literal_column("1"),
                    ),
                    else_=literal_column("0"),
                )
            ).label(label)
            columns.append(col)

        stmt = select(*columns).where(*filters)
        row = (await self.db.execute(stmt)).one()

        return [
            {"range": label, "count": int(row[i] or 0)}
            for i, (_, _, label) in enumerate(buckets)
        ]

    # ── 成功率趋势 ──

    async def get_success_rate_trend(
        self,
        start_date: date | None = None,
        end_date: date | None = None,
        tenant_id: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        按天的成功率趋势 / Daily success rate trend.

        Returns:
            [{"date", "total", "success", "failed", "rate"}, ...]
        """
        trend = await self.get_call_trend(start_date, end_date, tenant_id)
        return [
            {
                "date": item["date"],
                "total": item["calls"],
                "success": item["success"],
                "failed": item["failed"],
                "rate": round(item["success"] / max(item["calls"], 1) * 100, 1),
            }
            for item in trend
        ]

    # ── helpers ──

    def _date_filters(self, start_date: date | None, end_date: date | None) -> list:
        filters = []
        if start_date:
            filters.append(AICallLog.created_at >= start_date)
        if end_date:
            filters.append(AICallLog.created_at <= end_date + timedelta(days=1))
        return filters


__all__ = ["AnalyticsService"]
