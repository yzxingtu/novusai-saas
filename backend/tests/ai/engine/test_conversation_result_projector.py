"""
Test type: structural
Scope: conversation execution-result projection and stable diagnostic fields.
Mock strategy: service collaborators use fakes; projection helpers run real logic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from importlib import import_module
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.ai.engine.conversation import ConversationEngine
from app.ai.engine.conversation_result_projector import (
    build_execution_result,
    build_turn_projection,
    coerce_turn_record_payload,
)
from app.ai.engine.final_output_policy import build_untrusted_final_output_fallback
from app.ai.engine.recovery_web_research_gate import (
    WEB_RESEARCH_TERMINAL_CONTRACT_KEY,
    WEB_RESEARCH_TERMINAL_NO_RESULT,
)
from app.ai.engine.types import ExecutionRequest, PreparedExecution
from app.ai.tools.types import ToolDefinition
from app.ai.types import ChatMessage, ChatResponse

conversation_entrypoints_module = import_module(
    "app.ai.engine.conversation_entrypoints"
)
conversation_result_projector_module = import_module(
    "app.ai.engine.conversation_result_projector"
)


@dataclass
class _TurnRecordData:
    turn_outcome: str = "success"
    termination_reason: str = "completed"
    metadata: dict[str, object] = field(default_factory=dict)


def test_coerce_turn_record_payload_supports_dataclass() -> None:
    payload = coerce_turn_record_payload(_TurnRecordData(metadata={"seed": "value"}))

    assert payload["turn_outcome"] == "success"
    assert payload["termination_reason"] == "completed"
    assert payload["metadata"] == {"seed": "value"}


def test_build_turn_projection_preserves_success_turn_metadata() -> None:
    projection = build_turn_projection(
        raw_turn_record=_TurnRecordData(metadata={"seed": "value"}),
        diagnostics_payload={
            "intent_plan": [{"intent_id": "intent-1"}],
            "budget_status": "ok",
            "conversation_outcome": "success",
        },
        execution_path="normal",
        completion_reason="completed",
        partial=False,
        final_output_source="assistant",
    )

    assert projection.diagnostics["final_output_source"] == "assistant"
    assert projection.turn_record["execution_path"] == "normal"
    assert projection.turn_record["turn_outcome"] == "success"
    assert projection.turn_record["termination_reason"] == "completed"
    assert projection.turn_record["conversation_outcome"] == "success"
    assert projection.turn_record["metadata"]["seed"] == "value"
    assert (
        projection.turn_record["metadata"]["turn_diagnostics"] == projection.diagnostics
    )


def test_build_turn_projection_marks_partial_exit_from_completion_reason() -> None:
    projection = build_turn_projection(
        raw_turn_record={},
        diagnostics_payload={},
        execution_path="deep",
        completion_reason="completion_budget_exceeded",
        partial=True,
        final_output_source="budget_fallback",
    )

    assert projection.diagnostics["partial_exit_reason"] == "completion_budget_exceeded"
    assert projection.diagnostics["final_output_source"] == "budget_fallback"
    assert projection.turn_record["turn_outcome"] == "partial"
    assert projection.turn_record["termination_reason"] == "completion_budget_exceeded"
    assert projection.turn_record["partial_exit_reason"] == "completion_budget_exceeded"


def test_build_execution_result_uses_projection_and_runtime_model_info() -> None:
    projection = build_turn_projection(
        raw_turn_record={},
        diagnostics_payload={"conversation_outcome": "success"},
        execution_path="fast",
        completion_reason="completed",
        partial=False,
        final_output_source="assistant",
        default_turn_outcome="success",
        force_completion_reason_in_turn_record=True,
        protocol_path="responses",
    )

    result = build_execution_result(
        success=True,
        output="done",
        messages=[{"role": "assistant", "content": "done"}],
        tool_results=[],
        total_tokens=12,
        duration_ms=34,
        conversation_id=7,
        runtime_model_info={
            "model_id": 3,
            "model_name": "gpt-5.4",
            "provider_id": 9,
            "provider_name": "provider-a",
        },
        completion_reason="completed",
        rag_sources=None,
        rag_source_kinds=["knowledge_base"],
        turn_projection=projection,
        provider_events=[{"protocol": "responses"}],
    )

    assert result.runtime_model_name == "gpt-5.4"
    assert result.runtime_provider_name == "provider-a"
    assert result.turn_record["protocol_path"] == "responses"
    assert result.turn_record["termination_reason"] == "completed"
    assert result.diagnostics["final_output_source"] == "assistant"


def test_build_execution_result_accepts_explicit_diagnostics_without_projection() -> (
    None
):
    result = build_execution_result(
        success=False,
        output="",
        messages=[],
        tool_results=[],
        total_tokens=0,
        duration_ms=12,
        conversation_id=None,
        runtime_model_info=None,
        error="error",
        completion_reason="error",
        diagnostics={"failure_kind": "provider_timeout"},
    )

    assert result.diagnostics["failure_kind"] == "provider_timeout"
    assert isinstance(result.diagnostics.get("turn_flow"), dict)
    assert result.turn_record is None


def test_build_execution_result_sanitizes_untrusted_output_for_turn_flow(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, str] = {}

    def _fake_build_turn_flow_view_model(**kwargs):
        captured["output"] = str(kwargs.get("output") or "")
        return {
            "timeline": [],
            "evidence": [],
            "answer_card": {},
            "completion_reason": "completed",
            "interrupted": False,
            "error_surface": None,
        }

    monkeypatch.setattr(
        conversation_result_projector_module,
        "build_turn_flow_view_model",
        _fake_build_turn_flow_view_model,
    )

    projection = build_turn_projection(
        raw_turn_record={},
        diagnostics_payload={"final_output_source": "tool_evidence_completed"},
        execution_path="fast",
        completion_reason="completed",
        partial=False,
        final_output_source="tool_evidence_completed",
    )
    build_execution_result(
        success=True,
        output="fetched snippet should not be trusted answer",
        messages=[],
        tool_results=[],
        total_tokens=0,
        duration_ms=0,
        conversation_id=None,
        runtime_model_info=None,
        completion_reason="completed",
        turn_projection=projection,
    )

    assert captured["output"] == ""


def test_build_execution_result_keeps_recovery_evidence_output_for_turn_flow(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, str] = {}

    def _fake_build_turn_flow_view_model(**kwargs):
        captured["output"] = str(kwargs.get("output") or "")
        return {
            "timeline": [],
            "evidence": [],
            "answer_card": {"summary": kwargs.get("output")},
            "completion_reason": "provider_error",
            "interrupted": False,
            "error_surface": None,
        }

    monkeypatch.setattr(
        conversation_result_projector_module,
        "build_turn_flow_view_model",
        _fake_build_turn_flow_view_model,
    )

    projection = build_turn_projection(
        raw_turn_record={},
        diagnostics_payload={"final_output_source": "recovery_evidence"},
        execution_path="fast",
        completion_reason="provider_error",
        partial=True,
        final_output_source="recovery_evidence",
    )
    build_execution_result(
        success=False,
        output="当前焦点：企业管理；页面要点：管理企业、企业列表；约 12 个可交互元素。",
        messages=[],
        tool_results=[],
        total_tokens=0,
        duration_ms=0,
        conversation_id=None,
        runtime_model_info=None,
        completion_reason="provider_error",
        turn_projection=projection,
    )

    assert (
        captured["output"]
        == "当前焦点：企业管理；页面要点：管理企业、企业列表；约 12 个可交互元素。"
    )


def test_build_turn_projection_forces_success_over_stale_runtime_failure() -> None:
    projection = build_turn_projection(
        raw_turn_record={
            "turn_outcome": "failed",
            "termination_reason": "elapsed_budget_exceeded",
            "failure_kind": "provider_gateway_error",
        },
        diagnostics_payload={
            "final_output_source": "recovery_evidence",
            "intent_plan": [
                {
                    "intent_id": "intent-1",
                    "status": "completed",
                    "completed_by_tool_names": ["fetch_url"],
                }
            ],
            "unfinished_intents": [],
            WEB_RESEARCH_TERMINAL_CONTRACT_KEY: WEB_RESEARCH_TERMINAL_NO_RESULT,
        },
        execution_path="normal",
        completion_reason="completed",
        partial=False,
        final_output_source="recovery_evidence",
        default_turn_outcome="success",
        force_completion_reason_in_turn_record=True,
    )

    assert projection.turn_record["turn_outcome"] == "success"
    assert projection.turn_record["termination_reason"] == "completed"
    assert projection.turn_record["final_output_source"] == "recovery_evidence"
    assert (
        projection.turn_record[WEB_RESEARCH_TERMINAL_CONTRACT_KEY]
        == WEB_RESEARCH_TERMINAL_NO_RESULT
    )


def test_build_untrusted_final_output_fallback_returns_safe_text() -> None:
    fallback = build_untrusted_final_output_fallback(
        auto_fetch_gate_reason="search_not_successful"
    )
    assert fallback.strip()
    assert "http" not in fallback.lower()

    no_results = build_untrusted_final_output_fallback(
        auto_fetch_gate_reason="search_no_results_completed"
    )
    assert no_results.strip()

    candidate_wrapper = build_untrusted_final_output_fallback(
        failure_kind="candidate_search_wrapper_url"
    )
    assert "无法直接核实" in candidate_wrapper
    assert "再试一次" not in candidate_wrapper

    generic_fallback = build_untrusted_final_output_fallback()
    assert generic_fallback.strip()


@pytest.mark.asyncio
async def test_conversation_engine_execute_projects_turn_result_with_shared_helper() -> (
    None
):
    engine = ConversationEngine(
        db=MagicMock(), gateway=MagicMock(), sandbox=MagicMock()
    )
    prep = PreparedExecution(
        messages=[ChatMessage(role="user", content="hello")],
        tools=[ToolDefinition(name="web_search", description="Search the web")],
        diagnostics={
            "conversation_outcome": "success",
        },
        execution_path="normal",
    )
    engine._prepare_execution = AsyncMock(return_value=prep)

    response = ChatResponse(
        message=ChatMessage(role="assistant", content="你好"),
        total_tokens=11,
        metadata={
            "runtime_model_info": {
                "model_id": 1,
                "model_name": "gpt-5.4",
                "provider_id": 2,
                "provider_name": "provider-a",
            },
            "runtime_turn_record": SimpleNamespace(
                turn_outcome="success",
                termination_reason="completed",
                metadata={"seed": "value"},
            ),
        },
    )

    async def _fake_run(**_: object) -> SimpleNamespace:
        return SimpleNamespace(
            response=response,
            tool_results=[],
            total_tokens=11,
            output="你好",
            paused_for_consent=False,
            partial=False,
            completion_reason="completed",
            final_output_source="assistant",
        )

    engine._call_llm = AsyncMock()
    engine._handle_tool_calls = AsyncMock()

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            conversation_entrypoints_module.TurnExecutor,
            "run",
            AsyncMock(side_effect=_fake_run),
        )
        result = await engine.execute(
            SimpleNamespace(id=1),
            ExecutionRequest(
                agent_id=1,
                tenant_id=1,
                user_id=1,
                conversation_id=8,
                messages=[ChatMessage(role="user", content="hello")],
            ),
        )

    assert result.success is True
    assert result.output == "你好"
    assert result.turn_record["execution_path"] == "normal"
    assert result.turn_record["final_output_source"] == "assistant"
    assert result.turn_record["metadata"]["seed"] == "value"
    assert result.turn_record["metadata"]["orchestration"] == result.diagnostics
    assert result.diagnostics["candidate_tool_names"] == ["web_search"]
