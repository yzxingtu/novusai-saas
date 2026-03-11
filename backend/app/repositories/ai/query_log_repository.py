"""
AI 数据查询审计日志 Repository / AI Query Log Repository

提供 AI 数据查询日志的存储和查询功能
Provides AI data query log storage and query functions.
"""

from sqlalchemy import case, func, select

from app.core.base_repository import TenantRepository
from app.models.ai.query_log import AIQueryLog


class AIQueryLogRepository(TenantRepository[AIQueryLog]):
    """
    AI 数据查询审计日志 Repository

    继承 TenantRepository 自动注入 tenant_id 过滤
    """

    model = AIQueryLog

    async def get_stats(self) -> dict:
        """
        获取查询日志统计信息

        Returns:
            统计数据字典
        """
        stmt = select(
            func.count(AIQueryLog.id).label("total"),
            func.sum(case(
                (AIQueryLog.status == "success", 1), else_=0
            )).label("success_count"),
            func.sum(case(
                (AIQueryLog.status == "failed", 1), else_=0
            )).label("failed_count"),
            func.sum(case(
                (AIQueryLog.status == "rejected", 1), else_=0
            )).label("rejected_count"),
            func.avg(AIQueryLog.duration_ms).label("avg_duration_ms"),
            func.avg(AIQueryLog.row_count).label("avg_row_count"),
        ).where(
            AIQueryLog.tenant_id == self.tenant_id,
            AIQueryLog.is_deleted.is_(False),
        )

        result = await self.db.execute(stmt)
        row = result.one()

        return {
            "total": row.total or 0,
            "success_count": row.success_count or 0,
            "failed_count": row.failed_count or 0,
            "rejected_count": row.rejected_count or 0,
            "avg_duration_ms": round(float(row.avg_duration_ms or 0), 1),
            "avg_row_count": round(float(row.avg_row_count or 0), 1),
        }


__all__ = ["AIQueryLogRepository"]
