"""
Test type: behavioral
Scope: CLI conversation diagnostics rendering and compact projection with retired
page-awareness metadata removed from live diagnostic output.
Mock strategy: no external services; CLI projection helpers run directly.
"""

from __future__ import annotations

from app.ai.engine.execution_state_machine import ExecutionStateMachine
from app.ai.engine.types import (
    ExecutionBudget,
    IntentPlan,
    PreparedExecution,
    RecoveryDecision,
)
from app.ai.tools.types import ToolDefinition, ToolResult
from app.ai.types import ChatMessage
from app.cli import (
    _build_ai_conversation_compact_diagnostics,
    _extract_turn_diagnostics_from_call_log_metadata,
    _render_ai_conversation_diagnostics_text,
)


def test_extract_turn_diagnostics_from_call_log_metadata_reads_extended_fields() -> (
    None
):
    top_level_diagnostics = {
        "execution_path": "deep",
        "intent_plan": [
            {
                "intent_id": "intent-1",
                "kind": "weather_query",
                "family": "weather",
                "order": 1,
                "user_visible_label": "weather",
                "status": "completed",
                "allowed_tool_names": ["get_current_weather"],
            },
            {
                "intent_id": "intent-3",
                "kind": "record_read",
                "family": "data_ops",
                "order": 3,
                "user_visible_label": "record_read",
                "status": "pending",
                "allowed_tool_names": ["crm_lookup"],
            },
        ],
        "budget": {
            "status": "exited",
            "exit_reason": "tool_round_budget_exceeded",
            "limits": {"max_tool_rounds": 3},
            "usage": {"tool_rounds_used": 4},
        },
        "routing": {
            "candidate_tool_names": [
                "get_current_weather",
                "web_search",
                "fetch_url",
                "crm_lookup",
            ]
        },
        "path_decision": {
            "path": "deep",
            "reason": "multi_intent",
            "all_shortcircuit": False,
            "intent_count": 2,
        },
        "capability_injection": {
            "skills_injected": False,
            "kb_injected": False,
            "memory_injected": False,
            "bypass_reason": None,
        },
        "tool_filtering": {
            "all_tools_count": 15,
            "candidate_tools_count": 4,
            "filtering_reason": "intent_scoped",
        },
        "recovery_chain": [
            {
                "step": 1,
                "action": "retry_intent",
                "target_intent": "intent-3",
                "reason": "unfinished_intent_retry",
                "provider_failure_kind": "provider_http_5xx",
            }
        ],
        "recovery": {
            "retry_events": [
                {
                    "action": "retry_intent",
                    "target_intent_id": "intent-3",
                    "retry_family": "data_ops",
                    "allowed_tool_names": ["crm_lookup"],
                    "completed_intent_ids": ["intent-1", "intent-2"],
                    "unfinished_intent_ids": ["intent-3"],
                    "reason": "unfinished_intent_retry",
                }
            ],
            "partial_exit_reason": "retry_budget_exhausted",
        },
        "failures": {
            "failure_kind": "provider_http_5xx",
            "provider_events": [{"kind": "provider_http_5xx", "status_code": 503}],
        },
        "contract_breach_type": "unfinished_multi_intent_reply",
        "tool_leak_detected": True,
        "unfinished_intents": ["intent-3"],
        "recovered_via_retry": False,
    }
    diagnostics = _extract_turn_diagnostics_from_call_log_metadata(
        {
            "turn_diagnostics": {
                **top_level_diagnostics,
                "turn_record": {
                    "turn_outcome": "partial",
                    "termination_reason": "elapsed_budget_exceeded",
                    "protocol_path": "responses",
                    "selected_tool_names": ["get_current_weather", "web_search"],
                    "selected_skill_names": ["runtime.crm_records"],
                    "context_sources": [
                        {"kind": "read_model", "name": "admin.ai.dashboard"}
                    ],
                    "last_tool_name": "crm_lookup",
                    "interrupted_stage": "tool_loop",
                    "tool_loop_progress": {"current_round": 2, "total_rounds": 3},
                    "metadata": {
                        "contract_breach_type": "unfinished_multi_intent_reply",
                        "tool_leak_detected": True,
                        "unfinished_intents": ["intent-3"],
                        "leaked_tool_names": ["web_search"],
                        "recovered_via_retry": False,
                        "turn_diagnostics": top_level_diagnostics,
                    },
                },
            }
        }
    )

    assert diagnostics["execution_path"] == "deep"
    assert [item["intent_id"] for item in diagnostics["intent_plan"]] == [
        "intent-1",
        "intent-3",
    ]
    assert diagnostics["budget_status"] == "exited"
    assert diagnostics["budget_exit_reason"] == "tool_round_budget_exceeded"
    assert diagnostics["candidate_tool_names"] == [
        "get_current_weather",
        "web_search",
        "fetch_url",
        "crm_lookup",
    ]
    assert diagnostics["path_decision"] == {
        "path": "deep",
        "reason": "multi_intent",
        "all_shortcircuit": False,
        "intent_count": 2,
    }
    assert diagnostics["capability_injection"] == {
        "skills_injected": False,
        "kb_injected": False,
        "memory_injected": False,
        "bypass_reason": None,
    }
    assert diagnostics["tool_filtering"] == {
        "all_tools_count": 15,
        "candidate_tools_count": 4,
        "filtering_reason": "intent_scoped",
    }
    assert diagnostics["recovery_chain"] == [
        {
            "step": 1,
            "action": "retry_intent",
            "target_intent": "intent-3",
            "reason": "unfinished_intent_retry",
            "provider_failure_kind": "provider_http_5xx",
        }
    ]
    assert [
        event["target_intent_id"] for event in diagnostics.get("retry_events", [])
    ] == ["intent-3"]
    assert diagnostics["partial_exit_reason"] == "retry_budget_exhausted"
    assert diagnostics["failure_kind"] == "provider_http_5xx"
    assert diagnostics["provider_events"] == [
        {"kind": "provider_http_5xx", "status_code": 503}
    ]
    assert diagnostics["contract_breach_type"] == "unfinished_multi_intent_reply"
    assert diagnostics["tool_leak_detected"] is True
    assert diagnostics["unfinished_intents"] == ["intent-3"]
    assert diagnostics["recovered_via_retry"] is False
    assert diagnostics.get("last_tool_name") == "crm_lookup"
    assert diagnostics["tool_loop_progress"] == {"current_round": 2, "total_rounds": 3}


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


