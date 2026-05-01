"""
Test type: behavioral
Scope: Conversation turn-flow projection, failure states, and invalid runtime metadata
diagnostic scrubbing.
Mock strategy: no external services; projector logic runs directly.
"""

from app.services.ai.conversation_turn_flow_projector import (
    ConversationTurnFlowProjector,
)


def test_project_from_metadata_maps_elapsed_budget_exit_to_failed_terminal() -> None:
    turn_flow = ConversationTurnFlowProjector.project_from_metadata(
        {
            "completion_reason": "elapsed_budget_exceeded",
            "turn_record": {
                "turn_outcome": "partial",
            },
        },
        content="部分结果",
    )

    assert turn_flow["completion_reason"] == "elapsed_budget_exceeded"
    assert turn_flow["timeline"][-1]["type"] == "failed"
    assert turn_flow["timeline"][-1]["status"] == "error"
    answer_assembly = next(
        stage for stage in turn_flow["timeline"] if stage["type"] == "answer_assembly"
    )
    assert answer_assembly["status"] == "error"


def test_project_from_metadata_hides_raw_thinking_summary_from_user_timeline() -> None:
    turn_flow = ConversationTurnFlowProjector.project_from_metadata(
        {
            "thinking_content": (
                "Searching for Opus 4.7 news and official release info.\n"
                "I should also inspect secondary reports and compare timestamps."
            ),
        },
    )

    thinking_stage = next(
        stage for stage in turn_flow["timeline"] if stage["type"] == "thinking"
    )
    assert thinking_stage["summary"] == "已完成思考与规划"
    assert thinking_stage["detail_lines"] == []


def test_project_from_metadata_uses_legacy_rag_sources_only_when_canonical_context_sources_missing() -> None:
    turn_flow = ConversationTurnFlowProjector.project_from_metadata(
        {
            "rag_sources": [
                {
                    "kind": "knowledge_base",
                    "title": "Legacy retrieval source",
                    "source_ref": "legacy-retrieval",
                }
            ],
        },
        content="已读取旧消息证据。",
    )

    assert turn_flow["evidence"] == [
        {
            "id": "legacy-retrieval",
            "kind": "knowledge_base",
            "title": "Legacy retrieval source",
            "url": None,
            "snippet": None,
            "badge": None,
            "score": None,
            "tool_call_id": None,
            "source_ref": "legacy-retrieval",
        }
    ]


def test_project_from_metadata_sanitizes_existing_raw_thinking_stage_summary() -> None:
    turn_flow = ConversationTurnFlowProjector.project_from_metadata(
        {
            "turn_flow": {
                "timeline": [
                    {
                        "id": "thinking",
                        "type": "thinking",
                        "status": "completed",
                        "title": "已思考",
                        "summary": "**Considering user compliance**",
                        "detail_lines": ["**Considering user compliance**"],
                    }
                ],
                "evidence": [],
                "answer_card": {
                    "summary": "THREAD_OK_0418W",
                    "sections": [],
                    "source_chip_ids": [],
                },
                "completion_reason": "completed",
            },
            "turn_record": {
                "turn_outcome": "success",
                "termination_reason": "completed",
            },
        },
        content="THREAD_OK_0418W",
    )

    thinking_stage = next(
        stage for stage in turn_flow["timeline"] if stage["type"] == "thinking"
    )
    assert thinking_stage["summary"] == "已完成思考与规划"
    assert thinking_stage["detail_lines"] == []


def test_project_from_metadata_marks_untrusted_final_output_source_as_failed() -> None:
    turn_flow = ConversationTurnFlowProjector.project_from_metadata(
        {
            "completion_reason": "completed",
            "turn_record": {
                "turn_outcome": "success",
                "termination_reason": "completed",
                "final_output_source": "tool_evidence_completed",
            },
        },
        content="Fetched reddit.json",
    )

    assert turn_flow["timeline"][-1]["type"] == "failed"
    assert turn_flow["timeline"][-1]["status"] == "error"
    assert turn_flow["error_surface"]["error_type"] == "untrusted_final_output_source"
    assert turn_flow["answer_card"]["summary"] is None
    assert turn_flow["answer_card"]["sections"] == []


