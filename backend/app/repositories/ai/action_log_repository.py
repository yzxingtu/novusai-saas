"""
AI 操作审计日志 Repository / AI Action Log Repository

提供 AI 操作审计日志的查询和统计功能
Provides AI action audit log query and statistics functions.
"""

from sqlalchemy import case, func, select

from app.core.base_repository import TenantRepository
from app.enums.agent import ActionLevelEnum, ActionStatusEnum
from app.models.ai.action_log import AIActionLog


class AIActionLogRepository(TenantRepository[AIActionLog]):
    """
    AI 操作审计日志 Repository / AI Action Log Repository.

    继承 TenantRepository 自动注入 tenant_id 过滤
    """

    model = AIActionLog

    async def get_stats(self) -> dict:
        """
        获取审计日志统计信息 / Get action log statistics.

        返回：总操作数、各状态计数、各级别计数、各类型计数

        Returns:
            统计数据字典
        """
        stmt = select(
            func.count(AIActionLog.id).label("total"),
            func.sum(case(
                (AIActionLog.status == ActionStatusEnum.SUCCESS.value, 1), else_=0
            )).label("success_count"),
            func.sum(case(
                (AIActionLog.status == ActionStatusEnum.FAILED.value, 1), else_=0
            )).label("failed_count"),
            func.sum(case(
                (AIActionLog.status == ActionStatusEnum.REJECTED.value, 1), else_=0
            )).label("rejected_count"),
            func.sum(case(
                (AIActionLog.status == ActionStatusEnum.PENDING_CONFIRM.value, 1), else_=0
            )).label("pending_count"),
            func.sum(case(
                (AIActionLog.action_level == ActionLevelEnum.READ.value, 1), else_=0
            )).label("level_read"),
            func.sum(case(
                (AIActionLog.action_level == ActionLevelEnum.SAFE_WRITE.value, 1), else_=0
            )).label("level_safe_write"),
            func.sum(case(
                (AIActionLog.action_level == ActionLevelEnum.DANGEROUS.value, 1), else_=0
            )).label("level_dangerous"),
            func.avg(AIActionLog.duration_ms).label("avg_duration_ms"),
        ).where(
            AIActionLog.tenant_id == self.tenant_id,
            AIActionLog.is_deleted.is_(False),
        )

        result = await self.db.execute(stmt)
        row = result.one()

        return {
            "total": row.total or 0,
            "success_count": row.success_count or 0,
            "failed_count": row.failed_count or 0,
            "rejected_count": row.rejected_count or 0,
            "pending_count": row.pending_count or 0,
            "level_read": row.level_read or 0,
            "level_safe_write": row.level_safe_write or 0,
            "level_dangerous": row.level_dangerous or 0,
            "avg_duration_ms": round(float(row.avg_duration_ms or 0), 1),
        }

    async def get_type_distribution(self) -> list[dict]:
        """
        获取操作类型分布（用于饼图）/ Get action type distribution (for pie chart).

        Returns:
            [{action_type: str, count: int}, ...]
        """
        stmt = (
            select(
                AIActionLog.action_type,
                func.count(AIActionLog.id).label("count"),
            )
            .where(
                AIActionLog.tenant_id == self.tenant_id,
                AIActionLog.is_deleted.is_(False),
            )
            .group_by(AIActionLog.action_type)
            .order_by(func.count(AIActionLog.id).desc())
        )

        result = await self.db.execute(stmt)
        return [
            {"action_type": row.action_type, "count": row.count}
            for row in result.all()
        ]


__all__ = ["AIActionLogRepository"]