def test_cli_compact_diagnostics_builder_and_text_renderer_surface_key_orchestration_state() -> (
    None
):
    snapshot = {
        "conversation": {
            "id": 666,
            "tenant_id": 1,
            "agent_id": 99,
            "user_id": 7,
            "status": "active",
            "message_count": 12,
        },
        "diagnostics": {
            "source": "assistant_message",
            "turn_outcome": "partial",
            "termination_reason": "elapsed_budget_exceeded",
            "protocol_path": "responses",
            "execution_path": "deep",
            "selected_tool_names": [
                "get_current_weather",
                "web_search",
                "fetch_url",
            ],
            "selected_skill_names": ["runtime.crm_records"],
            "candidate_tool_names": [
                "get_current_weather",
                "web_search",
                "fetch_url",
                "crm_lookup",
            ],
            "tool_planner": {
                "intent": "weather_query",
                "family": "weather",
            },
            "path_decision": {
                "path": "deep",
                "reason": "multi_intent",
            },
            "capability_injection": {
                "skills_injected": False,
                "kb_injected": False,
                "memory_injected": False,
                "bypass_reason": None,
            },
            "tool_filtering": {
                "all_tools_count": 4,
                "candidate_tools_count": 3,
                "filtering_reason": "optimizer",
            },
            "recovery_chain": [
                {
                    "step": 1,
                    "action": "retry_intent",
                    "target_intent": "intent-3",
                    "reason": "unfinished_intent_retry",
                    "provider_failure_kind": "provider_http_5xx",
                }
            ],
            "intent_plan": [
                {
                    "intent_id": "intent-1",
                    "kind": "weather_query",
                    "family": "weather",
                    "order": 1,
                    "user_visible_label": "weather",
                    "status": "completed",
                    "allowed_tool_names": ["get_current_weather"],
                },
                {
                    "intent_id": "intent-2",
                    "kind": "web_research",
                    "family": "web_research",
                    "order": 2,
                    "user_visible_label": "rail_search",
                    "status": "completed",
                    "allowed_tool_names": ["web_search", "fetch_url"],
                },
                {
                    "intent_id": "intent-3",
                    "kind": "record_read",
                    "family": "data_ops",
                    "order": 3,
                    "user_visible_label": "record_read",
                    "status": "pending",
                    "allowed_tool_names": ["crm_lookup"],
                },
            ],
            "unfinished_intents": ["intent-3"],
            "retry_events": [
                {
                    "action": "retry_intent",
                    "target_intent_id": "intent-3",
                    "retry_family": "data_ops",
                    "allowed_tool_names": ["crm_lookup"],
                    "completed_intent_ids": ["intent-1", "intent-2"],
                    "unfinished_intent_ids": ["intent-3"],
                    "reason": "unfinished_intent_retry",
                }
            ],
            "partial_exit_reason": "retry_budget_exhausted",
            "failure_kind": "provider_http_5xx",
            "provider_events": [{"kind": "provider_http_5xx", "status_code": 503}],
            "budget": {
                "status": "exited",
                "exit_reason": "elapsed_budget_exceeded",
                "limits": {"max_elapsed_ms": 45000},
                "usage": {"elapsed_ms_used": 47000},
            },
            "budget_status": "exited",
            "budget_exit_reason": "elapsed_budget_exceeded",
            "contract_breach_type": "unfinished_multi_intent_reply",
            "tool_leak_detected": True,
            "recovered_via_retry": False,
            "last_tool_name": "crm_lookup",
            "interrupted_stage": "tool_loop",
        },
    }

    compact = _build_ai_conversation_compact_diagnostics(snapshot)
    text = _render_ai_conversation_diagnostics_text(snapshot)

    assert compact["conversation_id"] == 666
    assert compact["execution_path"] == "deep"
    assert compact["failure_kind"] == "provider_http_5xx"
    assert compact["budget_exit_reason"] == "elapsed_budget_exceeded"
    assert [item["intent_id"] for item in compact["intent_plan"]] == [
        "intent-1",
        "intent-2",
        "intent-3",
    ]
    assert [event["target_intent_id"] for event in compact["retry_events"]] == [
        "intent-3"
    ]
    assert compact["tool_planner"]["intent"] == "weather_query"
    assert compact["path_decision"]["path"] == "deep"
    assert "current_page_injected" not in compact["capability_injection"]
    assert compact["tool_filtering"]["candidate_tools_count"] == 3
    assert compact["recovery_chain"][0]["target_intent"] == "intent-3"
    assert compact["provider_events"] == [
        {"kind": "provider_http_5xx", "status_code": 503}
    ]
    assert "Conversation #666 diagnostics" in text
    assert "execution_path=deep" in text
    assert "selected_tools=get_current_weather, web_search, fetch_url" in text
    assert (
        "candidate_tools=get_current_weather, web_search, fetch_url, crm_lookup" in text
    )
    assert "crm_lookup" in text
    assert "data_ops" in text
    assert "tool_planner=" in text
    assert "path_decision=" in text
    assert "capability_injection=" in text
    assert "tool_filtering=" in text
    assert "recovery_chain=" in text
    assert "unfinished_intents=intent-3" in text
    assert "provider_events=" in text
    assert "budget=" in text


