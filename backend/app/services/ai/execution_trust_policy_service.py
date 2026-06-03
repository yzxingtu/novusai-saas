"""
Execution trust policy service / 执行信任策略服务
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from app.ai.runtime.execution_trust_policy import (
    build_policy_ref as runtime_build_policy_ref,
)
from app.ai.runtime.execution_trust_policy import (
    risk_rank as runtime_risk_rank,
)
from app.ai.runtime.execution_trust_policy import (
    tool_family_for_name as runtime_tool_family_for_name,
)
from app.ai.runtime.execution_trust_policy import (
    tool_risk_level as runtime_tool_risk_level,
)
from app.core.base_model import utc_now
from app.core.base_service import TenantService
from app.enums.agent import ActionLevelEnum
from app.models.ai.execution_trust_policy import ExecutionTrustPolicy
from app.repositories.ai.execution_trust_policy_repository import (
    ExecutionTrustPolicyRepository,
)
from app.schemas.ai.invalid_ai_runtime_input import (
    is_invalid_ai_runtime_tool_family,
    is_invalid_ai_runtime_tool_name,
)


class ExecutionTrustPolicyService(
    TenantService[ExecutionTrustPolicy, ExecutionTrustPolicyRepository]
):
    model = ExecutionTrustPolicy
    repository_class = ExecutionTrustPolicyRepository

    async def resolve_runtime_policy(
        self,
        *,
        conversation_id: int | None,
        agent_id: int | None,
        operator_id: int | None,
        operator_type: str | None,
        now: datetime | None = None,
    ) -> dict[str, Any] | None:
        rows = await self.repo.get_active_for_scope(
            conversation_id=conversation_id,
            agent_id=agent_id,
            operator_id=operator_id,
            operator_type=operator_type,
            now=now or utc_now(),
        )
        if not rows:
            return None

        allowed_tool_names: set[str] = set()
        tool_families: set[str] = set()
        risk_cap = ActionLevelEnum.READ.value
        source_policy_ids: list[int] = []

        for row in rows:
            source_policy_ids.append(int(row.id))
            allowed_tool_names.update(
                str(name).strip()
                for name in (row.allowed_tool_names or [])
                if str(name).strip()
                and not is_invalid_ai_runtime_tool_name(str(name).strip())
            )
            tool_family = str(row.tool_family or "").strip()
            if tool_family and not is_invalid_ai_runtime_tool_family(tool_family):
                tool_families.add(tool_family)
            if row.risk_level_cap and runtime_risk_rank(
                row.risk_level_cap
            ) > runtime_risk_rank(risk_cap):
                risk_cap = row.risk_level_cap

        return runtime_build_policy_ref(
            policy_ids=source_policy_ids,
            allowed_tool_names=sorted(allowed_tool_names),
            tool_families=sorted(tool_families),
            risk_level_cap=risk_cap,
        )

    async def grant_conversation_tool_trust(
        self,
        *,
        conversation_id: int,
        agent_id: int,
        operator_id: int | None,
        operator_type: str | None,
        tool_name: str,
        granted_by: int | None,
        grant_reason: str | None = None,
    ) -> ExecutionTrustPolicy:
        tool_family = runtime_tool_family_for_name(tool_name)
        risk_level_cap = runtime_tool_risk_level(
            tool_name=tool_name,
            tool_family=tool_family,
        )

        existing_rows = await self.repo.get_active_for_scope(
            conversation_id=conversation_id,
            agent_id=agent_id,
            operator_id=operator_id,
            operator_type=operator_type,
            now=utc_now(),
        )
        existing = next(
            (
                row
                for row in existing_rows
                if row.conversation_id == conversation_id
                and row.agent_id == agent_id
                and row.operator_id == operator_id
                and (row.operator_type or None) == (operator_type or None)
                and (row.tool_family or "") == tool_family
            ),
            None,
        )

        if existing is not None:
            next_names = {
                str(name).strip()
                for name in (existing.allowed_tool_names or [])
                if str(name).strip()
            }
            next_names.add(tool_name)
            existing.allowed_tool_names = sorted(next_names)
            if runtime_risk_rank(risk_level_cap) > runtime_risk_rank(
                existing.risk_level_cap
            ):
                existing.risk_level_cap = risk_level_cap
            existing.granted_by = granted_by
            existing.grant_reason = grant_reason or existing.grant_reason
            existing.updated_at = utc_now()
            await self.db.flush()
            return existing

        return await self.create(
            {
                "tenant_id": self.tenant_id,
                "conversation_id": conversation_id,
                "agent_id": agent_id,
                "operator_id": operator_id,
                "operator_type": operator_type,
                "tool_family": tool_family,
                "allowed_tool_names": [tool_name],
                "risk_level_cap": risk_level_cap,
                "is_active": True,
                "granted_by": granted_by,
                "grant_reason": grant_reason,
                "metadata_": {},
            }
        )

    async def has_active_conversation_trust(
        self,
        *,
        conversation_id: int,
        agent_id: int | None,
        operator_id: int | None,
        operator_type: str | None,
    ) -> bool:
        rows = await self.repo.get_active_for_scope(
            conversation_id=conversation_id,
            agent_id=agent_id,
            operator_id=operator_id,
            operator_type=operator_type,
            now=utc_now(),
        )
        return any(
            getattr(row, "conversation_id", None) == conversation_id for row in rows
        )


__all__ = ["ExecutionTrustPolicyService"]
