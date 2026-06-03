"""
Test type: behavioral
Scope: CLI conversation diagnostics rendering and compact projection with retired
page-awareness metadata removed from live diagnostic output.
Mock strategy: no external services; CLI projection helpers run directly.
"""

from __future__ import annotations

from app.cli_commands.ai_render import (
    _build_ai_conversation_compact_diagnostics,
    _extract_turn_diagnostics_from_call_log_metadata,
    _render_ai_conversation_diagnostics_text,
)


def test_extract_turn_diagnostics_from_call_log_metadata_normalizes_provider_connection_failure() -> (
    None
):
    diagnostics = _extract_turn_diagnostics_from_call_log_metadata(
        {
            "turn_diagnostics": {
                "turn_outcome": "failed",
                "termination_reason": "error",
                "turn_record": {
                    "turn_outcome": "failed",
                    "termination_reason": "error",
                    "protocol_path": "responses",
                    "metadata": {
                        "protocol_fallback_blocked_reason": "provider_connection_error",
                        "stream_failure_error_type": "ProviderConnectionError",
                    },
                },
            }
        }
    )

    assert diagnostics["turn_outcome"] == "failed"
    assert diagnostics["termination_reason"] == "provider_unavailable"
    assert diagnostics["failure_kind"] == "provider_unavailable"
    assert diagnostics["protocol_path"] == "responses"


def test_cli_compact_diagnostics_hydrates_required_fields_from_nested_turn_record() -> (
    None
):
    snapshot = {
        "conversation": {"id": 1237},
        "diagnostics": {
            "source": "assistant_turn_record",
            "turn_outcome": "failed",
            "termination_reason": "provider_unavailable",
            "protocol_path": "responses",
        },
        "recent_messages": [
            {
                "role": "assistant",
                "content": "",
                "metadata": {
                    "turn_record": {
                        "turn_outcome": "failed",
                        "termination_reason": "provider_unavailable",
                        "protocol_path": "responses",
                        "metadata": {
                            "turn_diagnostics": {
                                "path_decision": {
                                    "path": "normal",
                                    "reason": "bounded_multi_intent",
                                    "all_shortcircuit": False,
                                    "intent_count": 1,
                                },
                                "capability_injection_decision": {
                                    "skills_injected": False,
                                    "kb_injected": False,
                                    "memory_injected": False,
                                    "bypass_reason": None,
                                },
                                "tool_filtering": {
                                    "all_tools_count": 15,
                                    "candidate_tools_count": 3,
                                    "filtering_reason": "intent_scoped",
                                },
                                "recovery_chain": [],
                            }
                        },
                    }
                },
            }
        ],
    }

    compact = _build_ai_conversation_compact_diagnostics(snapshot)
    text = _render_ai_conversation_diagnostics_text(snapshot)

    assert compact["path_decision"] == {
        "path": "normal",
        "reason": "bounded_multi_intent",
        "all_shortcircuit": False,
        "intent_count": 1,
    }
    assert compact["capability_injection"] == {
        "skills_injected": False,
        "kb_injected": False,
        "memory_injected": False,
        "bypass_reason": None,
    }
    assert compact["tool_filtering"] == {
        "all_tools_count": 15,
        "candidate_tools_count": 3,
        "filtering_reason": "intent_scoped",
    }
    assert compact["recovery_chain"] == []
    assert "path_decision=" in text
    assert "capability_injection=" in text
    assert "tool_filtering=" in text
    assert "recovery_chain=[]" in text


def test_extract_turn_diagnostics_preserves_provider_failure_after_partial_progress() -> (
    None
):
    diagnostics = _extract_turn_diagnostics_from_call_log_metadata(
        {
            "turn_diagnostics": {
                "execution_path": "normal",
                "failures": {
                    "failure_kind": "provider_http_5xx",
                    "provider_events": [
                        {"kind": "provider_http_5xx", "status_code": 503}
                    ],
                },
                "turn_record": {
                    "turn_outcome": "partial",
                    "termination_reason": "provider_failure_after_partial_progress",
                    "protocol_path": "responses",
                    "metadata": {},
                },
            }
        }
    )

    assert diagnostics["turn_outcome"] == "partial"
    assert (
        diagnostics["termination_reason"] == "provider_failure_after_partial_progress"
    )
    assert diagnostics["failure_kind"] == "provider_http_5xx"