def test_cli_diagnostics_projects_canonical_web_research_without_fetch_invention() -> (
    None
):
    snapshot = {
        "conversation": {"id": 2282},
        "diagnostics": {
            "source": "assistant_turn_record",
            "turn_outcome": "failed",
            "termination_reason": "completed",
            "protocol_path": "responses",
            "final_output_source": "recovery_evidence",
            "turn_record": {
                "turn_outcome": "failed",
                "termination_reason": "completed",
                "metadata": {
                    "turn_diagnostics": {
                        "web_research_evidence": {
                            "query": "大模型排行榜 2026",
                            "status": "partial",
                            "search_provider": "builtin-web-search",
                            "fetch_provider": "builtin-fetch-url",
                            "search_results": [
                                {
                                    "title": "Ranking",
                                    "url": "https://example.com/ranking",
                                    "snippet": "search-only snippet",
                                    "rank": 1,
                                    "provider": "builtin-web-search",
                                }
                            ],
                            "fetched_pages": [],
                            "citations": [],
                            "answer_quality": "none",
                            "failure_kind": "fetch_not_attempted",
                            "diagnostics": {
                                "pipeline_id": "wr-2282",
                                "search_provider": "builtin-web-search",
                                "fetch_provider": "builtin-fetch-url",
                                "evidence_status": "partial",
                                "candidate_urls": ["https://example.com/ranking"],
                                "fetched_urls": [],
                                "evidence_quality": "none",
                                "answer_source": "none",
                                "failure_kind": "fetch_not_attempted",
                                "provider_disable_reason": (
                                    "optional_provider_skipped:builtin_default"
                                ),
                            },
                        }
                    }
                },
            },
        },
    }

    compact = _build_ai_conversation_compact_diagnostics(snapshot)
    text = _render_ai_conversation_diagnostics_text(snapshot)

    assert compact["web_research_pipeline_id"] == "wr-2282"
    assert compact["search_provider"] == "builtin-web-search"
    assert compact["fetch_provider"] == "builtin-fetch-url"
    assert compact["evidence_status"] == "partial"
    assert compact["candidate_urls"] == ["https://example.com/ranking"]
    assert compact["fetched_urls"] == []
    assert compact["web_research_failure_kind"] == "fetch_not_attempted"
    assert compact["web_research_failure_layer"] == "evidence"
    assert (
        compact["web_research_provider_disable_reason"]
        == "optional_provider_skipped:builtin_default"
    )
    assert "web_research pipeline_id=wr-2282" in text
    assert "web_research_candidate_urls=https://example.com/ranking" in text
    assert "web_research_fetched_urls" not in text
    assert "native_web_search_first" not in text


