from __future__ import annotations

from importlib import import_module

turn_flow_projector = import_module("app.ai.engine.turn_flow_projector")
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
        rag_sources=[],
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
        stage for stage in turn_flow["timeline"] if stage.get("type") == "tool_selection"
    )
    assert tool_selection_stage["status"] == "skipped"
    assert len(turn_flow["evidence"]) == 1
    assert isinstance(turn_flow["answer_card"], dict)
    assert turn_flow["completion_reason"] == "completed"


def test_build_turn_flow_view_model_prefers_canonical_context_sources_over_legacy_rag_sources() -> None:
    turn_flow = build_turn_flow_view_model(
        diagnostics_payload={
            "context_sources": [
                {
                    "kind": "page",
                    "name": "Current page",
                    "metadata": {
                        "source_ref": "ctx_page_1",
                        "title": "Current page",
                        "snippet": "Read page state",
                    },
                }
            ],
            "tool_filtering": {"all_tools_count": 1, "candidate_tools_count": 0},
            "turn_events": [],
        },
        turn_record={"termination_reason": "completed"},
        rag_sources=[
            {
                "id": "legacy_page_write",
                "kind": "page_write",
                "title": "Legacy write alias",
                "snippet": "Should not be primary",
            }
        ],
        output="已读取页面。",
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
            "id": "evidence_1",
            "kind": "page",
            "output": None,
            "result_link": None,
            "score": None,
            "skill_name": None,
            "skill_type": None,
            "snippet": "Read page state",
            "source_ref": "ctx_page_1",
            "started_at": None,
            "status": None,
            "summary_payload": None,
            "title": "Current page",
            "tool_call_id": None,
            "tool_name": None,
            "url": None,
        }
    ]


def test_build_turn_flow_view_model_projects_tool_results_into_canonical_evidence() -> None:
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
        stage for stage in turn_flow["timeline"] if stage.get("type") == "tool_execution"
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


def test_build_turn_evidence_events_emits_retrieval_and_items() -> None:
    events = build_turn_evidence_events(
        [
            {
                "id": "src_web_1",
                "kind": "web",
                "title": "Web result",
                "url": "https://example.com/a",
            },
            {
                "id": "src_kb_1",
                "kind": "knowledge_base",
                "title": "KB result",
            },
        ]
    )
    assert (events[0].get("event")) == "turn_stage_update"
    assert (events[0].get("stage") or {}).get("type") == "retrieval"
    evidence_events = [event for event in events if event.get("event") == "turn_evidence"]
    assert len(evidence_events) == 2


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
        stage for stage in turn_flow["timeline"] if stage.get("type") == "answer_assembly"
    )
    final_stage = turn_flow["timeline"][-1]

    assert answer_assembly_stage["status"] == "error"
    assert final_stage["type"] == "failed"
    assert final_stage["status"] == "error"
    assert (turn_flow["answer_card"] or {}).get("confidence_label") == "low"
    assert (turn_flow["error_surface"] or {}).get("message")
    assert (turn_flow["error_surface"] or {}).get("failure_kind") == "provider_unavailable"
    assert len(turn_flow["evidence"]) == 1
    assert turn_flow["evidence"][0]["id"] == "src_2"


def test_build_turn_flow_view_model_marks_elapsed_budget_exit_as_error_terminal() -> None:
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
        stage for stage in turn_flow["timeline"] if stage.get("type") == "answer_assembly"
    )
    final_stage = turn_flow["timeline"][-1]

    assert answer_assembly_stage["status"] == "error"
    assert final_stage["type"] == "failed"
    assert final_stage["status"] == "error"
    assert (turn_flow["error_surface"] or {}).get("message")


def test_build_turn_flow_view_model_marks_hosted_web_search_timeout_as_tool_execution_error() -> None:
    turn_flow = build_turn_flow_view_model(
        diagnostics_payload={
            "turn_outcome": "partial",
            "failure_kind": "provider_timeout",
            "provider_events": [{"kind": "web_search_in_progress"}],
            "tool_filtering": {"all_tools_count": 2, "candidate_tools_count": 2},
            "turn_events": [],
        },
        turn_record={
            "turn_outcome": "partial",
            "termination_reason": "provider_timeout",
        },
        rag_sources=[],
        output="",
        completion_reason="provider_timeout",
        interrupted=False,
        error=None,
    )

    tool_execution_stage = next(
        stage for stage in turn_flow["timeline"] if stage.get("type") == "tool_execution"
    )

    assert tool_execution_stage["status"] == "error"
    assert (
        tool_execution_stage["summary"]
        == "Hosted web search timed out before results returned"
    )


def test_build_turn_flow_view_model_ignores_untrusted_tool_evidence_answer_text() -> None:
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
        stage for stage in turn_flow["timeline"] if stage.get("type") == "answer_assembly"
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
        stage for stage in turn_flow["timeline"] if stage.get("type") == "answer_assembly"
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


def test_build_turn_flow_view_model_prefers_public_error_for_untrusted_failed_output() -> None:
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
