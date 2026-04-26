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


def test_extract_turn_diagnostics_projects_compact_runtime_decision_fields() -> None:
    payload = extract_turn_diagnostics_from_metadata(
        {
            "turn_record": {
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
                            "page_injected": True,
                            "bypass_reason": None,
                        },
                        "routing": {
                            "tool_filtering": {
                                "all_tools_count": 15,
                                "candidate_tools_count": 3,
                                "filtering_reason": "intent_scoped",
                            }
                        },
                        "recovery_chain": [],
                    }
                }
            }
        }
    )

    assert payload["path_decision"] == {
        "path": "normal",
        "reason": "bounded_multi_intent",
        "all_shortcircuit": False,
        "intent_count": 1,
    }
    assert payload["capability_injection"] == {
        "skills_injected": False,
        "kb_injected": False,
        "memory_injected": False,
        "page_injected": True,
        "bypass_reason": None,
    }
    assert payload["tool_filtering"] == {
        "all_tools_count": 15,
        "candidate_tools_count": 3,
        "filtering_reason": "intent_scoped",
    }
    assert payload["recovery_chain"] == []


def test_extract_turn_diagnostics_derives_elapsed_budget_exit_from_usage() -> None:
    payload = extract_turn_diagnostics_from_metadata(
        {
            "turn_record": {
                "turn_outcome": "success",
                "termination_reason": "completed",
                "budget": {
                    "status": "ok",
                    "limits": {"max_elapsed_ms": 60000},
                    "usage": {"elapsed_ms_used": 135500},
                },
            }
        }
    )

    assert payload["budget_status"] == "exited"
    assert payload["budget_exit_reason"] == "elapsed_budget_exceeded"
    assert payload["budget"]["usage"]["elapsed_over_limit"] is True
    assert payload["budget"]["usage"]["elapsed_over_limit_ms"] == 75500


def test_extract_turn_diagnostics_keeps_explicit_empty_live_selection_over_inventory() -> (
    None
):
    payload = extract_turn_diagnostics_from_metadata(
        {
            "turn_record": {
                "selected_tool_names": [],
                "selected_skill_names": [],
                "turn_outcome": "failed",
                "termination_reason": "tool_round_failed",
                "metadata": {
                    "turn_diagnostics": {
                        "selected_tool_names": ["ui_get_snapshot", "web_search"],
                        "selected_skill_names": ["Page Skill", "Research Skill"],
                        "turn_skill_activation": {
                            "applied": True,
                            "reason": "runtime_policy",
                            "selected_tool_names": [],
                            "selected_skill_names": [],
                            "inventory_selected_tool_names": [
                                "ui_get_snapshot",
                                "web_search",
                            ],
                            "inventory_selected_skill_names": [
                                "Page Skill",
                                "Research Skill",
                            ],
                        },
                    }
                },
            },
            "context_diagnostics": {
                "selected_tool_names": ["ui_get_snapshot", "web_search"],
                "selected_skill_names": ["Page Skill", "Research Skill"],
            },
            "last_run_summary": {
                "selected_tool_names": ["ui_get_snapshot", "web_search"],
                "selected_skill_names": ["Page Skill", "Research Skill"],
            },
        }
    )

    assert payload["selected_tool_names"] == []
    assert payload["selected_skill_names"] == []
    assert payload["turn_skill_activation"]["inventory_selected_tool_names"] == [
        "ui_get_snapshot",
        "web_search",
    ]