def test_cli_diagnostics_prefers_turn_flow_web_research_evidence_over_stale_fields() -> (
    None
):
    completed_evidence = {
        "query": "大模型排行榜 2026",
        "status": "completed",
        "search_provider": "builtin:web_search",
        "fetch_provider": "builtin:fetch_url",
        "search_results": [
            {
                "title": "Ranking",
                "url": "https://search.example/ranking",
                "snippet": "candidate",
                "rank": 1,
                "provider": "builtin:web_search",
            }
        ],
        "fetched_pages": [
            {
                "title": "Ranking",
                "url": "https://source.example/ranking",
                "status": "completed",
                "answer_quality": "body",
                "provider": "builtin:fetch_url",
            }
        ],
        "citations": [
            {
                "title": "Ranking",
                "url": "https://source.example/ranking",
                "provider": "builtin:fetch_url",
                "source": "page",
            }
        ],
        "answer_quality": "body",
        "failure_kind": None,
        "diagnostics": {
            "pipeline_id": "web-research-1",
            "search_provider": "builtin:web_search",
            "fetch_provider": "builtin:fetch_url",
            "evidence_status": "completed",
            "candidate_urls": ["https://search.example/ranking"],
            "fetched_urls": ["https://source.example/ranking"],
            "evidence_quality": "body",
            "answer_source": "fetched_body",
            "failure_kind": None,
            "provider_disable_reason": "optional_provider_skipped:builtin_default",
        },
    }
    stale_projection = {
        "evidence_status": "partial",
        "candidate_urls": ["https://stale.example/search-only"],
        "fetched_urls": [],
        "web_research_failure_kind": "fetch_not_attempted",
        "web_research_failure_layer": "evidence",
        "web_research_provider_disable_reason": "fetch_already_attempted",
    }
    snapshot = {
        "conversation": {"id": 2283},
        "diagnostics": {
            "source": "assistant_turn_record",
            "turn_outcome": "success",
            "termination_reason": "completed",
            "final_output_source": "recovery_evidence",
            **stale_projection,
            "turn_record": {
                "turn_outcome": "success",
                "termination_reason": "completed",
                **stale_projection,
                "web_research_diagnostics": dict(stale_projection),
                "turn_flow": {
                    "evidence": [
                        {
                            "id": "web-research-1:fetch_url:1",
                            "kind": "tool",
                            "title": "fetch_url",
                            "summary_payload": {
                                "web_research_evidence": completed_evidence
                            },
                        }
                    ]
                },
                "metadata": {
                    "turn_diagnostics": {
                        **stale_projection,
                        "web_research_diagnostics": dict(stale_projection),
                    }
                },
            },
        },
    }

    compact = _build_ai_conversation_compact_diagnostics(snapshot)
    text = _render_ai_conversation_diagnostics_text(snapshot)

    assert compact["web_research_pipeline_id"] == "web-research-1"
    assert compact["search_provider"] == "builtin:web_search"
    assert compact["fetch_provider"] == "builtin:fetch_url"
    assert compact["evidence_status"] == "completed"
    assert compact["candidate_urls"] == ["https://search.example/ranking"]
    assert compact["fetched_urls"] == ["https://source.example/ranking"]
    assert compact["evidence_quality"] == "body"
    assert compact["answer_source"] == "fetched_body"
    assert compact["web_research_failure_kind"] is None
    assert compact["web_research_failure_layer"] is None
    assert (
        compact["web_research_provider_disable_reason"]
        == "optional_provider_skipped:builtin_default"
    )
    assert "web_research pipeline_id=web-research-1" in text
    assert "evidence_status=completed" in text
    assert "web_research_fetched_urls=https://source.example/ranking" in text
    assert "fetch_not_attempted" not in text


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