def test_project_from_metadata_preserves_hosted_search_progress_for_timeout_history() -> None:
    turn_flow = ConversationTurnFlowProjector.project_from_metadata(
        {
            "completion_reason": "error",
            "turn_record": {
                "turn_outcome": "partial",
                "termination_reason": "error",
                "metadata": {
                    "failure_kind": "provider_timeout",
                    "stream_progress_kinds": ["web_search_in_progress"],
                    "unfinished_intents": ["intent-1"],
                },
            },
            "selected_tool_names": ["web_search", "fetch_url"],
            "unfinished_intents": ["intent-1"],
            "failure_kind": "provider_timeout",
            "provider_events": [
                {
                    "kind": "web_search_in_progress",
                    "protocol_path": "responses",
                    "tool_family": "web_research",
                }
            ],
        },
        content="",
    )

    tool_selection = next(
        stage for stage in turn_flow["timeline"] if stage["type"] == "tool_selection"
    )
    tool_execution = next(
        stage for stage in turn_flow["timeline"] if stage["type"] == "tool_execution"
    )
    retrieval = next(
        stage for stage in turn_flow["timeline"] if stage["type"] == "retrieval"
    )

    assert tool_selection["summary"] == "已从 2 个工具中筛选 2 个"
    assert tool_execution["status"] == "error"
    assert tool_execution["summary"] == "联网搜索在等待结果返回时超时"
    assert tool_execution["detail_lines"] == ["联网搜索在等待结果返回时超时"]
    assert retrieval["summary"] == "搜索未返回可展示证据"
    assert retrieval["detail_lines"] == ["搜索未返回可展示证据"]


def test_project_from_metadata_scrubs_invalid_runtime_metadata_without_reclassifying_turn() -> None:
    turn_flow = ConversationTurnFlowProjector.project_from_metadata(
        {
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
                        "summary": "completed",
                    },
                ],
                "evidence": [],
                "answer_card": {
                    "summary": "我先整理已有信息。",
                    "sections": [],
                    "source_chip_ids": [],
                },
                "completion_reason": "completed",
            },
            "context_diagnostics": {
                "conversation_outcome": "success",
                "turn_outcome": "success",
                "continuation_source": "data_ops",
                "tool_planner": {
                    "intent": "page_search",
                    "family": "data_ops",
                },
                "intent_plan": [
                    {
                        "intent_id": "intent-1",
                        "kind": "page_search",
                        "family": "data_ops",
                        "status": "completed",
                        "completed_by_tool_names": ["crm_list_actions"],
                    }
                ],
                "candidate_tool_names": [
                    "crm_read_record",
                    "crm_list_actions",
                    "crm_update_record",
                ],
                "selected_tool_names": [],
            },
        },
        content="我先整理已有信息。",
    )

    assert turn_flow["completion_reason"] == "completed"
    assert turn_flow["timeline"][-1]["type"] == "completed"
    assert turn_flow["timeline"][-1]["status"] == "completed"
    assert turn_flow["error_surface"] is None
    answer_assembly = next(
        stage for stage in turn_flow["timeline"] if stage["type"] == "answer_assembly"
    )
    assert answer_assembly["status"] == "completed"


def test_project_from_metadata_uses_completed_tool_names_when_selected_tools_missing() -> None:
    turn_flow = ConversationTurnFlowProjector.project_from_metadata(
        {
            "context_diagnostics": {
                "tool_planner": {
                    "intent": "web_research",
                    "family": "web_research",
                },
                "candidate_tool_names": [
                    "web_search",
                    "fetch_url",
                ],
                "intent_plan": [
                    {
                        "intent_id": "intent-1",
                        "kind": "web_research",
                        "family": "web_research",
                        "status": "completed",
                        "completed_by_tool_names": ["fetch_url"],
                    }
                ],
            },
        },
        content="已整理公开资料。",
    )

    tool_selection = next(
        stage for stage in turn_flow["timeline"] if stage["type"] == "tool_selection"
    )
    assert tool_selection["summary"] == "已从 2 个工具中筛选 1 个"
    assert tool_selection["metrics"]["selected_count"] == 1


