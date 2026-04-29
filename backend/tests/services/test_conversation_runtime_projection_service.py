"""Test type: behavioral.

Verifies retained conversation runtime projections preserve a partial
turn_outcome even when the stored turn_flow ends in a failed/error terminal
stage, while keeping conversation_outcome=failed for the overall turn result.
"""

from __future__ import annotations

from app.services.ai.conversation_runtime_projection_service import (
    ConversationRuntimeProjectionService,
)


def _partial_provider_error_message() -> dict[str, object]:
    return {
        "token_count": 5,
        "created_at": "2026-04-27T06:15:02+08:00",
        "provider_name": "ASXS",
        "model_name": "gpt-5.5-xhigh",
        "metadata": {
            "partial": True,
            "interrupted": False,
            "completion_reason": "provider_error",
            "context_diagnostics": {
                "turn_outcome": "partial",
                "conversation_outcome": "failed",
                "termination_reason": "provider_error",
                "selected_tool_names": [],
                "selected_skill_names": [],
                "failure_kind": "provider_http_5xx",
                "partial_exit_reason": "provider_error",
                "candidate_tool_names": ["get_current_time"],
            },
            "last_run_summary": {
                "turn_outcome": "partial",
                "conversation_outcome": "failed",
                "termination_reason": "provider_error",
                "selected_tool_names": [],
                "selected_skill_names": [],
                "failure_kind": "provider_http_5xx",
                "partial_exit_reason": "provider_error",
                "candidate_tool_names": ["get_current_time"],
            },
            "turn_record": {
                "turn_outcome": "partial",
                "conversation_outcome": "failed",
                "termination_reason": "provider_error",
                "protocol_path": "responses",
                "execution_path": "fast",
                "selected_tool_names": [],
                "selected_skill_names": [],
                "candidate_tool_names": ["get_current_time"],
                "failure_kind": "provider_http_5xx",
                "partial_exit_reason": "provider_error",
            },
            "turn_flow": {
                "timeline": [
                    {
                        "id": "tool_execution",
                        "type": "tool_execution",
                        "status": "completed",
                    },
                    {
                        "id": "failed",
                        "type": "failed",
                        "status": "error",
                    },
                ],
                "completion_reason": "provider_error",
                "interrupted": False,
                "error_surface": {
                    "failure_kind": "provider_http_5xx",
                },
            },
        },
    }


def test_build_retained_runtime_projection_keeps_partial_turn_truth() -> None:
    message_payload = _partial_provider_error_message()

    context_diagnostics = (
        ConversationRuntimeProjectionService.build_context_diagnostics_payload(
            message_payload,
            compaction_snapshot=None,
            interaction_mode_effective="trusted_auto",
        )
    )
    last_run_summary = (
        ConversationRuntimeProjectionService.build_last_run_summary_payload(
            message_payload,
            interaction_mode_effective="trusted_auto",
            downgrade_reason=None,
        )
    )

    assert context_diagnostics["turn_outcome"] == "partial"
    assert context_diagnostics["conversation_outcome"] == "failed"
    assert context_diagnostics["selected_tool_names"] == []
    assert context_diagnostics["selected_skill_names"] == []
    assert context_diagnostics["failure_kind"] == "provider_http_5xx"

    assert last_run_summary["turn_outcome"] == "partial"
    assert last_run_summary["conversation_outcome"] == "failed"
    assert last_run_summary["selected_tool_names"] == []
    assert last_run_summary["selected_skill_names"] == []
    assert last_run_summary["failure_kind"] == "provider_http_5xx"
