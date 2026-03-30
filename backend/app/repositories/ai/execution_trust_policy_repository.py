"""
Execution trust policy repository / 执行信任策略仓储
"""

from __future__ import annotations

import inspect
from datetime import datetime

from sqlalchemy import or_, select

from app.core.base_repository import TenantRepository
from app.models.ai.execution_trust_policy import ExecutionTrustPolicy


class ExecutionTrustPolicyRepository(TenantRepository[ExecutionTrustPolicy]):
    model = ExecutionTrustPolicy

    async def get_active_for_scope(
        self,
        *,
        conversation_id: int | None,
        agent_id: int | None,
        operator_id: int | None,
        operator_type: str | None,
        now: datetime | None = None,
    ) -> list[ExecutionTrustPolicy]:
        stmt = (
            select(self.model)
            .where(
                self.model.tenant_id == self.tenant_id,
                self.model.is_deleted.is_(False),
                self.model.is_active.is_(True),
            )
            .order_by(self.model.created_at.desc())
        )

        if conversation_id is not None:
            stmt = stmt.where(
                or_(
                    self.model.conversation_id.is_(None),
                    self.model.conversation_id == conversation_id,
                )
            )
        if agent_id is not None:
            stmt = stmt.where(
                or_(self.model.agent_id.is_(None), self.model.agent_id == agent_id)
            )
        if operator_id is not None:
            stmt = stmt.where(
                or_(
                    self.model.operator_id.is_(None),
                    self.model.operator_id == operator_id,
                )
            )
        if operator_type:
            stmt = stmt.where(
                or_(
                    self.model.operator_type.is_(None),
                    self.model.operator_type == operator_type,
                )
            )
        if now is not None:
            stmt = stmt.where(
                or_(self.model.expires_at.is_(None), self.model.expires_at > now)
            )

        result = await self.db.execute(stmt)
        scalars_result = result.scalars()
        if inspect.isawaitable(scalars_result):
            scalars_result = await scalars_result
        if hasattr(scalars_result, "all"):
            rows = scalars_result.all()
            if inspect.isawaitable(rows):
                rows = await rows
            return list(rows)
        return list(scalars_result)


__all__ = ["ExecutionTrustPolicyRepository"]
