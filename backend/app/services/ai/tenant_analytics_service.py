"""
Tenant 端 AI 数据分析服务 / Tenant AI Analytics Service

复用 AnalyticsService 核心查询，自动注入 tenant_id 过滤。
Reuses AnalyticsService core queries with auto-injected tenant_id filtering.
额外提供 / Additionally provides:
- Agent 调用排行 / Agent call rankings
- 费用趋势 / Cost trends
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_model import utc_now
from app.core.logging import LogManager
from app.services.ai.analytics_service import AnalyticsService

logger = LogManager.get_logger("ai")


class TenantAnalyticsService:
    """Tenant 端 AI 数据分析服务（自动过滤 tenant_id）"""

    def __init__(self, db: AsyncSession, tenant_id: int) -> None:
        self.db = db
        self.tenant_id = tenant_id
        self._admin_svc = AnalyticsService(db)

    async def get_call_trend(
        self,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[dict[str, Any]]:
        """按天聚合调用趋势（自动注入 tenant_id）"""
        return await self._admin_svc.get_call_trend(start_date, end_date, self.tenant_id)

    async def get_model_distribution(
        self,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[dict[str, Any]]:
        """模型调用分布（自动注入 tenant_id）"""
        return await self._admin_svc.get_model_distribution(start_date, end_date, self.tenant_id)

    async def get_cost_trend(
        self,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[dict[str, Any]]:
        """
        费用趋势（按天聚合）

        Returns:
            [{"date", "cost", "calls"}, ...]
        """
        trend = await self.get_call_trend(start_date, end_date)
        return [
            {
                "date": item["date"],
                "cost": item["cost"],
                "calls": item["calls"],
            }
            for item in trend
        ]

    async def get_agent_ranking(
        self,
        top_n: int = 10,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[dict[str, Any]]:
        """
        Agent 调用排行（基于 AIActionLog，因为 AICallLog 无 agent_id）

        Returns:
            [{"agent_id", "agent_name", "calls"}, ...]
        """
        from app.models.ai.action_log import AIActionLog
        from app.models.ai.agent import Agent

        if not start_date:
            start_date = (utc_now() - timedelta(days=30)).date()
        if not end_date:
            end_date = utc_now().date()

        stmt = select(
            AIActionLog.agent_id,
            func.count(AIActionLog.id).label("calls"),
        ).where(
            AIActionLog.tenant_id == self.tenant_id,
            AIActionLog.created_at >= start_date,
            AIActionLog.created_at <= end_date + timedelta(days=1),
        ).group_by(
            AIActionLog.agent_id,
        ).order_by(
            func.count(AIActionLog.id).desc(),
        ).limit(top_n)

        result = await self.db.execute(stmt)
        rows = result.all()

        # Fetch agent names
        agent_ids = [r.agent_id for r in rows if r.agent_id]
        agent_names: dict[int, str] = {}
        if agent_ids:
            name_result = await self.db.execute(
                select(Agent.id, Agent.name).where(Agent.id.in_(agent_ids))
            )
            agent_names = {r.id: r.name for r in name_result.all()}

        return [
            {
                "agent_id": r.agent_id,
                "agent_name": agent_names.get(r.agent_id, f"Agent #{r.agent_id}") if r.agent_id else "Unknown",
                "calls": r.calls,
                "tokens": 0,
                "cost": 0.0,
            }
            for r in rows
        ]


__all__ = ["TenantAnalyticsService"]
