"""
Test type: structural / behavioral
Scope: turn-flow view-model projection and canonical evidence fields.
Mock strategy: no external services; projector helpers run directly.
"""

from __future__ import annotations

from importlib import import_module

turn_flow_projector = import_module("app.ai.engine.turn_flow_projector")
build_tool_execution_result_evidence_event = (
    turn_flow_projector.build_tool_execution_result_evidence_event
)
build_tool_execution_started_evidence_event = (
    turn_flow_projector.build_tool_execution_started_evidence_event
)
build_turn_evidence_events = turn_flow_projector.build_turn_evidence_events
build_turn_flow_view_model = turn_flow_projector.build_turn_flow_view_model


def test_build_turn_flow_view_model_contains_required_contract() -> None:
    turn_flow = build_turn_flow_view_model(
        diagnostics_payload={
            "context_sources": [
                {
                    "kind": "web",
                    "name": "Example source",
                    "metadata": {
                        "source_ref": "src_1",
                        "title": "Example source",
                        "url": "https://example.com",
                        "snippet": "example snippet",
                    },
                }
            ],
            "tool_filtering": {"all_tools_count": 15, "candidate_tools_count": 0},
            "turn_events": [
                {"kind": "turn.started", "timestamp_ms": 1, "data": {}},
                {"kind": "turn.model_called", "timestamp_ms": 8, "data": {}},
            ],
        },
        turn_record={"termination_reason": "completed"},
        rag_sources=[
            {
                "id": "src_1",
                "kind": "knowledge_base",
                "title": "Example source",
                "url": "https://example.com",
                "snippet": "example snippet",
                "source_ref": "src_1",
            }
        ],
        output="Final answer body",
        completion_reason="completed",
        interrupted=False,
        error=None,
    )

    assert set(turn_flow.keys()) == {
        "timeline",
        "evidence",
        "answer_card",
        "completion_reason",
        "interrupted",
        "error_surface",
    }
    tool_selection_stage = next(
        stage
        for stage in turn_flow["timeline"]
        if stage.get("type") == "tool_selection"
    )
    assert tool_selection_stage["status"] == "skipped"
    assert len(turn_flow["evidence"]) == 1
    assert isinstance(turn_flow["answer_card"], dict)
    assert turn_flow["completion_reason"] == "completed"


def test_build_turn_flow_view_model_uses_rag_sources_not_context_diagnostics() -> None:
    turn_flow = build_turn_flow_view_model(
        diagnostics_payload={
            "context_sources": [
                {
                    "kind": "knowledge_base",
                    "name": "Knowledge base source",
                    "metadata": {
                        "source_ref": "ctx_kb_1",
                        "title": "Knowledge base source",
                        "snippet": "Matched document excerpt",
                    },
                }
            ],
            "tool_filtering": {"all_tools_count": 1, "candidate_tools_count": 0},
            "turn_events": [],
        },
        turn_record={"termination_reason": "completed"},
        rag_sources=[
            {
                "id": "fallback_kb_source",
                "kind": "knowledge_base",
                "title": "Fallback KB alias",
                "snippet": "Should not be primary",
            }
        ],
        output="已读取知识库资料。",
        completion_reason="completed",
        interrupted=False,
        error=None,
    )

    assert turn_flow["evidence"] == [
        {
            "arguments": None,
            "badge": None,
            "display_name": None,
            "duration_ms": None,
            "error": None,
            "error_type": None,
            "id": "fallback_kb_source",
            "kind": "knowledge_base",
            "output": None,
            "result_link": None,
            "score": None,
            "skill_name": None,
            "skill_type": None,
            "source_kind": None,
            "doc_id": None,
            "doc_name": None,
            "chunk_id": None,
            "knowledge_base_id": None,
            "knowledge_base_name": None,
            "snippet": "Should not be primary",
            "source_ref": "fallback_kb_source",
            "started_at": None,
            "status": None,
            "summary_payload": None,
            "title": "Fallback KB alias",
            "tool_call_id": None,
            "tool_name": None,
            "url": None,
        }
    ]


