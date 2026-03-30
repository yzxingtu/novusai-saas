"""
Execution decision service / 执行决策服务
"""

from __future__ import annotations

from app.core.base_service import GlobalService, TenantService
from app.models.ai.execution_decision import ExecutionDecision
from app.repositories.ai.execution_decision_repository import (
    AdminExecutionDecisionRepository,
    ExecutionDecisionRepository,
)


class ExecutionDecisionService(
    TenantService[ExecutionDecision, ExecutionDecisionRepository]
):
    model = ExecutionDecision
    repository_class = ExecutionDecisionRepository

    async def record_decision(self, data: dict) -> ExecutionDecision:
        correlation_key = str(data.get("correlation_key") or "").strip()
        if not correlation_key:
            raise ValueError("correlation_key is required")

        existing = await self.repo.get_by_correlation_key(correlation_key)
        if existing is not None:
            existing.update_from_dict(data)
            await self.db.flush()
            return existing

        return await self.create(data)

    async def serialize_decision(self, decision: ExecutionDecision) -> dict:
        return decision.to_dict()

    async def serialize_decisions(
        self,
        decisions: list[ExecutionDecision],
    ) -> list[dict]:
        return [decision.to_dict() for decision in decisions]


class AdminExecutionDecisionService(
    GlobalService[ExecutionDecision, AdminExecutionDecisionRepository]
):
    model = ExecutionDecision
    repository_class = AdminExecutionDecisionRepository

    async def serialize_decision(self, decision: ExecutionDecision) -> dict:
        return decision.to_dict()

    async def serialize_decisions(
        self,
        decisions: list[ExecutionDecision],
    ) -> list[dict]:
        return [decision.to_dict() for decision in decisions]


__all__ = ["ExecutionDecisionService", "AdminExecutionDecisionService"]