def test_cli_diagnostics_text_surfaces_empty_selected_and_candidate_tools() -> None:
    snapshot = {
        "conversation": {"id": 667},
        "diagnostics": {
            "source": "assistant_turn_record",
            "turn_outcome": "success",
            "termination_reason": "completed",
            "protocol_path": "responses",
            "execution_path": "fast",
            "selected_tool_names": [],
            "candidate_tool_names": [],
            "selected_skill_names": ["get_current_time", "web_search"],
            "tool_planner": {
                "intent": "direct_reply",
                "family": "none",
            },
            "budget": {
                "status": "ok",
                "usage": {"tool_rounds_used": 0, "candidate_tools_count": 0},
            },
        },
    }

    text = _render_ai_conversation_diagnostics_text(snapshot)

    assert "selected_tools=[]" in text
    assert "candidate_tools=[]" in text
    assert "tool_planner=" in text
    assert "budget_usage=" in text


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


def test_extract_turn_diagnostics_clears_completed_progress_signal() -> None:
    diagnostics = _extract_turn_diagnostics_from_call_log_metadata(
        {
            "turn_diagnostics": {
                "failures": {
                    "failure_kind": "web_search_in_progress",
                },
                "turn_record": {
                    "turn_outcome": "success",
                    "termination_reason": "completed",
                    "protocol_path": "responses",
                    "failure_kind": "web_search_in_progress",
                    "selected_tool_names": ["web_search", "fetch_url"],
                    "selected_skill_names": ["web_search"],
                },
            }
        }
    )

    assert diagnostics["turn_outcome"] == "success"
    assert diagnostics["termination_reason"] == "completed"
    assert diagnostics["failure_kind"] is None


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


