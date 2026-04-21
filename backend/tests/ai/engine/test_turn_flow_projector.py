from __future__ import annotations

from importlib import import_module

turn_flow_projector = import_module("app.ai.engine.turn_flow_projector")
build_turn_evidence_events = turn_flow_projector.build_turn_evidence_events
build_turn_flow_view_model = turn_flow_projector.build_turn_flow_view_model


def test_build_turn_flow_view_model_contains_required_contract() -> None:
    turn_flow = build_turn_flow_view_model(
        diagnostics_payload={
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
                "kind": "web",
                "title": "Example source",
                "url": "https://example.com",
                "snippet": "example snippet",
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
        stage for stage in turn_flow["timeline"] if stage.get("type") == "tool_selection"
    )
    assert tool_selection_stage["status"] == "skipped"
    assert len(turn_flow["evidence"]) == 1
    assert isinstance(turn_flow["answer_card"], dict)
    assert turn_flow["completion_reason"] == "completed"
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
