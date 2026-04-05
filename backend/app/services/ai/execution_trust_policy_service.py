"""
Execution trust policy service / 执行信任策略服务
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from app.core.base_model import utc_now
from app.core.base_service import TenantService
from app.enums.agent import ActionLevelEnum
from app.models.ai.execution_trust_policy import ExecutionTrustPolicy
from app.repositories.ai.execution_trust_policy_repository import (
    ExecutionTrustPolicyRepository,
)

_RISK_ORDER = {
    ActionLevelEnum.READ.value: 0,
    ActionLevelEnum.SAFE_WRITE.value: 1,
    ActionLevelEnum.DANGEROUS.value: 2,
}


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
            )
            if row.tool_family:
                tool_families.add(str(row.tool_family).strip())
            if row.risk_level_cap and self._risk_rank(
                row.risk_level_cap
            ) > self._risk_rank(risk_cap):
                risk_cap = row.risk_level_cap

        return {
            "policy_ids": source_policy_ids,
            "allowed_tool_names": sorted(allowed_tool_names),
            "tool_families": sorted(tool_families),
            "risk_level_cap": risk_cap,
        }

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
        tool_family = self.tool_family_for_name(tool_name)
        risk_level_cap = self.tool_risk_level(
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
            if self._risk_rank(risk_level_cap) > self._risk_rank(
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

    @staticmethod
    def _risk_rank(value: str | None) -> int:
        return _RISK_ORDER.get(str(value or "").strip(), -1)

    @classmethod
    def tool_risk_level(
        cls,
        *,
        tool_name: str,
        tool_family: str | None,
    ) -> str:
        normalized_name = str(tool_name or "").strip().lower()
        normalized_family = str(tool_family or "").strip().lower()

        if normalized_family in {"web_research", "weather"}:
            return ActionLevelEnum.READ.value

        if normalized_name in {
            "get_page_context",
            "list_page_operations",
        } or normalized_name.startswith(
            (
                "pageop_get_",
                "pageop_read_",
                "pageop_list_",
            )
        ):
            return ActionLevelEnum.READ.value

        if normalized_family == "page_ops" or normalized_name.startswith("pageop_"):
            return ActionLevelEnum.SAFE_WRITE.value

        if normalized_name.startswith(("http", "email", "code_", "toolkit")):
            return ActionLevelEnum.DANGEROUS.value

        return ActionLevelEnum.SAFE_WRITE.value

    @staticmethod
    def tool_family_for_name(tool_name: str) -> str:
        normalized = str(tool_name or "").strip().lower()
        if normalized in {"web_search", "fetch_url"}:
            return "web_research"
        if normalized in {"get_current_weather", "get_weather_forecast"}:
            return "weather"
        if normalized in {
            "get_page_context",
            "invoke_page_operation",
            "list_page_operations",
        } or normalized.startswith("pageop_"):
            return "page_ops"
        return "none"

    @classmethod
    def allows_tool(
        cls,
        *,
        tool_name: str,
        tool_family: str | None,
        policy_ref: dict[str, Any] | None,
    ) -> bool:
        if not isinstance(policy_ref, dict):
            return False
        allowed_tool_names = {
            str(name).strip()
            for name in (policy_ref.get("allowed_tool_names") or [])
            if str(name).strip()
        }
        allowed_families = {
            str(name).strip()
            for name in (policy_ref.get("tool_families") or [])
            if str(name).strip()
        }
        if tool_name in allowed_tool_names:
            return cls._risk_rank(
                cls.tool_risk_level(tool_name=tool_name, tool_family=tool_family)
            ) <= cls._risk_rank(policy_ref.get("risk_level_cap"))
        if tool_family and tool_family in allowed_families:
            return cls._risk_rank(
                cls.tool_risk_level(tool_name=tool_name, tool_family=tool_family)
            ) <= cls._risk_rank(policy_ref.get("risk_level_cap"))
        return False


__all__ = ["ExecutionTrustPolicyService"]