def test_execution_state_machine_emits_canonical_turn_event_schema() -> None:
    budget = ExecutionBudget(
        max_prompt_tokens=4096,
        max_completion_tokens=1024,
        max_tool_rounds=4,
        max_elapsed_ms=120000,
        max_retry_per_intent=2,
        max_candidate_tools=4,
        max_tool_result_bytes=16384,
    )
    intent = IntentPlan(
        intent_id="intent-1",
        kind="time_query",
        family="time",
        order=1,
        user_visible_label="time",
        source_text="现在几点",
        shortcircuit=True,
        allowed_tool_names=["get_current_time"],
        completion_signals=["get_current_time"],
    )
    prep = PreparedExecution(
        intent_plan=[intent],
        execution_path="fast",
        execution_budget=budget,
        tools=[ToolDefinition(name="get_current_time")],
        all_tools=[
            ToolDefinition(name="get_current_time"),
            ToolDefinition(name="get_current_weather"),
            ToolDefinition(name="web_search"),
        ],
        diagnostics={
            "capability_injection_decision": {
                "skills_injected": False,
                "kb_injected": False,
                "memory_injected": False,
                "bypass_reason": "all_shortcircuit",
            }
        },
    )

    machine = ExecutionStateMachine.from_prepared_execution(prep)
    machine.register_completion_tokens(32)
    machine.register_tool_round()
    machine.register_tool_results(
        messages=[
            ChatMessage(
                role="assistant",
                content="",
                tool_calls=[
                    {
                        "id": "call-1",
                        "success": True,
                        "function": {"name": "get_current_time"},
                    }
                ],
            )
        ],
        tool_results=[
            ToolResult(
                tool_call_id="call-1",
                name="get_current_time",
                success=True,
                output="现在是 14:30",
            )
        ],
    )
    machine.register_retry(
        RecoveryDecision(
            action="retry_intent",
            target_intent_id="intent-1",
            retry_family="time",
            allowed_tool_names=["get_current_time"],
            completed_intent_ids=["intent-1"],
            unfinished_intent_ids=[],
            reason="retry_for_validation",
        )
    )

    payload = machine.build_diagnostics_payload()

    assert payload["path_decision"] == {
        "path": "fast",
        "reason": "all_shortcircuit",
        "all_shortcircuit": True,
        "intent_count": 1,
    }
    assert payload["capability_injection"] == {
        "skills_injected": False,
        "kb_injected": False,
        "memory_injected": False,
        "bypass_reason": "all_shortcircuit",
    }
    assert payload["tool_filtering"] == {
        "all_tools_count": 3,
        "candidate_tools_count": 1,
        "filtering_reason": "intent_scoped_shortcircuit",
    }
    assert payload["recovery_chain"][-1]["action"] == "retry_intent"
    assert payload["recovery_chain"][-1]["target_intent"] == "intent-1"
    event_kinds = {event["kind"] for event in payload["turn_events"]}
    assert {
        "turn.started",
        "turn.intent_planned",
        "turn.path_selected",
        "turn.capability_gated",
        "turn.tools_filtered",
        "turn.model_called",
        "turn.tool_round",
        "turn.tool_completed",
        "turn.recovery_decided",
        "turn.budget_checked",
    }.issubset(event_kinds)
    assert payload["candidate_tool_names"] == ["get_current_time"]
    for event in payload["turn_events"]:
        assert isinstance(event["timestamp_ms"], int)
        assert event["timestamp_ms"] >= 0
        assert isinstance(event["data"], dict)


def test_recoverable_failure_does_not_emit_terminal_failed_event_before_recovery() -> (
    None
):
    budget = ExecutionBudget(
        max_prompt_tokens=2048,
        max_completion_tokens=512,
        max_tool_rounds=3,
        max_elapsed_ms=60000,
        max_retry_per_intent=2,
        max_candidate_tools=3,
        max_tool_result_bytes=8192,
    )
    intent = IntentPlan(
        intent_id="intent-1",
        kind="weather_query",
        family="weather",
        order=1,
        user_visible_label="weather",
        source_text="今天天气",
        allowed_tool_names=["get_current_weather"],
    )
    machine = ExecutionStateMachine.from_prepared_execution(
        PreparedExecution(
            intent_plan=[intent],
            execution_path="normal",
            execution_budget=budget,
            tools=[ToolDefinition(name="get_current_weather")],
            all_tools=[
                ToolDefinition(name="get_current_weather"),
                ToolDefinition(name="web_search"),
            ],
        )
    )

    machine.register_provider_failure(
        kind="tool_timeout",
        event={"kind": "tool_timeout", "status_code": 504},
    )
    machine.register_retry(
        RecoveryDecision(
            action="retry_intent",
            target_intent_id="intent-1",
            retry_family="weather",
            allowed_tool_names=["get_current_weather"],
            completed_intent_ids=[],
            unfinished_intent_ids=["intent-1"],
            reason="unfinished_intent_retry",
            provider_failure_kind="tool_timeout",
        )
    )
    machine.transition("completed")

    payload = machine.build_diagnostics_payload()
    event_kinds = [event["kind"] for event in payload["turn_events"]]

    assert "turn.tool_failed" in event_kinds
    assert "turn.recovery_decided" in event_kinds
    assert "turn.completed" in event_kinds
    assert "turn.failed" not in event_kinds
    assert "turn.partial_exit" not in event_kinds
