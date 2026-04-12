from __future__ import annotations

from dataclasses import dataclass, field
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.ai.engine.conversation import ConversationEngine
from app.ai.engine.conversation_result_projector import (
    build_execution_result,
    build_turn_projection,
    coerce_turn_record_payload,
)
from app.ai.engine.types import ExecutionRequest, PreparedExecution
from app.ai.tools.types import ToolDefinition
from app.ai.types import ChatMessage, ChatResponse


@dataclass
class _TurnRecordData:
    turn_outcome: str = "success"
    termination_reason: str = "completed"
    metadata: dict[str, object] = field(default_factory=dict)


def test_coerce_turn_record_payload_supports_dataclass() -> None:
    payload = coerce_turn_record_payload(
        _TurnRecordData(metadata={"seed": "value"})
    )

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
    assert projection.turn_record["metadata"]["turn_diagnostics"] == projection.diagnostics


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


def test_build_execution_result_accepts_explicit_diagnostics_without_projection() -> None:
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

    assert result.diagnostics == {"failure_kind": "provider_timeout"}
    assert result.turn_record is None


@pytest.mark.asyncio
async def test_conversation_engine_execute_projects_turn_result_with_shared_helper() -> None:
    engine = ConversationEngine(db=MagicMock(), gateway=MagicMock(), sandbox=MagicMock())
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
            "app.ai.engine.conversation_entrypoints.TurnExecutor.run",
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
