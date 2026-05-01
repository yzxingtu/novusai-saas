from __future__ import annotations

from app.ai.engine.types import ExecutionResult
from app.services.ai.agent_chat_turn_projection import (
    build_context_diagnostics,
    build_last_run_summary,
    extract_turn_meta_from_result,
)


def _result_with_turn_record() -> ExecutionResult:
    return ExecutionResult(
        success=False,
        output="partial output",
        messages=[],
        tool_results=[],
        total_tokens=123,
        duration_ms=456,
        error="interrupted",
        partial=True,
        interrupted=True,
        completion_reason="interrupted",
        rag_source_kinds=["memory"],
        tool_planner={"family": "memory"},
        turn_record={
            "metadata": {
                "turn_diagnostics": {
                    "active_intent_id": "intent-1",
                    "context_sources": [{"kind": "memory", "name": "profile"}],
                    "protocol_path": "responses",
                    "selected_skill_names": ["runtime.memory"],
                    "selected_tool_names": ["save_memory"],
                    "turn_skill_activation": {
                        "applied": True,
                        "reason": "explicit_skill_mention",
                        "selected_skill_names": ["runtime.memory"],
                        "selected_tool_names": ["save_memory"],
                        "inventory_selected_skill_names": [
                            "runtime.memory",
                            "runtime.web_research",
                        ],
                        "inventory_selected_tool_names": [
                            "save_memory",
                            "web_search",
                        ],
                    },
                    "turn_outcome": "partial",
                }
            },
            "termination_reason": "interrupted",
        },
    )


def test_turn_projection_uses_default_diagnostics_projector() -> None:
    result = _result_with_turn_record()

    turn_meta = extract_turn_meta_from_result(result)
    context_payload = build_context_diagnostics(
        result,
        interaction_mode_effective="confirm",
    )
    summary_payload = build_last_run_summary(
        result,
        interaction_mode_effective="confirm",
        downgrade_reason=None,
    )

    assert turn_meta["turn_outcome"] == "partial"
    assert turn_meta["termination_reason"] == "interrupted"
    assert turn_meta["protocol_path"] == "responses"
    assert turn_meta["turn_skill_activation"]["reason"] == "explicit_skill_mention"
    assert context_payload["selected_tool_names"] == ["save_memory"]
    assert context_payload["turn_skill_activation"]["inventory_skill_count"] == 2
    assert context_payload["context_sources"][0]["kind"] == "memory"
    assert summary_payload["termination_reason"] == "interrupted"
    assert summary_payload["selected_skill_names"] == ["runtime.memory"]
    assert summary_payload["turn_skill_activation"]["selected_tool_names"] == [
        "save_memory"
    ]


def test_turn_projection_omits_selected_names_when_live_selection_is_explicitly_empty() -> (
    None
):
    result = ExecutionResult(
        success=False,
        output="upstream failure",
        messages=[],
        tool_results=[],
        total_tokens=17,
        duration_ms=31,
        error="tool_round_failed",
        completion_reason="tool_round_failed",
        turn_record={
            "selected_tool_names": [],
            "selected_skill_names": [],
            "turn_outcome": "failed",
            "termination_reason": "tool_round_failed",
            "metadata": {
                "turn_diagnostics": {
                    "selected_tool_names": ["crm_lookup", "web_search"],
                    "selected_skill_names": ["Workflow Skill", "Research Skill"],
                    "turn_skill_activation": {
                        "applied": True,
                        "reason": "runtime_policy",
                        "selected_tool_names": [],
                        "selected_skill_names": [],
                        "inventory_selected_tool_names": [
                            "crm_lookup",
                            "web_search",
                        ],
                        "inventory_selected_skill_names": [
                            "Workflow Skill",
                            "Research Skill",
                        ],
                    },
                }
            },
        },
    )

    context_payload = build_context_diagnostics(
        result,
        interaction_mode_effective="trusted_auto",
    )
    summary_payload = build_last_run_summary(
        result,
        interaction_mode_effective="trusted_auto",
        downgrade_reason=None,
    )

    assert "selected_tool_names" not in context_payload
    assert "selected_skill_names" not in context_payload
    assert "selected_tool_names" not in summary_payload
    assert "selected_skill_names" not in summary_payload
