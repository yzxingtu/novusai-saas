"""Test type: behavioral
Scope: extracted diagnostics support seam and retired page-awareness scrubbing.
Real dependencies: diagnostics extraction helpers.
Mocked dependencies: none.
"""

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
                                    "retry_family": "web_research",
                                    "allowed_tool_names": ["web_search"],
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
            "retry_family": "web_research",
            "allowed_tool_names": ["web_search"],
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
                        "selected_skill_names": [
                            "runtime.page_context",
                            "Research Skill",
                        ],
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
                                "runtime.page_context",
                                "Research Skill",
                            ],
                        },
                    }
                },
            },
            "context_diagnostics": {
                "selected_tool_names": ["ui_get_snapshot", "web_search"],
                "selected_skill_names": ["runtime.page_context", "Research Skill"],
            },
            "last_run_summary": {
                "selected_tool_names": ["ui_get_snapshot", "web_search"],
                "selected_skill_names": ["runtime.page_context", "Research Skill"],
            },
        }
    )

    assert payload["selected_tool_names"] == []
    assert payload["selected_skill_names"] == []
    assert payload["turn_skill_activation"]["inventory_selected_tool_names"] == [
        "web_search",
    ]
    assert payload["turn_skill_activation"]["inventory_selected_skill_names"] == [
        "Research Skill"
    ]


def test_extract_turn_diagnostics_scrubs_retired_page_awareness_metadata() -> None:
    payload = extract_turn_diagnostics_from_metadata(
        {
            "turn_record": {
                "selected_tool_names": ["ui_get_snapshot", "web_search"],
                "selected_skill_names": ["runtime.page_context", "Research Skill"],
                "metadata": {
                    "turn_diagnostics": {
                        "continuation_source": "page_ops",
                        "last_tool_name": "ui_click",
                        "routing": {
                            "candidate_tool_names": ["pageop_click", "fetch_url"]
                        },
                        "context_sources": [
                            {
                                "kind": "page_context",
                                "name": "admin.ai.dashboard",
                                "metadata": {
                                    "selected_tool_names": ["ui_click"],
                                },
                            },
                            {
                                "kind": "skill",
                                "name": "Research Skill",
                                "metadata": {
                                    "selected_tool_names": [
                                        "ui_get_snapshot",
                                        "fetch_url",
                                    ],
                                    "selected_skill_names": [
                                        "页面感知交互",
                                        "Research Skill",
                                    ],
                                },
                            },
                        ],
                        "tool_planner": {
                            "intent": "page_search",
                            "family": "page_ops",
                            "allowed_tool_names": ["ui_get_snapshot"],
                        },
                        "intent_plan": [
                            {
                                "intent_id": "intent-page",
                                "kind": "page_search",
                                "family": "page_ops",
                                "status": "completed",
                                "completed_by_tool_names": ["ui_get_snapshot"],
                            },
                            {
                                "intent_id": "intent-web",
                                "kind": "web_research",
                                "family": "web_research",
                                "status": "pending",
                                "allowed_tool_names": ["web_search"],
                            },
                        ],
                        "recovery": {
                            "retry_events": [
                                {
                                    "action": "retry_intent",
                                    "target_intent_id": "intent-page",
                                    "retry_family": "page_ops",
                                    "allowed_tool_names": ["ui_click"],
                                },
                                {
                                    "action": "retry_intent",
                                    "target_intent_id": "intent-web",
                                    "retry_family": "web_research",
                                    "allowed_tool_names": ["fetch_url"],
                                },
                            ]
                        },
                    }
                },
            }
        }
    )

    assert payload["selected_tool_names"] == ["web_search"]
    assert payload["selected_skill_names"] == ["Research Skill"]
    assert payload["candidate_tool_names"] == ["fetch_url"]
    assert payload["continuation_source"] is None
    assert payload["last_tool_name"] is None
    assert payload["tool_planner"] is None
    assert payload["context_sources"] == [
        {
            "kind": "skill",
            "name": "Research Skill",
            "active": True,
            "metadata": {
                "selected_tool_names": ["fetch_url"],
                "selected_skill_names": ["Research Skill"],
            },
        }
    ]
    assert payload["intent_plan"] == [
        {
            "intent_id": "intent-web",
            "kind": "web_research",
            "family": "web_research",
            "order": None,
            "user_visible_label": None,
            "source_text": None,
            "status": "pending",
            "allowed_tool_names": ["web_search"],
            "completed_by_tool_names": [],
            "failure_reason": None,
        }
    ]
    assert payload["retry_events"] == [
        {
            "action": "retry_intent",
            "target_intent_id": "intent-web",
            "retry_family": "web_research",
            "allowed_tool_names": ["fetch_url"],
            "completed_intent_ids": [],
            "unfinished_intent_ids": [],
            "reason": None,
            "provider_failure_kind": None,
            "metadata": {},
        }
    ]
