"""
Test type: behavioral
Regression for: BUG-2026-05-06-2340
Original symptom: conversation 2340 failed with provider_unavailable but the
turn-flow read model turned runtime context diagnostics into three fake sources,
so the UI showed "found 3 sources" and completed-looking process chrome.
Scope: Turn-flow projection from runtime diagnostics and persisted turn_flow.
Mock strategy: no external services; projector logic runs directly.
"""

from __future__ import annotations

from app.ai.engine.turn_flow_projector import build_turn_flow_view_model
from app.services.ai.conversation_turn_flow_projector import (
    ConversationTurnFlowProjector,
)

RUNTIME_CONTEXT_SOURCES = [
    {
        "kind": "skill",
        "name": "skill_resolver",
        "active": True,
        "metadata": {
            "tool_count": 0,
            "selected_tool_names": [],
            "inventory_tool_count": 1,
            "inventory_selected_tool_names": ["get_current_time"],
            "turn_skill_activation_applied": False,
            "turn_skill_activation_reason": "no_turn_skill_activation",
        },
    },
    {
        "kind": "long_term_memory",
        "name": "long_term_memory",
        "active": False,
        "metadata": {
            "runtime_enabled": True,
            "recall_enabled": True,
            "capture_enabled": True,
            "recalled": False,
            "recall_count": 0,
        },
    },
    {
        "kind": "runtime_model_capability",
        "name": "gpt-5.5",
        "active": True,
        "metadata": {
            "supports_function_calling": True,
            "supports_streaming": True,
            "context_window": 128000,
            "model_code": "gpt-5.5",
            "provider_code": "provider_1",
        },
    },
]


def _retrieval_stages(turn_flow: dict) -> list[dict]:
    return [
        stage
        for stage in turn_flow.get("timeline", [])
        if stage.get("type") == "retrieval"
    ]


def test_conversation_2340_runtime_context_sources_do_not_become_evidence() -> None:
    turn_flow = ConversationTurnFlowProjector.project_from_metadata(
        {
            "completion_reason": "provider_unavailable",
            "turn_record": {
                "turn_outcome": "partial",
                "termination_reason": "provider_unavailable",
                "failure_kind": "provider_unavailable",
                "final_output_source": "partial_output",
                "selected_tool_names": [],
                "candidate_tool_names": [],
                "context_sources": RUNTIME_CONTEXT_SOURCES,
                "provider_events": [
                    {
                        "kind": "provider_unavailable",
                        "error": "Connection error.",
                        "protocol_path": "responses",
                    }
                ],
            },
        },
        content="我先把已完成部分整理给你：direct_reply。",
    )

    assert turn_flow["evidence"] == []
    assert turn_flow["answer_card"]["source_chip_ids"] == []
    assert _retrieval_stages(turn_flow) == []
    assert turn_flow["timeline"][-1]["type"] == "failed"
    assert turn_flow["timeline"][-1]["status"] == "error"
    assert turn_flow["error_surface"]["error_type"] == "untrusted_final_output_source"


def test_conversation_2340_existing_polluted_turn_flow_is_scrubbed() -> None:
    turn_flow = ConversationTurnFlowProjector.project_from_metadata(
        {
            "completion_reason": "provider_unavailable",
            "turn_flow": {
                "timeline": [
                    {
                        "id": "retrieval",
                        "type": "retrieval",
                        "status": "completed",
                        "title": "Retrieval",
                        "summary": "Retrieved 3 sources",
                        "metrics": {"source_count": 3},
                        "source_refs": ["evidence_1", "evidence_2", "evidence_3"],
                    },
                    {
                        "id": "failed",
                        "type": "failed",
                        "status": "error",
                        "summary": "provider_unavailable",
                    },
                ],
                "evidence": [
                    {
                        "id": "evidence_1",
                        "kind": "knowledge_base",
                        "title": "skill_resolver",
                    },
                    {
                        "id": "evidence_2",
                        "kind": "memory",
                        "title": "long_term_memory",
                    },
                    {
                        "id": "evidence_3",
                        "kind": "knowledge_base",
                        "title": "gpt-5.5",
                    },
                ],
                "answer_card": {
                    "summary": "Connection error.",
                    "sections": [{"title": "Answer", "content": "Connection error."}],
                    "source_chip_ids": ["evidence_1", "evidence_2", "evidence_3"],
                },
                "completion_reason": "provider_unavailable",
                "error_surface": {
                    "message": "Connection error.",
                    "failure_kind": "provider_unavailable",
                    "error_type": "untrusted_final_output_source",
                },
            },
            "turn_record": {
                "turn_outcome": "partial",
                "termination_reason": "provider_unavailable",
                "failure_kind": "provider_unavailable",
                "final_output_source": "partial_output",
            },
        },
        content="我先把已完成部分整理给你：direct_reply。",
    )

    retrieval = _retrieval_stages(turn_flow)
    assert turn_flow["evidence"] == []
    assert turn_flow["answer_card"]["source_chip_ids"] == []
    assert retrieval == [
        {
            "id": "retrieval",
            "type": "retrieval",
            "status": "skipped",
            "title": "Retrieval",
            "summary": "整理了 0 条证据",
            "detail_lines": ["整理了 0 条证据"],
            "started_at_ms": None,
            "ended_at_ms": None,
            "duration_ms": None,
            "metrics": {"source_count": 0, "evidence_count": 0},
            "tool_call_ids": [],
            "source_refs": [],
        }
    ]


def test_engine_turn_flow_uses_rag_sources_not_runtime_context_sources() -> None:
    turn_flow = build_turn_flow_view_model(
        diagnostics_payload={
            "context_sources": RUNTIME_CONTEXT_SOURCES,
            "tool_filtering": {"all_tools_count": 1, "candidate_tools_count": 0},
            "turn_events": [],
            "turn_outcome": "partial",
            "failure_kind": "provider_unavailable",
        },
        turn_record={
            "turn_outcome": "partial",
            "termination_reason": "provider_unavailable",
            "failure_kind": "provider_unavailable",
            "final_output_source": "partial_output",
        },
        rag_sources=[],
        output="我先把已完成部分整理给你：direct_reply。",
        completion_reason="provider_unavailable",
        interrupted=False,
        error="Connection error.",
    )

    retrieval = _retrieval_stages(turn_flow)
    assert turn_flow["evidence"] == []
    assert turn_flow["answer_card"]["source_chip_ids"] == []
    assert retrieval[0]["status"] == "skipped"
    assert retrieval[0]["metrics"]["source_count"] == 0
    assert turn_flow["timeline"][-1]["type"] == "failed"
    assert turn_flow["timeline"][-1]["status"] == "error"