def test_project_from_metadata_provider_timeout_after_completed_tool_keeps_tool_stage_completed() -> None:
    turn_flow = ConversationTurnFlowProjector.project_from_metadata(
        {
            "partial": True,
            "completion_reason": "provider_timeout",
            "context_diagnostics": {
                "turn_outcome": "partial",
                "termination_reason": "provider_timeout",
                "failure_kind": "provider_timeout",
                "tool_planner": {
                    "intent": "web_research",
                    "family": "web_research",
                },
                "candidate_tool_names": ["web_search"],
                "intent_plan": [
                    {
                        "intent_id": "intent-1",
                        "kind": "web_research",
                        "family": "web_research",
                        "status": "completed",
                        "completed_by_tool_names": ["web_search"],
                    }
                ],
                "provider_events": [
                    {
                        "kind": "provider_timeout",
                        "protocol_path": "responses",
                    }
                ],
            },
        },
        content="我先把已完成部分整理给你：这部分。",
    )

    thinking = next(stage for stage in turn_flow["timeline"] if stage["type"] == "thinking")
    tool_selection = next(
        stage for stage in turn_flow["timeline"] if stage["type"] == "tool_selection"
    )
    tool_execution = next(
        stage for stage in turn_flow["timeline"] if stage["type"] == "tool_execution"
    )
    answer_assembly = next(
        stage for stage in turn_flow["timeline"] if stage["type"] == "answer_assembly"
    )

    assert thinking["status"] == "completed"
    assert tool_selection["status"] == "completed"
    assert tool_execution["status"] == "error"
    assert tool_execution["summary"] == "联网搜索在等待结果返回时超时"
    assert answer_assembly["status"] == "error"
    assert turn_flow["answer_card"]["summary"] == "我先把已完成部分整理给你：这部分。"


def test_normalize_turn_flow_replaces_generic_missing_answer_summary_with_partial_content() -> None:
    turn_flow = ConversationTurnFlowProjector.project_from_metadata(
        {
            "partial": True,
            "completion_reason": "provider_timeout",
            "turn_flow": {
                "timeline": [
                    {
                        "id": "thinking",
                        "type": "thinking",
                        "status": "error",
                        "title": "Thinking",
                        "summary": "Reasoning summary generated",
                    },
                    {
                        "id": "tool_selection",
                        "type": "tool_selection",
                        "status": "skipped",
                        "title": "Tool Selection",
                        "summary": "Selected 1 of 1 tools",
                    },
                    {
                        "id": "tool_execution",
                        "type": "tool_execution",
                        "status": "error",
                        "title": "Tool Execution",
                        "summary": "工具已进入执行阶段，但未等到返回结果",
                    },
                    {
                        "id": "answer_assembly",
                        "type": "answer_assembly",
                        "status": "error",
                        "title": "Answer Assembly",
                        "summary": "Answer assembly failed",
                    },
                    {
                        "id": "failed",
                        "type": "failed",
                        "status": "error",
                        "title": "Failed",
                        "summary": "provider_timeout",
                    },
                ],
                "answer_card": {
                    "summary": "No trusted assistant final answer.",
                    "sections": [
                        {
                            "id": "final_answer",
                            "title": "Answer",
                            "content": "No trusted assistant final answer.",
                        }
                    ],
                    "source_chip_ids": [],
                    "confidence_label": "low",
                    "follow_up_suggestions": [],
                },
                "completion_reason": "provider_timeout",
            },
            "context_diagnostics": {
                "turn_outcome": "partial",
                "termination_reason": "provider_timeout",
                "failure_kind": "provider_timeout",
                "tool_planner": {
                    "intent": "web_research",
                    "family": "web_research",
                },
                "candidate_tool_names": ["web_search"],
                "intent_plan": [
                    {
                        "intent_id": "intent-1",
                        "kind": "web_research",
                        "family": "web_research",
                        "status": "completed",
                        "completed_by_tool_names": ["web_search"],
                    }
                ],
            },
        },
        content="我先把已完成部分整理给你：这部分。",
    )

    thinking = next(stage for stage in turn_flow["timeline"] if stage["type"] == "thinking")
    tool_selection = next(
        stage for stage in turn_flow["timeline"] if stage["type"] == "tool_selection"
    )
    tool_execution = next(
        stage for stage in turn_flow["timeline"] if stage["type"] == "tool_execution"
    )

    assert thinking["status"] == "completed"
    assert tool_selection["status"] == "completed"
    assert tool_execution["status"] == "completed"
    assert turn_flow["answer_card"]["summary"] == "我先把已完成部分整理给你：这部分。"
    assert (
        turn_flow["answer_card"]["sections"][0]["content"]
        == "我先把已完成部分整理给你：这部分。"
    )


