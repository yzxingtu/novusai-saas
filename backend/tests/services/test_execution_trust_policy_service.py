"""
Test type: behavioral
Scope: runtime trust-policy allow/deny decisions for tool names and semantic families.
Mock strategy: no mocks; pure policy helper calls with observable boolean outcomes.
"""

from pathlib import Path

from app.ai.runtime.execution_trust_policy import (
    allows_tool,
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
        allows_tool(
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
        allows_tool(
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
