"""
使用量统计 Repository

提供使用量统计的查询和聚合功能
"""

from datetime import date
from typing import Optional
from sqlalchemy import select, func, and_

from app.core.base_repository import BaseRepository
from app.models.ai import UsageStat
from app.models.ai.model import AIModel


class UsageStatRepository(BaseRepository[UsageStat]):
    """
    使用量统计 Repository
    """
    model = UsageStat

    async def get_or_create_stat(
        self,
        tenant_id: int,
        model_id: int,
        request_type: str,
        stat_date: date,
        user_id: Optional[int] = None,
    ) -> UsageStat:
        """
        获取或创建统计记录
        """
        stmt = select(UsageStat).where(
            and_(
                UsageStat.tenant_id == tenant_id,
                UsageStat.model_id == model_id,
                UsageStat.request_type == request_type,
                UsageStat.stat_date == stat_date,
                UsageStat.user_id == user_id if user_id else UsageStat.user_id.is_(None)
            )
        )
        result = await self.db.execute(stmt)
        stat = result.scalar_one_or_none()

        if not stat:
            stat = UsageStat(
                tenant_id=tenant_id,
                model_id=model_id,
                request_type=request_type,
                stat_date=stat_date,
                user_id=user_id,
            )
            self.db.add(stat)
            await self.db.flush()

        return stat

    async def get_tenant_usage_summary(
        self,
        tenant_id: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> dict:
        """
        获取租户使用量汇总
        """
        stmt = select(
            func.sum(UsageStat.total_tokens).label("total_tokens"),
            func.sum(UsageStat.input_tokens).label("input_tokens"),
            func.sum(UsageStat.output_tokens).label("output_tokens"),
            func.sum(UsageStat.call_count).label("call_count"),
            func.sum(UsageStat.total_cost).label("total_cost"),
            func.sum(UsageStat.success_count).label("success_count"),
            func.sum(UsageStat.failed_count).label("failed_count"),
        ).where(UsageStat.tenant_id == tenant_id)

        if start_date:
            stmt = stmt.where(UsageStat.stat_date >= start_date)
        if end_date:
            stmt = stmt.where(UsageStat.stat_date <= end_date)

        result = await self.db.execute(stmt)
        row = result.one()

        return {
            "total_tokens": row.total_tokens or 0,
            "input_tokens": row.input_tokens or 0,
            "output_tokens": row.output_tokens or 0,
            "total_calls": row.call_count or 0,
            "total_cost": float(row.total_cost or 0),
            "success_calls": row.success_count or 0,
            "failed_calls": row.failed_count or 0,
        }

    async def get_user_usage_summary(
        self,
        tenant_id: int,
        user_id: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> dict:
        """
        获取用户使用量汇总
        """
        stmt = select(
            func.sum(UsageStat.total_tokens).label("total_tokens"),
            func.sum(UsageStat.call_count).label("call_count"),
            func.sum(UsageStat.total_cost).label("total_cost"),
        ).where(
            and_(
                UsageStat.tenant_id == tenant_id,
                UsageStat.user_id == user_id,
            )
        )

        if start_date:
            stmt = stmt.where(UsageStat.stat_date >= start_date)
        if end_date:
            stmt = stmt.where(UsageStat.stat_date <= end_date)

        result = await self.db.execute(stmt)
        row = result.one()

        return {
            "total_tokens": row.total_tokens or 0,
            "call_count": row.call_count or 0,
            "total_cost": float(row.total_cost or 0),
        }

    async def get_model_usage_summary(
        self,
        model_id: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> dict:
        """
        获取模型使用量汇总
        """
        stmt = select(
            func.sum(UsageStat.total_tokens).label("total_tokens"),
            func.sum(UsageStat.call_count).label("call_count"),
            func.sum(UsageStat.total_cost).label("total_cost"),
            func.count(func.distinct(UsageStat.tenant_id)).label("tenant_count"),
        ).where(UsageStat.model_id == model_id)

        if start_date:
            stmt = stmt.where(UsageStat.stat_date >= start_date)
        if end_date:
            stmt = stmt.where(UsageStat.stat_date <= end_date)

        result = await self.db.execute(stmt)
        row = result.one()

        return {
            "total_tokens": row.total_tokens or 0,
            "call_count": row.call_count or 0,
            "total_cost": float(row.total_cost or 0),
            "tenant_count": row.tenant_count or 0,
        }


    async def get_daily_stats(
        self,
        tenant_id: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> list[dict]:
        """
        获取租户每日用量统计
        """
        stmt = select(
            UsageStat.stat_date.label("stat_date"),
            func.sum(UsageStat.input_tokens).label("input_tokens"),
            func.sum(UsageStat.output_tokens).label("output_tokens"),
            func.sum(UsageStat.total_tokens).label("total_tokens"),
            func.sum(UsageStat.total_cost).label("cost"),
            func.sum(UsageStat.call_count).label("calls"),
        ).where(
            and_(
                UsageStat.tenant_id == tenant_id,
                UsageStat.user_id.is_(None),
            )
        )

        if start_date:
            stmt = stmt.where(UsageStat.stat_date >= start_date)
        if end_date:
            stmt = stmt.where(UsageStat.stat_date <= end_date)

        stmt = stmt.group_by(UsageStat.stat_date).order_by(UsageStat.stat_date)

        result = await self.db.execute(stmt)
        rows = result.all()

        return [
            {
                "date": str(row.stat_date),
                "input_tokens": row.input_tokens or 0,
                "output_tokens": row.output_tokens or 0,
                "total_tokens": row.total_tokens or 0,
                "cost": float(row.cost or 0),
                "calls": row.calls or 0,
            }
            for row in rows
        ]

    async def get_model_stats(
        self,
        tenant_id: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> list[dict]:
        """
        获取租户按模型维度的用量统计
        """
        stmt = select(
            UsageStat.model_id,
            AIModel.name.label("model_name"),
            func.sum(UsageStat.total_tokens).label("total_tokens"),
            func.sum(UsageStat.total_cost).label("cost"),
            func.sum(UsageStat.call_count).label("calls"),
        ).join(
            AIModel, AIModel.id == UsageStat.model_id, isouter=True
        ).where(
            and_(
                UsageStat.tenant_id == tenant_id,
                UsageStat.user_id.is_(None),
            )
        )

        if start_date:
            stmt = stmt.where(UsageStat.stat_date >= start_date)
        if end_date:
            stmt = stmt.where(UsageStat.stat_date <= end_date)

        stmt = stmt.group_by(UsageStat.model_id, AIModel.name)
        stmt = stmt.order_by(func.sum(UsageStat.total_tokens).desc())

        result = await self.db.execute(stmt)
        rows = result.all()

        return [
            {
                "model_id": row.model_id,
                "model_name": row.model_name or "Unknown",
                "total_tokens": row.total_tokens or 0,
                "cost": float(row.cost or 0),
                "calls": row.calls or 0,
            }
            for row in rows
        ]


__all__ = ["UsageStatRepository"]