def test_normalize_turn_flow_keeps_missing_answer_placeholder_for_untrusted_final_output() -> None:
    turn_flow = ConversationTurnFlowProjector.project_from_metadata(
        {
            "completion_reason": "completed",
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
                        "summary": "completed",
                    },
                ],
                "answer_card": {
                    "summary": "No trusted assistant final answer.",
                    "sections": [
                        {
                            "title": "Answer",
                            "content": "No trusted assistant final answer.",
                        }
                    ],
                    "source_chip_ids": [],
                },
                "completion_reason": "completed",
            },
            "turn_record": {
                "turn_outcome": "success",
                "termination_reason": "completed",
                "final_output_source": "tool_evidence_completed",
            },
        },
        content="Fetched reddit.json",
    )

    assert turn_flow["timeline"][-1]["type"] == "failed"
    assert turn_flow["timeline"][-1]["status"] == "error"
    assert turn_flow["error_surface"]["error_type"] == "untrusted_final_output_source"
    assert turn_flow["answer_card"]["summary"] == "No trusted assistant final answer."
    assert turn_flow["answer_card"]["sections"] == [
        {
            "title": "Answer",
            "content": "No trusted assistant final answer.",
        }
    ]


def test_normalize_turn_flow_surfaces_safe_untrusted_fallback_output() -> None:
    turn_flow = ConversationTurnFlowProjector.project_from_metadata(
        {
            "turn_flow": {
                "timeline": [
                    {
                        "id": "answer_assembly",
                        "type": "answer_assembly",
                        "status": "error",
                        "title": "答案生成",
                        "summary": "答复生成失败",
                    },
                    {
                        "id": "terminal",
                        "type": "failed",
                        "status": "error",
                        "title": "本轮失败",
                        "summary": "completed",
                    },
                ],
                "answer_card": {
                    "summary": "No trusted assistant final answer.",
                    "sections": [
                        {
                            "title": "Answer",
                            "content": "No trusted assistant final answer.",
                        }
                    ],
                    "source_chip_ids": [],
                },
                "completion_reason": "completed",
            },
            "turn_record": {
                "turn_outcome": "success",
                "termination_reason": "completed",
                "final_output_source": "tool_evidence_completed",
            },
            "stripped_untrusted_final_output": True,
            "untrusted_final_output_fallback_applied": True,
        },
        content="这次处理没有成功生成最终答复，请再试一次。",
    )

    assert turn_flow["answer_card"]["summary"] == "这次处理没有成功生成最终答复，请再试一次。"
    assert turn_flow["answer_card"]["sections"] == [
        {
            "title": "Answer",
            "content": "这次处理没有成功生成最终答复，请再试一次。",
        }
    ]