def test_build_turn_flow_view_model_projects_tool_results_into_canonical_evidence() -> (
    None
):
    turn_flow = build_turn_flow_view_model(
        diagnostics_payload={
            "tool_filtering": {"all_tools_count": 15, "candidate_tools_count": 1},
            "turn_events": [
                {"kind": "turn.started", "timestamp_ms": 1, "data": {}},
                {"kind": "turn.tool_round", "timestamp_ms": 4, "data": {}},
                {
                    "kind": "turn.tool_completed",
                    "timestamp_ms": 9,
                    "data": {
                        "tool_call_id": "tc_weather_1",
                        "tool_name": "get_current_weather",
                    },
                },
            ],
        },
        turn_record={"termination_reason": "completed"},
        rag_sources=[],
        tool_results=[
            {
                "display_name": "天气查询",
                "duration_ms": 2917,
                "name": "get_current_weather",
                "output": "北京晴，18°C",
                "success": True,
                "summary": "已查询北京天气",
                "summary_payload": {"temperature_c": 18},
                "tool_call_id": "tc_weather_1",
            }
        ],
        output="北京今天晴，18°C",
        completion_reason="completed",
        interrupted=False,
        error=None,
    )

    tool_execution_stage = next(
        stage
        for stage in turn_flow["timeline"]
        if stage.get("type") == "tool_execution"
    )

    assert tool_execution_stage["tool_call_ids"] == ["tc_weather_1"]
    assert turn_flow["evidence"] == [
        {
            "arguments": None,
            "badge": None,
            "display_name": "天气查询",
            "duration_ms": 2917,
            "error": None,
            "error_type": None,
            "id": "tc_weather_1",
            "kind": "tool",
            "output": "北京晴，18°C",
            "result_link": None,
            "score": None,
            "skill_name": None,
            "skill_type": None,
            "source_kind": None,
            "doc_id": None,
            "doc_name": None,
            "chunk_id": None,
            "knowledge_base_id": None,
            "knowledge_base_name": None,
            "snippet": "已查询北京天气",
            "source_ref": "get_current_weather",
            "started_at": None,
            "status": "success",
            "summary_payload": {"temperature_c": 18},
            "title": "天气查询",
            "tool_call_id": "tc_weather_1",
            "tool_name": "get_current_weather",
            "url": None,
        }
    ]


def test_build_tool_execution_started_evidence_event_marks_tool_running() -> None:
    event = build_tool_execution_started_evidence_event(
        tool_name="query_records",
        arguments={"question": "统计今天调用情况"},
        skill_info={"skill_name": "报表技能", "skill_type": "toolkit"},
        tool_call_id="tc_live_1",
    )

    assert event["event"] == "turn_evidence"
    evidence = event["evidence"]
    assert evidence["id"] == "tc_live_1"
    assert evidence["kind"] == "tool"
    assert evidence["status"] == "running"
    assert evidence["tool_call_id"] == "tc_live_1"
    assert evidence["tool_name"] == "query_records"
    assert evidence["arguments"] == {"question": "统计今天调用情况"}
    assert evidence["skill_name"] == "报表技能"
    assert evidence["skill_type"] == "toolkit"


def test_build_tool_execution_result_evidence_event_preserves_result_details() -> None:
    event = build_tool_execution_result_evidence_event(
        result={
            "display_name": "报表查询",
            "name": "query_records",
            "output": "查询完成",
            "success": True,
            "summary": "已查询今天调用情况",
            "summary_payload": {"tables": ["ai_call_logs"]},
            "tool_call_id": "tc_live_1",
        },
        duration_ms=27,
        arguments={"question": "统计今天调用情况"},
        skill_info={"skill_name": "报表技能", "skill_type": "toolkit"},
    )

    assert event is not None
    assert event["event"] == "turn_evidence"
    evidence = event["evidence"]
    assert evidence["id"] == "tc_live_1"
    assert evidence["display_name"] == "报表查询"
    assert evidence["duration_ms"] == 27
    assert evidence["output"] == "查询完成"
    assert evidence["snippet"] == "已查询今天调用情况"
    assert evidence["status"] == "success"
    assert evidence["summary_payload"] == {"tables": ["ai_call_logs"]}
    assert evidence["tool_call_id"] == "tc_live_1"


