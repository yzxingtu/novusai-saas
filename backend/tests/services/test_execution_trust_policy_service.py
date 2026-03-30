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


def test_execution_trust_policy_blocks_tool_above_risk_cap() -> None:
    policy_ref = {
        "allowed_tool_names": [],
        "tool_families": ["page_ops"],
        "risk_level_cap": "read",
    }

    assert not ExecutionTrustPolicyService.allows_tool(
        tool_name="invoke_page_operation",
        tool_family="page_ops",
        policy_ref=policy_ref,
    )


def test_execution_trust_policy_allows_family_with_safe_write_cap() -> None:
    policy_ref = {
        "allowed_tool_names": [],
        "tool_families": ["page_ops"],
        "risk_level_cap": "safe_write",
    }

    assert ExecutionTrustPolicyService.allows_tool(
        tool_name="invoke_page_operation",
        tool_family="page_ops",
        policy_ref=policy_ref,
    )

