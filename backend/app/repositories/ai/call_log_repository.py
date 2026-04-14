"""
AI 调用日志 Repository / AI Call Log Repository

提供调用日志查询、监控统计和基于账单事实的使用量聚合。
Provides call log queries, monitoring statistics, and billing-fact usage aggregations.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import select

from app.core.base_repository import BaseRepository
from app.enums.ai import CallStatusEnum
from app.models.ai import AICallLog
from app.repositories.ai.call_log_repository_enrichment import (
    enrich_logs_to_dicts as enrich_call_logs_to_dicts,
)
from app.repositories.ai.call_log_repository_usage import (
    date_filters,
    effective_usage_tenant_expr,
    effective_usage_tenant_name_expr,
    get_billing_daily_stats,
    get_billing_model_stats,
    get_billing_model_usage_summary,
    get_billing_tenant_usage_summary,
    get_billing_user_usage_summary,
    get_overall_summary,
    get_statistics,
    platform_usage_tenant_expr,
    query_usage_stats,
)
from app.schemas.common.query import FilterRule, QuerySpec


class AICallLogRepository(BaseRepository[AICallLog]):
    """
    AI 调用日志 Repository / AI call log repository.
    """

    model = AICallLog
    PLATFORM_USAGE_TENANT_NAME = "平台管理端"

    @classmethod
    def _platform_usage_tenant_expr(cls):
        return platform_usage_tenant_expr()

    @classmethod
    def _effective_usage_tenant_expr(cls):
        return effective_usage_tenant_expr()

    @classmethod
    def _effective_usage_tenant_name_expr(cls):
        return effective_usage_tenant_name_expr(cls.PLATFORM_USAGE_TENANT_NAME)

    @staticmethod
    def _date_filters(
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list:
        return date_filters(start_date, end_date)

    async def enrich_logs_to_dicts(
        self,
        items: list[AICallLog],
        *,
        include_tenant_names: bool = True,
        include_caller_names: bool = False,
        include_payload: bool = False,
    ) -> list[dict]:
        return await enrich_call_logs_to_dicts(
            self.db,
            items,
            include_tenant_names=include_tenant_names,
            include_caller_names=include_caller_names,
            include_payload=include_payload,
            platform_tenant_id=0,
            platform_usage_tenant_name=self.PLATFORM_USAGE_TENANT_NAME,
        )

    async def query_list_with_names(
        self,
        spec,
        *,
        forced_filters: list[FilterRule] | None = None,
        include_tenant_names: bool = True,
        include_caller_names: bool = False,
    ) -> tuple[list[dict], int]:
        """
        查询调用日志列表，附带 model_name / provider_name / tenant_name / Query call log list with names.

        通过批量查 ID→Name 映射，避免逐行 JOIN 性能问题
        """
        items, total = await self.query_list(spec, forced_filters=forced_filters)
        if not items:
            return [], total

        result = await self.enrich_logs_to_dicts(
            items,
            include_tenant_names=include_tenant_names,
            include_caller_names=include_caller_names,
            include_payload=False,
        )
        return result, total

    async def query_usage_stats(
        self,
        spec: QuerySpec,
    ) -> tuple[list[dict], int]:
        return await query_usage_stats(self, spec)

    async def get_statistics(
        self,
        tenant_id: int | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        group_by: str | None = None,
    ) -> list[dict]:
        """
        获取统计信息 / Get call statistics.

        Args:
            tenant_id: 企业 ID (可选)
            start_date: 开始日期
            end_date: 结束日期
            group_by: 分组维度 (daily/model/user)

        Returns:
            统计数据列表
        """
        return await get_statistics(
            self.db,
            tenant_id=tenant_id,
            start_date=start_date,
            end_date=end_date,
            group_by=group_by,
        )

    async def get_by_request_hash(
        self,
        request_hash: str,
        tenant_id: int | None = None,
    ) -> AICallLog | None:
        """
        根据请求哈希查询日志（用于缓存命中检测）/ Get log by request hash (for cache hit detection).
        """
        stmt = select(AICallLog).where(
            AICallLog.request_hash == request_hash,
            AICallLog.status == CallStatusEnum.SUCCESS.value,
            AICallLog.is_deleted.is_(False),
        )

        if tenant_id is not None:
            stmt = stmt.where(AICallLog.tenant_id == tenant_id)

        stmt = stmt.order_by(AICallLog.created_at.desc())
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_recent_logs(
        self,
        tenant_id: int | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AICallLog]:
        """
        获取最近的调用日志 / Get recent call logs.
        """
        stmt = select(AICallLog).where(AICallLog.is_deleted.is_(False))

        if tenant_id is not None:
            stmt = stmt.where(AICallLog.tenant_id == tenant_id)

        stmt = stmt.order_by(AICallLog.created_at.desc()).limit(limit).offset(offset)
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def get_failed_logs(
        self,
        tenant_id: int | None = None,
        start_date: date | None = None,
        limit: int = 100,
    ) -> list[AICallLog]:
        """
        获取失败的调用日志 / Get failed call logs.
        """
        stmt = select(AICallLog).where(
            AICallLog.status == CallStatusEnum.FAILED.value,
            AICallLog.is_deleted.is_(False),
        )

        if tenant_id is not None:
            stmt = stmt.where(AICallLog.tenant_id == tenant_id)
        if start_date:
            stmt = stmt.where(AICallLog.created_at >= start_date)

        stmt = stmt.order_by(AICallLog.created_at.desc()).limit(limit)
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def get_overall_summary(
        self,
        tenant_id: int | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> dict:
        """
        获取总体统计汇总（单个 dict，非分组列表）/ Get overall call summary (single dict, not grouped).
        """
        return await get_overall_summary(
            self.db,
            tenant_id=tenant_id,
            start_date=start_date,
            end_date=end_date,
        )

    async def get_billing_tenant_usage_summary(
        self,
        tenant_id: int,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> dict:
        """
        Get tenant usage summary from billing facts.
        从计费事实获取企业用量汇总。
        """
        return await get_billing_tenant_usage_summary(
            self,
            tenant_id=tenant_id,
            start_date=start_date,
            end_date=end_date,
        )

    async def get_billing_user_usage_summary(
        self,
        tenant_id: int,
        user_id: int,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> dict:
        """
        Get tenant-user usage summary from billing facts.
        从计费事实获取企业用户用量汇总。
        """
        return await get_billing_user_usage_summary(
            self,
            tenant_id=tenant_id,
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
        )

    async def get_billing_model_usage_summary(
        self,
        model_id: int,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> dict:
        """
        Get model usage summary from billing facts.
        从计费事实获取模型用量汇总。
        """
        return await get_billing_model_usage_summary(
            self,
            model_id=model_id,
            start_date=start_date,
            end_date=end_date,
        )

    async def get_billing_daily_stats(
        self,
        tenant_id: int,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[dict]:
        """Get tenant daily usage stats from billing facts / 从计费事实获取企业每日用量统计。"""
        return await get_billing_daily_stats(
            self,
            tenant_id=tenant_id,
            start_date=start_date,
            end_date=end_date,
        )

    async def get_billing_model_stats(
        self,
        tenant_id: int,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[dict]:
        """Get tenant usage stats by model from billing facts / 从计费事实获取企业按模型用量统计。"""
        return await get_billing_model_stats(
            self,
            tenant_id=tenant_id,
            start_date=start_date,
            end_date=end_date,
        )


__all__ = ["AICallLogRepository"]