def test_project_from_metadata_prefers_turn_record_turn_flow_over_polluted_message_turn_flow() -> None:
    turn_flow = ConversationTurnFlowProjector.project_from_metadata(
        {
            "turn_flow": {
                "timeline": [
                    {
                        "id": "answer_assembly",
                        "type": "answer_assembly",
                        "status": "error",
                        "title": "答案生成",
                        "summary": "答复生成失败",
                    },
                    {
                        "id": "terminal",
                        "type": "failed",
                        "status": "error",
                        "title": "本轮失败",
                        "summary": "completed",
                    },
                ],
                "answer_card": {
                    "summary": "Fetched reddit.json",
                    "sections": [
                        {
                            "title": "Answer",
                            "content": "Fetched reddit.json",
                        }
                    ],
                    "source_chip_ids": [],
                },
                "completion_reason": "completed",
            },
            "turn_record": {
                "turn_outcome": "success",
                "termination_reason": "completed",
                "final_output_source": "tool_evidence_completed",
                "metadata": {
                    "turn_flow": {
                        "timeline": [
                            {
                                "id": "answer_assembly",
                                "type": "answer_assembly",
                                "status": "error",
                                "title": "答案生成",
                                "summary": "答复生成失败",
                            },
                            {
                                "id": "terminal",
                                "type": "failed",
                                "status": "error",
                                "title": "本轮失败",
                                "summary": "completed",
                            },
                        ],
                        "answer_card": {
                            "summary": "No trusted assistant final answer.",
                            "sections": [
                                {
                                    "title": "Answer",
                                    "content": "No trusted assistant final answer.",
                                }
                            ],
                            "source_chip_ids": [],
                        },
                        "completion_reason": "completed",
                    }
                },
            },
        },
        content="Fetched reddit.json",
    )

    assert turn_flow["error_surface"]["error_type"] == "untrusted_final_output_source"
    assert turn_flow["answer_card"]["summary"] == "No trusted assistant final answer."
    assert turn_flow["answer_card"]["sections"] == [
        {
            "title": "Answer",
            "content": "No trusted assistant final answer.",
        }
    ]


def test_normalize_turn_flow_supplements_existing_tool_evidence_from_tool_calls() -> None:
    turn_flow = ConversationTurnFlowProjector.project_from_metadata(
        {
            "turn_flow": {
                "timeline": [
                    {
                        "id": "tool_execution",
                        "type": "tool_execution",
                        "status": "completed",
                        "title": "工具执行",
                        "summary": "执行了 1 个工具调用",
                    },
                    {
                        "id": "terminal",
                        "type": "completed",
                        "status": "completed",
                        "title": "本轮结束",
                        "summary": "completed",
                    },
                ],
                "evidence": [],
                "answer_card": {
                    "summary": "北京当前天气如下。",
                    "sections": [],
                    "source_chip_ids": [],
                },
                "completion_reason": "completed",
            },
        },
        content="北京当前天气如下。",
        tool_calls=[
            {
                "id": "tc_weather_1",
                "name": "get_current_weather",
                "display_name": "天气查询",
                "function": {"arguments": '{"city":"北京"}'},
                "output": "北京晴，18°C",
                "success": True,
                "summary": "北京晴，18°C",
                "summary_payload": {"temperature_c": 18},
            }
        ],
    )

    assert turn_flow["evidence"] == [
        {
            "id": "ev_tool_tc_weather_1",
            "kind": "tool",
            "title": "天气查询",
            "url": None,
            "snippet": "北京晴，18°C",
            "badge": None,
            "score": None,
            "tool_call_id": "tc_weather_1",
            "source_ref": "get_current_weather",
            "tool_name": "get_current_weather",
            "status": "success",
            "arguments": {"city": "北京"},
            "display_name": "天气查询",
            "output": "北京晴，18°C",
            "summary_payload": {"temperature_c": 18},
        }
    ]
    tool_execution = next(
        stage for stage in turn_flow["timeline"] if stage["type"] == "tool_execution"
    )
    assert tool_execution["tool_call_ids"] == ["tc_weather_1"]


def test_normalize_turn_flow_preserves_existing_tool_evidence_detail_fields() -> None:
    turn_flow = ConversationTurnFlowProjector.project_from_metadata(
        {
            "turn_flow": {
                "timeline": [
                    {
                        "id": "tool_execution",
                        "type": "tool_execution",
                        "status": "completed",
                        "title": "工具执行",
                        "summary": "执行了 1 个工具调用",
                        "tool_call_ids": ["tc_weather_1"],
                    },
                    {
                        "id": "terminal",
                        "type": "completed",
                        "status": "completed",
                        "title": "本轮结束",
                        "summary": "completed",
                    },
                ],
                "evidence": [
                    {
                        "id": "ev_tool_tc_weather_1",
                        "kind": "tool",
                        "title": "天气查询",
                        "tool_call_id": "tc_weather_1",
                        "source_ref": "get_current_weather",
                        "tool_name": "get_current_weather",
                        "status": "success",
                        "arguments": {"city": "北京"},
                        "display_name": "天气查询",
                        "output": "北京晴，18°C",
                        "summary_payload": {"temperature_c": 18},
                    }
                ],
                "answer_card": {
                    "summary": "北京当前天气如下。",
                    "sections": [],
                    "source_chip_ids": [],
                },
                "completion_reason": "completed",
            },
        },
        content="北京当前天气如下。",
    )

    assert turn_flow["evidence"][0]["tool_name"] == "get_current_weather"
    assert turn_flow["evidence"][0]["status"] == "success"
    assert turn_flow["evidence"][0]["arguments"] == {"city": "北京"}
    assert turn_flow["evidence"][0]["output"] == "北京晴，18°C"
    assert turn_flow["evidence"][0]["summary_payload"] == {"temperature_c": 18}