def test_build_turn_evidence_events_emits_retrieval_and_items() -> None:
    events = build_turn_evidence_events(
        [
            {
                "id": "src_kb_1",
                "kind": "knowledge_base",
                "title": "KB result",
            },
        ]
    )
    assert (events[0].get("event")) == "turn_stage_update"
    assert (events[0].get("stage") or {}).get("type") == "retrieval"
    evidence_events = [
        event for event in events if event.get("event") == "turn_evidence"
    ]
    assert len(evidence_events) == 1
    assert [event["evidence"]["kind"] for event in evidence_events] == [
        "knowledge_base",
    ]


def test_build_turn_evidence_events_preserves_formal_kb_identity() -> None:
    events = build_turn_evidence_events(
        [
            {
                "chunk_id": 301,
                "doc_id": 21,
                "doc_name": "test_doc.txt",
                "knowledge_base_id": 1,
                "knowledge_base_name": "测试知识库",
                "score": 0.82,
                "snippet": "NovusAI 平台支持知识库 RAG。",
                "source_kind": "formal_kb",
            },
        ]
    )

    evidence_event = next(
        event for event in events if event.get("event") == "turn_evidence"
    )
    evidence = evidence_event["evidence"]
    assert evidence["kind"] == "knowledge_base"
    assert evidence["source_kind"] == "formal_kb"
    assert evidence["knowledge_base_id"] == 1
    assert evidence["knowledge_base_name"] == "测试知识库"
    assert evidence["doc_id"] == 21
    assert evidence["doc_name"] == "test_doc.txt"
    assert evidence["chunk_id"] == 301


def test_build_turn_evidence_events_drops_retired_page_search_and_url_sources() -> None:
    events = build_turn_evidence_events(
        [
            {"id": "page-source", "kind": "page", "title": "Page source"},
            {"id": "search-source", "kind": "search", "title": "Search source"},
            {"id": "url-source", "kind": "url", "title": "URL source"},
            {"id": "url-only-source", "title": "URL only", "url": "https://e.test"},
        ]
    )

    evidence_events = [
        event for event in events if event.get("event") == "turn_evidence"
    ]

    assert evidence_events == []


def test_build_turn_flow_view_model_marks_partial_failure_as_error_terminal() -> None:
    turn_flow = build_turn_flow_view_model(
        diagnostics_payload={
            "failure_kind": "provider_unavailable",
            "turn_outcome": "partial",
            "tool_filtering": {"all_tools_count": 3, "candidate_tools_count": 1},
            "turn_events": [
                {"kind": "turn.started", "timestamp_ms": 1, "data": {}},
                {"kind": "turn.model_called", "timestamp_ms": 9, "data": {}},
            ],
        },
        turn_record={
            "turn_outcome": "partial",
            "termination_reason": "provider_failure_after_partial_progress",
        },
        rag_sources=[
            {
                "id": "src_2",
                "kind": "web",
                "title": "Preserved evidence",
                "url": "https://example.com/failure",
            }
        ],
        output="",
        completion_reason="provider_failure_after_partial_progress",
        interrupted=False,
        error=None,
    )

    answer_assembly_stage = next(
        stage
        for stage in turn_flow["timeline"]
        if stage.get("type") == "answer_assembly"
    )
    final_stage = turn_flow["timeline"][-1]

    assert answer_assembly_stage["status"] == "error"
    assert final_stage["type"] == "failed"
    assert final_stage["status"] == "error"
    assert (turn_flow["answer_card"] or {}).get("confidence_label") == "low"
    assert (turn_flow["error_surface"] or {}).get("message")
    assert (turn_flow["error_surface"] or {}).get(
        "failure_kind"
    ) == "provider_unavailable"
    assert turn_flow["evidence"] == []


