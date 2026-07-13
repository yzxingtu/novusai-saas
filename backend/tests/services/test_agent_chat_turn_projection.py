"""Test type: behavioral
Scope: agent-chat turn diagnostics projection from retained runtime metadata.
Mocked dependencies: none; projection helpers run their real shaping logic.
"""

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
                        "reason": "react_autonomous",
                        "selected_skill_names": ["runtime.memory"],
                        "selected_tool_names": ["save_memory"],
                        "inventory_selected_skill_names": [
                            "runtime.memory",
                            "runtime.crm",
                        ],
                        "inventory_selected_tool_names": [
                            "save_memory",
                            "crm_lookup",
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
    assert turn_meta["turn_skill_activation"]["reason"] == "react_autonomous"
    assert context_payload["selected_tool_names"] == ["save_memory"]
    assert context_payload["turn_skill_activation"]["inventory_skill_count"] == 2
    assert context_payload["context_sources"][0]["kind"] == "memory"
    assert summary_payload["termination_reason"] == "interrupted"
    assert summary_payload["selected_skill_names"] == ["runtime.memory"]
    assert summary_payload["turn_skill_activation"]["selected_tool_names"] == [
        "save_memory"
    ]
