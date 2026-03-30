"""
Execution decision repository / 执行决策仓储
"""

from sqlalchemy import and_, select

from app.core.base_repository import BaseRepository, TenantRepository
from app.models.ai.execution_decision import ExecutionDecision


class ExecutionDecisionRepository(TenantRepository[ExecutionDecision]):
    model = ExecutionDecision

    async def get_by_correlation_key(
        self,
        correlation_key: str,
    ) -> ExecutionDecision | None:
        result = await self.db.execute(
            select(self.model).where(
                and_(
                    self.model.tenant_id == self.tenant_id,
                    self.model.correlation_key == correlation_key,
                    self.model.is_deleted.is_(False),
                )
            )
        )
        return result.scalar_one_or_none()


class AdminExecutionDecisionRepository(BaseRepository[ExecutionDecision]):
    model = ExecutionDecision


__all__ = ["ExecutionDecisionRepository", "AdminExecutionDecisionRepository"]