def test_build_turn_flow_view_model_marks_elapsed_budget_exit_as_error_terminal() -> (
    None
):
    turn_flow = build_turn_flow_view_model(
        diagnostics_payload={
            "turn_outcome": "partial",
            "failure_kind": "budget_exit",
            "budget_status": "exited",
            "budget_exit_reason": "elapsed_budget_exceeded",
            "tool_filtering": {"all_tools_count": 2, "candidate_tools_count": 1},
            "turn_events": [
                {"kind": "turn.started", "timestamp_ms": 1, "data": {}},
                {"kind": "turn.model_called", "timestamp_ms": 7, "data": {}},
            ],
        },
        turn_record={
            "turn_outcome": "partial",
            "termination_reason": "elapsed_budget_exceeded",
        },
        rag_sources=[],
        output="",
        completion_reason="elapsed_budget_exceeded",
        interrupted=False,
        error=None,
    )

    answer_assembly_stage = next(
        stage
        for stage in turn_flow["timeline"]
        if stage.get("type") == "answer_assembly"
    )
    final_stage = turn_flow["timeline"][-1]

    assert answer_assembly_stage["status"] == "error"
    assert final_stage["type"] == "failed"
    assert final_stage["status"] == "error"
    assert (turn_flow["error_surface"] or {}).get("message")


def test_build_turn_flow_view_model_ignores_untrusted_tool_evidence_answer_text() -> (
    None
):
    turn_flow = build_turn_flow_view_model(
        diagnostics_payload={
            "final_output_source": "tool_evidence_completed",
            "tool_filtering": {"all_tools_count": 2, "candidate_tools_count": 1},
            "turn_events": [],
        },
        turn_record={"termination_reason": "completed"},
        rag_sources=[
            {
                "id": "src_3",
                "kind": "web",
                "title": "Evidence",
            }
        ],
        output="raw fetched snippet should not be summary",
        completion_reason="completed",
        interrupted=False,
        error=None,
    )

    answer_assembly_stage = next(
        stage
        for stage in turn_flow["timeline"]
        if stage.get("type") == "answer_assembly"
    )
    answer_card = turn_flow["answer_card"] or {}

    assert answer_assembly_stage["status"] == "skipped"
    assert answer_card.get("summary") == "No trusted assistant final answer."
    assert answer_card.get("confidence_label") == "low"


def test_build_turn_flow_view_model_surfaces_safe_untrusted_fallback_output() -> None:
    turn_flow = build_turn_flow_view_model(
        diagnostics_payload={
            "final_output_source": "tool_evidence_completed",
            "stripped_untrusted_final_output": True,
            "untrusted_final_output_fallback_applied": True,
            "tool_filtering": {"all_tools_count": 2, "candidate_tools_count": 1},
            "turn_events": [],
        },
        turn_record={"termination_reason": "completed"},
        rag_sources=[],
        output="这次处理没有成功生成最终答复，请再试一次。",
        completion_reason="completed",
        interrupted=False,
        error=None,
    )

    answer_assembly_stage = next(
        stage
        for stage in turn_flow["timeline"]
        if stage.get("type") == "answer_assembly"
    )
    answer_card = turn_flow["answer_card"] or {}

    assert answer_assembly_stage["status"] == "completed"
    assert answer_card.get("summary") == "这次处理没有成功生成最终答复，请再试一次。"
    assert answer_card.get("sections") == [
        {
            "id": "final_answer",
            "title": "Answer",
            "content": "这次处理没有成功生成最终答复，请再试一次。",
        }
    ]


def test_build_turn_flow_view_model_uses_safe_fallback_for_terminal_error_surface() -> (
    None
):
    safe_partial = "我没有拿到足够可靠的答案质量证据，因此暂时不生成结论。"
    turn_flow = build_turn_flow_view_model(
        diagnostics_payload={
            "final_output_source": "partial_output",
            "failure_kind": "no_answer_quality_evidence",
            "stripped_untrusted_final_output": True,
            "turn_outcome": "partial",
            "untrusted_final_output_fallback_applied": True,
            "tool_filtering": {"all_tools_count": 3, "candidate_tools_count": 2},
            "turn_events": [],
        },
        turn_record={"termination_reason": "no_answer_quality_evidence"},
        rag_sources=[],
        output=safe_partial,
        completion_reason="no_answer_quality_evidence",
        interrupted=False,
        error=None,
    )

    answer_card = turn_flow["answer_card"] or {}
    error_surface = turn_flow["error_surface"] or {}

    assert answer_card.get("summary") == safe_partial
    assert error_surface.get("message") == safe_partial
    assert error_surface.get("message") != (
        "The assistant could not finish this turn. Please retry."
    )
    assert (turn_flow["error_surface"] or {}).get(
        "error_type"
    ) == "untrusted_final_output_source"