def test_cli_compact_diagnostics_marks_untrusted_final_output_source_as_failed() -> (
    None
):
    snapshot = {
        "conversation": {"id": 1215},
        "diagnostics": {
            "source": "assistant_turn_record",
            "turn_outcome": "success",
            "termination_reason": "completed",
            "protocol_path": "responses",
            "execution_path": "normal",
            "budget_status": "ok",
            "final_output_source": "tool_evidence_completed",
        },
        "recent_messages": [
            {
                "id": 7568,
                "role": "assistant",
                "content": "Fetched reddit.json",
                "metadata": {
                    "completion_reason": "completed",
                    "turn_record": {
                        "turn_outcome": "success",
                        "termination_reason": "completed",
                        "protocol_path": "responses",
                        "final_output_source": "tool_evidence_completed",
                    },
                },
            }
        ],
    }

    compact = _build_ai_conversation_compact_diagnostics(snapshot)

    assert compact["turn_outcome"] == "failed"
    assert compact["termination_reason"] == "completed"
    assert compact["failure_kind"] == "untrusted_final_output_source"
    assert compact["final_output_source"] == "tool_evidence_completed"


def test_cli_compact_diagnostics_derives_elapsed_budget_overrun_from_historical_snapshot() -> (
    None
):
    snapshot = {
        "conversation": {"id": 1215},
        "diagnostics": {
            "source": "assistant_turn_record",
            "turn_outcome": "success",
            "termination_reason": "completed",
            "protocol_path": "responses",
            "execution_path": "normal",
            "budget": {
                "status": "ok",
                "limits": {"max_elapsed_ms": 60000},
                "usage": {"elapsed_ms_used": 135500},
            },
            "budget_status": "ok",
            "final_output_source": "tool_evidence_completed",
        },
    }

    compact = _build_ai_conversation_compact_diagnostics(snapshot)
    text = _render_ai_conversation_diagnostics_text(snapshot)

    assert compact["budget_status"] == "exited"
    assert compact["budget_exit_reason"] == "elapsed_budget_exceeded"
    assert compact["budget"]["usage"]["elapsed_over_limit"] is True
    assert compact["budget"]["usage"]["elapsed_over_limit_ms"] == 75500
    assert "budget_status=exited" in text
    assert "budget_exit_reason=elapsed_budget_exceeded" in text


def test_cli_compact_diagnostics_aligns_turn_outcome_with_projected_turn_flow_failure() -> (
    None
):
    snapshot = {
        "conversation": {"id": 668},
        "recent_messages": [
            {
                "role": "assistant",
                "content": "已输出部分内容",
                "metadata": {
                    "turn_record": {
                        "turn_outcome": "partial",
                        "termination_reason": "provider_failure_after_partial_progress",
                        "metadata": {
                            "turn_diagnostics": {
                                "failures": {
                                    "failure_kind": "provider_http_5xx",
                                }
                            }
                        },
                    },
                    "turn_flow": {
                        "timeline": [
                            {
                                "id": "answer_assembly",
                                "type": "answer_assembly",
                                "status": "completed",
                                "title": "答案生成",
                                "summary": "已生成最终答复",
                            },
                            {
                                "id": "terminal",
                                "type": "completed",
                                "status": "completed",
                                "title": "本轮结束",
                                "summary": "provider_failure_after_partial_progress",
                            },
                        ],
                        "completion_reason": "provider_failure_after_partial_progress",
                        "interrupted": False,
                        "error_surface": None,
                    },
                },
            }
        ],
        "diagnostics": {
            "source": "assistant_turn_record",
            "turn_outcome": "partial",
            "termination_reason": "provider_failure_after_partial_progress",
            "failure_kind": None,
            "protocol_path": "responses",
        },
    }

    compact = _build_ai_conversation_compact_diagnostics(snapshot)
    text = _render_ai_conversation_diagnostics_text(snapshot)

    assert compact["turn_outcome"] == "failed"
    assert compact["termination_reason"] == "provider_failure_after_partial_progress"
    assert compact["failure_kind"] == "provider_http_5xx"
    assert "outcome=failed" in text
