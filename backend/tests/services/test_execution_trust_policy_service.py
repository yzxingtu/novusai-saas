"""
Test type: behavioral
Scope: runtime trust-policy allow/deny decisions for tool names and semantic families.
Mock strategy: no mocks; pure policy helper calls with observable boolean outcomes.
"""

from pathlib import Path
from types import SimpleNamespace

import pytest

from app.ai.engine.types import ExecutionRequest
from app.ai.types import ChatMessage
from app.services.ai.execution_trust_policy_service import (
    ExecutionTrustPolicyService,
)


def test_execution_trust_policy_allows_named_read_tool() -> None:
    policy_ref = {
        "allowed_tool_names": ["web_search"],
        "tool_families": [],
        "risk_level_cap": "read",
    }

    assert ExecutionTrustPolicyService.allows_tool(
        tool_name="web_search",
        tool_family="web_research",
        policy_ref=policy_ref,
    )


def test_execution_trust_policy_allows_named_safe_write_tool_with_sufficient_risk_cap() -> (
    None
):
    policy_ref = {
        "allowed_tool_names": ["crm_update_record"],
        "tool_families": [],
        "risk_level_cap": "dangerous",
    }

    assert (
        ExecutionTrustPolicyService.allows_tool(
            tool_name="crm_update_record",
            tool_family="data_ops",
            policy_ref=policy_ref,
        )
        is True
    )


def test_execution_trust_policy_allows_family_when_policy_lists_family() -> None:
    policy_ref = {
        "allowed_tool_names": [],
        "tool_families": ["data_ops"],
        "risk_level_cap": "dangerous",
    }

    assert (
        ExecutionTrustPolicyService.allows_tool(
            tool_name="custom_data_update",
            tool_family="data_ops",
            policy_ref=policy_ref,
        )
        is True
    )


def test_base_engine_uses_runtime_trust_policy_helper_only() -> None:
    backend_root = Path(__file__).resolve().parents[2]
    source = (backend_root / "app/ai/engine/tool_policy_trust_helpers.py").read_text(
        encoding="utf-8"
    )

    assert "app.services.ai.execution_trust_policy_service" not in source
    assert "app.ai.runtime.execution_trust_policy" in source


@pytest.mark.asyncio
async def test_resolve_runtime_policy_filters_legacy_page_operation_trust() -> None:
    """Regression: legacy page-operation trust rows must not crash AgentChat."""

    class _Repo:
        async def get_active_for_scope(self, **_kwargs):
            return [
                SimpleNamespace(
                    id=4,
                    allowed_tool_names=["pageop_create_record", "web_search"],
                    tool_family="page_ops",
                    risk_level_cap="safe_write",
                )
            ]

    service = object.__new__(ExecutionTrustPolicyService)
    service.repo = _Repo()

    policy_ref = await service.resolve_runtime_policy(
        conversation_id=9,
        agent_id=55,
        operator_id=1,
        operator_type="admin",
    )

    assert policy_ref == {
        "policy_ids": [4],
        "allowed_tool_names": ["web_search"],
        "tool_families": [],
        "risk_level_cap": "safe_write",
    }
    ExecutionRequest(
        agent_id=55,
        tenant_id=0,
        messages=[ChatMessage(role="user", content="rewrite selection")],
        trust_policy_ref=policy_ref,
    )