def test_build_turn_flow_view_model_prefers_public_error_for_untrusted_failed_output() -> (
    None
):
    turn_flow = build_turn_flow_view_model(
        diagnostics_payload={
            "final_output_source": "partial_output",
            "failure_kind": "provider_http_5xx",
            "turn_outcome": "partial",
            "tool_filtering": {"all_tools_count": 4, "candidate_tools_count": 4},
            "turn_events": [],
        },
        turn_record={"termination_reason": "provider_error"},
        rag_sources=[],
        output="内部 partial output 不应展示",
        completion_reason="provider_error",
        interrupted=False,
        error="AI 供应商服务端错误",
    )

    answer_card = turn_flow["answer_card"] or {}

    assert answer_card.get("summary") == "AI 供应商服务端错误"
    assert answer_card.get("sections") == [
        {
            "id": "final_answer",
            "title": "Answer",
            "content": "AI 供应商服务端错误",
        }
    ]
    assert (turn_flow["error_surface"] or {}).get("error_type") == (
        "untrusted_final_output_source"
    )


def test_build_turn_flow_view_model_strips_trace_id_suffix_from_error_surface() -> None:
    turn_flow = build_turn_flow_view_model(
        diagnostics_payload={
            "final_output_source": "partial_output",
            "failure_kind": "provider_http_5xx",
            "turn_outcome": "partial",
            "tool_filtering": {"all_tools_count": 1, "candidate_tools_count": 1},
            "turn_events": [],
        },
        turn_record={"termination_reason": "provider_error"},
        rag_sources=[],
        output="",
        completion_reason="provider_error",
        interrupted=False,
        error="AI 供应商服务端错误 [trace_id=test-trace]",
    )

    assert turn_flow["answer_card"]["summary"] == "AI 供应商服务端错误"
    assert turn_flow["error_surface"]["message"] == "AI 供应商服务端错误"


# --- ReAct round projection tests ---


build_react_round_started_event = (
    turn_flow_projector.build_react_round_started_event
)
build_react_answer_assembly_event = (
    turn_flow_projector.build_react_answer_assembly_event
)


def test_react_round_projects_tool_selection_from_round_events() -> None:
    """ReAct 多轮执行时，tool_selection stage 从 react_round 事件导出。"""
    turn_flow = build_turn_flow_view_model(
        diagnostics_payload={
            "turn_events": [
                {
                    "kind": "turn.round_started",
                    "timestamp_ms": 10,
                    "data": {
                        "round_kind": "react_round",
                        "tool_names": ["get_weather", "search_kb", "memory_save"],
                    },
                },
                {
                    "kind": "turn.round_started",
                    "timestamp_ms": 500,
                    "data": {
                        "round_kind": "react_round",
                        "tool_names": ["get_weather", "search_kb", "memory_save"],
                    },
                },
            ],
        },
        turn_record={"termination_reason": "completed"},
        rag_sources=[],
        tool_results=[
            {
                "name": "get_weather",
                "success": True,
                "output": "北京晴",
                "tool_call_id": "tc_1",
            },
            {
                "name": "search_kb",
                "success": True,
                "output": "KB result",
                "tool_call_id": "tc_2",
            },
        ],
        output="北京今天晴天。",
        completion_reason="completed",
        interrupted=False,
        error=None,
    )

    tool_selection_stage = next(
        stage
        for stage in turn_flow["timeline"]
        if stage.get("type") == "tool_selection"
    )
    assert tool_selection_stage["status"] == "completed"
    assert tool_selection_stage["metrics"]["all_tools_count"] == 3
    assert tool_selection_stage["metrics"]["filtering_reason"] == "react_full_toolset"