def test_project_from_metadata_reads_legacy_canonical_tool_calls_only_for_historical_messages() -> None:
    turn_flow = ConversationTurnFlowProjector.project_from_metadata(
        {
            "turn_record": {
                "turn_outcome": "success",
                "termination_reason": "completed",
                "metadata": {
                    "canonical_tool_calls": [
                        {
                            "id": "tc_weather_1",
                            "name": "get_current_weather",
                            "display_name": "天气查询",
                            "function": {"arguments": '{"city":"北京"}'},
                            "output": "北京晴，18°C",
                            "success": True,
                            "summary": "北京晴，18°C",
                            "summary_payload": {"temperature_c": 18},
                        }
                    ]
                },
            },
        },
        content="北京当前天气如下。",
    )

    assert turn_flow["evidence"] == [
        {
            "id": "ev_tool_tc_weather_1",
            "kind": "tool",
            "title": "天气查询",
            "url": None,
            "snippet": "北京晴，18°C",
            "badge": None,
            "score": None,
            "tool_call_id": "tc_weather_1",
            "source_ref": "get_current_weather",
            "tool_name": "get_current_weather",
            "status": "success",
            "arguments": {"city": "北京"},
            "display_name": "天气查询",
            "output": "北京晴，18°C",
            "summary_payload": {"temperature_c": 18},
        }
    ]
    tool_execution = next(
        stage for stage in turn_flow["timeline"] if stage["type"] == "tool_execution"
    )
    assert tool_execution["tool_call_ids"] == ["tc_weather_1"]


def test_normalize_turn_flow_does_not_use_legacy_canonical_tool_calls_when_canonical_turn_flow_exists() -> None:
    turn_flow = ConversationTurnFlowProjector.project_from_metadata(
        {
            "turn_flow": {
                "timeline": [
                    {
                        "id": "tool_execution",
                        "type": "tool_execution",
                        "status": "completed",
                        "title": "工具执行",
                        "summary": "执行了 1 个工具调用",
                    },
                    {
                        "id": "terminal",
                        "type": "completed",
                        "status": "completed",
                        "title": "本轮结束",
                        "summary": "completed",
                    },
                ],
                "evidence": [],
                "answer_card": {
                    "summary": "北京当前天气如下。",
                    "sections": [],
                    "source_chip_ids": [],
                },
                "completion_reason": "completed",
            },
            "turn_record": {
                "turn_outcome": "success",
                "termination_reason": "completed",
                "metadata": {
                    "canonical_tool_calls": [
                        {
                            "id": "tc_weather_1",
                            "name": "get_current_weather",
                            "display_name": "天气查询",
                            "summary": "北京晴，18°C",
                            "success": True,
                        }
                    ]
                },
            },
        },
        content="北京当前天气如下。",
    )

    assert turn_flow["evidence"] == []
    tool_execution = next(
        stage for stage in turn_flow["timeline"] if stage["type"] == "tool_execution"
    )
    assert tool_execution["tool_call_ids"] == []


