"""Sentinel tests for the extracted diagnostics support seam."""

from __future__ import annotations

from app.services.ai.conversation_diagnostics_projector_support import (
    extract_turn_diagnostics_from_metadata,
)


def test_extract_turn_diagnostics_preserves_explicit_false_flags() -> None:
    payload = extract_turn_diagnostics_from_metadata(
        {
            "turn_record": {
                "selected_tool_names": ["web_search"],
                "metadata": {
                    "recovered_via_retry": False,
                    "sync_rescue": False,
                    "should_record_call_log": False,
                    "turn_diagnostics": {
                        "routing": {"candidate_tool_names": ["web_search"]},
                        "failures": {
                            "failure_kind": "provider_timeout",
                            "provider_events": [{"kind": "provider_timeout"}],
                        },
                    },
                },
            },
            "last_run_summary": {
                "recovered_via_retry": True,
                "sync_rescue": True,
                "should_record_call_log": True,
            },
        }
    )

    assert payload["selected_tool_names"] == ["web_search"]
    assert payload["candidate_tool_names"] == ["web_search"]
    assert payload["failure_kind"] == "provider_timeout"
    assert payload["provider_events"] == [{"kind": "provider_timeout"}]
    assert payload["recovered_via_retry"] is False
    assert payload["sync_rescue"] is False
    assert payload["should_record_call_log"] is False


def test_extract_turn_diagnostics_keeps_budget_and_retry_projection() -> None:
    payload = extract_turn_diagnostics_from_metadata(
        {
            "turn_record": {
                "execution_path": "deep",
                "budget": {
                    "status": "exited",
                    "exit_reason": "tool_round_budget_exceeded",
                },
                "metadata": {
                    "turn_diagnostics": {
                        "recovery": {
                            "partial_exit_reason": "tool_round_budget_exceeded",
                            "retry_events": [
                                {
                                    "action": "retry_intent",
                                    "target_intent_id": "intent-2",
                                    "retry_family": "page_ops",
                                    "allowed_tool_names": ["ui_get_snapshot"],
                                }
                            ],
                        }
                    }
                },
            }
        }
    )

    assert payload["execution_path"] == "deep"
    assert payload["budget_status"] == "exited"
    assert payload["budget_exit_reason"] == "tool_round_budget_exceeded"
    assert payload["partial_exit_reason"] == "tool_round_budget_exceeded"
    assert payload["retry_events"] == [
        {
            "action": "retry_intent",
            "target_intent_id": "intent-2",
            "retry_family": "page_ops",
            "allowed_tool_names": ["ui_get_snapshot"],
            "completed_intent_ids": [],
            "unfinished_intent_ids": [],
            "reason": None,
            "provider_failure_kind": None,
            "metadata": {},
        }
    ]