def test_react_round_projects_tool_execution_with_react_round_count() -> None:
    """ReAct 多轮执行时，tool_execution stage 正确聚合 react_round 轮次。"""
    turn_flow = build_turn_flow_view_model(
        diagnostics_payload={
            "turn_events": [
                {
                    "kind": "turn.round_started",
                    "timestamp_ms": 10,
                    "data": {"round_kind": "react_round", "tool_names": ["a", "b"]},
                },
                {
                    "kind": "turn.round_started",
                    "timestamp_ms": 200,
                    "data": {"round_kind": "react_round", "tool_names": ["a", "b"]},
                },
                {
                    "kind": "turn.round_started",
                    "timestamp_ms": 400,
                    "data": {"round_kind": "react_round", "tool_names": ["a", "b"]},
                },
            ],
        },
        turn_record={"termination_reason": "completed"},
        rag_sources=[],
        tool_results=[
            {"name": "a", "success": True, "output": "r1", "tool_call_id": "tc_1"},
            {"name": "b", "success": True, "output": "r2", "tool_call_id": "tc_2"},
            {"name": "a", "success": False, "error": "timeout", "tool_call_id": "tc_3"},
        ],
        output="最终答案",
        completion_reason="completed",
        interrupted=False,
        error=None,
    )

    tool_execution_stage = next(
        stage
        for stage in turn_flow["timeline"]
        if stage.get("type") == "tool_execution"
    )
    assert tool_execution_stage["metrics"]["react_rounds"] == 3
    assert tool_execution_stage["metrics"]["tool_call_count"] == 3
    assert tool_execution_stage["metrics"]["completed_tool_calls"] == 2
    assert tool_execution_stage["metrics"]["failed_tool_calls"] == 1
    assert tool_execution_stage["status"] == "error"  # 有失败的工具


def test_build_react_round_started_event_emits_thinking_and_tool_selection() -> None:
    """build_react_round_started_event 发出 thinking 和 tool_selection 阶段事件。"""
    events = build_react_round_started_event(round_index=0, tool_count=5)

    assert len(events) == 2
    thinking_event = events[0]
    assert thinking_event["stage"]["type"] == "thinking"
    assert thinking_event["stage"]["status"] == "running"
    assert "ReAct round 1" in thinking_event["stage"]["summary"]

    selection_event = events[1]
    assert selection_event["stage"]["type"] == "tool_selection"
    assert selection_event["stage"]["status"] == "running"
    assert selection_event["stage"]["metrics"]["all_tools_count"] == 5


def test_build_react_round_started_event_skips_tool_selection_when_no_tools() -> None:
    """没有工具时只发出 thinking 事件。"""
    events = build_react_round_started_event(round_index=2, tool_count=0)

    assert len(events) == 1
    assert events[0]["stage"]["type"] == "thinking"


def test_build_react_answer_assembly_event_emits_stage() -> None:
    """build_react_answer_assembly_event 发出 answer_assembly 阶段事件。"""
    event = build_react_answer_assembly_event()
    assert event["stage"]["type"] == "answer_assembly"
    assert event["stage"]["status"] == "running"
    assert "Synthesizing" in event["stage"]["summary"]


def test_react_round_tool_selection_skipped_when_no_tools_available() -> None:
    """ReAct 模式且无工具时，tool_selection stage 应为 skipped。"""
    turn_flow = build_turn_flow_view_model(
        diagnostics_payload={
            "turn_events": [
                {
                    "kind": "turn.round_started",
                    "timestamp_ms": 10,
                    "data": {"round_kind": "react_round", "tool_names": []},
                },
            ],
        },
        turn_record={"termination_reason": "completed"},
        rag_sources=[],
        tool_results=None,
        output="纯文本回复",
        completion_reason="completed",
        interrupted=False,
        error=None,
    )

    tool_selection_stage = next(
        stage
        for stage in turn_flow["timeline"]
        if stage.get("type") == "tool_selection"
    )
    assert tool_selection_stage["status"] == "skipped"