def test_normalize_turn_flow_replaces_missing_answer_placeholder_with_public_error_surface_message() -> None:
    turn_flow = ConversationTurnFlowProjector.project_from_metadata(
        {
            "completion_reason": "provider_error",
            "error": True,
            "error_message": "AI 供应商服务端错误",
            "turn_flow": {
                "timeline": [
                    {
                        "id": "answer_assembly",
                        "type": "answer_assembly",
                        "status": "error",
                        "title": "答案生成",
                        "summary": "答复生成失败",
                    },
                    {
                        "id": "terminal",
                        "type": "failed",
                        "status": "error",
                        "title": "本轮失败",
                        "summary": "provider_error",
                    },
                ],
                "answer_card": {
                    "summary": "No trusted assistant final answer.",
                    "sections": [
                        {
                            "title": "Answer",
                            "content": "No trusted assistant final answer.",
                        }
                    ],
                    "source_chip_ids": [],
                    "confidence_label": "low",
                },
                "completion_reason": "provider_error",
            },
            "turn_record": {
                "turn_outcome": "partial",
                "termination_reason": "provider_error",
                "metadata": {
                    "failure_kind": "provider_http_5xx",
                },
            },
        },
        content="",
    )

    assert turn_flow["answer_card"]["summary"] == "AI 供应商服务端错误"
    assert turn_flow["answer_card"]["sections"] == [
        {
            "title": "Answer",
            "content": "AI 供应商服务端错误",
        }
    ]
    assert turn_flow["error_surface"]["message"] == "AI 供应商服务端错误"


def test_normalize_turn_flow_keeps_placeholder_when_only_default_error_surface_exists() -> None:
    turn_flow = ConversationTurnFlowProjector.project_from_metadata(
        {
            "completion_reason": "provider_error",
            "turn_flow": {
                "timeline": [
                    {
                        "id": "answer_assembly",
                        "type": "answer_assembly",
                        "status": "error",
                        "title": "答案生成",
                        "summary": "答复生成失败",
                    },
                    {
                        "id": "terminal",
                        "type": "failed",
                        "status": "error",
                        "title": "本轮失败",
                        "summary": "provider_error",
                    },
                ],
                "answer_card": {
                    "summary": "No trusted assistant final answer.",
                    "sections": [
                        {
                            "title": "Answer",
                            "content": "No trusted assistant final answer.",
                        }
                    ],
                    "source_chip_ids": [],
                },
                "completion_reason": "provider_error",
            },
            "turn_record": {
                "turn_outcome": "partial",
                "termination_reason": "provider_error",
                "metadata": {
                    "failure_kind": "stream_execution_error",
                },
            },
        },
        content="",
    )

    assert turn_flow["answer_card"]["summary"] == "No trusted assistant final answer."
    assert turn_flow["answer_card"]["sections"] == [
        {
            "title": "Answer",
            "content": "No trusted assistant final answer.",
        }
    ]


def test_project_from_metadata_strips_trace_id_suffix_from_public_error_message() -> None:
    turn_flow = ConversationTurnFlowProjector.project_from_metadata(
        {
            "completion_reason": "provider_error",
            "error": True,
            "error_message": "AI 供应商服务端错误 [trace_id=test-trace]",
            "friendly_message": "AI 供应商服务端错误 [trace_id=test-trace]",
            "turn_flow": {
                "timeline": [
                    {
                        "id": "answer_assembly",
                        "type": "answer_assembly",
                        "status": "error",
                        "title": "答案生成",
                        "summary": "答复生成失败",
                    },
                    {
                        "id": "terminal",
                        "type": "failed",
                        "status": "error",
                        "title": "本轮失败",
                        "summary": "provider_error",
                    },
                ],
                "answer_card": {
                    "summary": "No trusted assistant final answer.",
                    "sections": [
                        {
                            "title": "Answer",
                            "content": "No trusted assistant final answer.",
                        }
                    ],
                    "source_chip_ids": [],
                    "confidence_label": "low",
                },
                "completion_reason": "provider_error",
            },
            "turn_record": {
                "turn_outcome": "partial",
                "termination_reason": "provider_error",
                "metadata": {
                    "failure_kind": "provider_http_5xx",
                },
            },
        },
        content="",
    )

    assert turn_flow["answer_card"]["summary"] == "AI 供应商服务端错误"
    assert turn_flow["error_surface"]["message"] == "AI 供应商服务端错误"
