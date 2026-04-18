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


def test_project_from_metadata_reclassifies_stored_completed_turn_flow_for_incomplete_page_reply() -> None:
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
                    "summary": "我先帮你检查一下页面上有没有可用的搜索区域或关键词“发票”的相关内容喵~",
                    "sections": [],
                    "source_chip_ids": [],
                },
                "completion_reason": "completed",
            },
            "context_diagnostics": {
                "conversation_outcome": "success",
                "turn_outcome": "success",
                "continuation_source": "page_ops",
                "tool_planner": {
                    "intent": "page_search",
                    "family": "page_ops",
                },
                "intent_plan": [
                    {
                        "intent_id": "intent-1",
                        "kind": "page_search",
                        "family": "page_ops",
                        "status": "completed",
                        "completed_by_tool_names": ["ui_list_interactables"],
                    }
                ],
                "candidate_tool_names": [
                    "ui_read_region",
                    "ui_list_interactables",
                    "ui_click",
                ],
                "selected_tool_names": [],
            },
        },
        content="我先帮你检查一下页面上有没有可用的搜索区域或关键词“发票”的相关内容喵~",
    )

    assert turn_flow["completion_reason"] == "incomplete_promissory_reply"
    assert turn_flow["timeline"][-1]["type"] == "failed"
    assert turn_flow["timeline"][-1]["status"] == "error"
    assert turn_flow["error_surface"]["error_type"] == "incomplete_promissory_reply"
    answer_assembly = next(
        stage for stage in turn_flow["timeline"] if stage["type"] == "answer_assembly"
    )
    assert answer_assembly["status"] == "error"


def test_project_from_metadata_uses_completed_tool_names_when_selected_tools_missing() -> None:
    turn_flow = ConversationTurnFlowProjector.project_from_metadata(
        {
            "context_diagnostics": {
                "tool_planner": {
                    "intent": "page_search",
                    "family": "page_ops",
                },
                "candidate_tool_names": [
                    "ui_read_region",
                    "ui_list_interactables",
                    "ui_click",
                ],
                "intent_plan": [
                    {
                        "intent_id": "intent-1",
                        "kind": "page_search",
                        "family": "page_ops",
                        "status": "completed",
                        "completed_by_tool_names": ["ui_list_interactables"],
                    }
                ],
            },
        },
        content="已定位到页面上的搜索区域。",
    )

    tool_selection = next(
        stage for stage in turn_flow["timeline"] if stage["type"] == "tool_selection"
    )
    assert tool_selection["summary"] == "已从 3 个工具中筛选 1 个"
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
                    "intent": "page_summary",
                    "family": "page_ops",
                },
                "candidate_tool_names": ["ui_get_snapshot"],
                "intent_plan": [
                    {
                        "intent_id": "intent-1",
                        "kind": "page_summary",
                        "family": "page_ops",
                        "status": "completed",
                        "completed_by_tool_names": ["ui_get_snapshot"],
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
    assert tool_execution["status"] == "completed"
    assert tool_execution["summary"] == "执行了 1 个工具调用"
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
                    "intent": "page_summary",
                    "family": "page_ops",
                },
                "candidate_tool_names": ["ui_get_snapshot"],
                "intent_plan": [
                    {
                        "intent_id": "intent-1",
                        "kind": "page_summary",
                        "family": "page_ops",
                        "status": "completed",
                        "completed_by_tool_names": ["ui_get_snapshot"],
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
