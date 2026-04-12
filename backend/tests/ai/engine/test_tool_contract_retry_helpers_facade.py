from __future__ import annotations

from app.ai.engine import (
    tool_contract_breach_analysis,
    tool_contract_diagnostics,
    tool_contract_evidence,
    tool_contract_retry_policies,
)
from app.ai.engine import (
    tool_contract_retry_helpers as facade,
)


def test_tool_contract_retry_helpers_is_thin_facade() -> None:
    mapping = [
        ("analyze_post_tool_contract_breach", tool_contract_breach_analysis),
        ("build_post_tool_retry_policy", tool_contract_retry_policies),
        ("collect_tool_family_evidence", tool_contract_evidence),
        ("log_tool_contract_diagnostics", tool_contract_diagnostics),
        ("log_tool_contract_diagnostics_default", tool_contract_diagnostics),
        ("log_web_research_contract_diagnostics", tool_contract_diagnostics),
        ("log_web_research_contract_diagnostics_default", tool_contract_diagnostics),
        ("resolve_breach_retry_policy", tool_contract_retry_policies),
        ("should_retry_tool_contract_breach", tool_contract_retry_policies),
        ("should_retry_web_research_contract_breach", tool_contract_retry_policies),
    ]

    for name, module in mapping:
        assert getattr(facade, name) is getattr(module, name)
