from __future__ import annotations

import json
import sys
import types
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.ai.types import ChatMessage, ChatResponse, messages_to_dicts

ENGINE_DIR = Path(__file__).resolve().parents[3] / "app" / "ai" / "engine"
if "app.ai.engine" not in sys.modules:
    engine_pkg = types.ModuleType("app.ai.engine")
    engine_pkg.__path__ = [str(ENGINE_DIR)]
    sys.modules["app.ai.engine"] = engine_pkg

stream_generation_pipeline = import_module("app.ai.engine.stream_generation_pipeline")
stream_generation_view = import_module("app.ai.engine.stream_generation_view")
stream_finalization_pipeline = import_module("app.ai.engine.stream_finalization_pipeline")
stream_execution_runtime = import_module("app.ai.engine.stream_execution_runtime")
conversation_sync_result_support = import_module(
    "app.ai.engine.conversation_sync_result_support"
)
_build_replay_events = stream_generation_pipeline._build_replay_events
_finalize_partial_output = stream_generation_pipeline._finalize_partial_output
_build_result_turn_record = stream_finalization_pipeline.build_result_turn_record
build_done_event_payload = stream_finalization_pipeline.build_done_event_payload
_finalize_completed_output = stream_generation_pipeline._finalize_completed_output
_resolve_done_turn_outcome = stream_finalization_pipeline.resolve_done_turn_outcome
build_initial_events = stream_generation_pipeline.build_initial_events
build_terminal_result = stream_generation_pipeline.build_terminal_result
build_sync_success_result = (
    conversation_sync_result_support.build_sync_success_result
)
_resolve_stream_exception_completion_reason = (
    stream_execution_runtime._resolve_stream_exception_completion_reason
)
reset_stream_state = stream_generation_pipeline.reset_stream_state
StreamGenerationView = stream_generation_view.StreamGenerationView
build_stream_generation_view = stream_generation_view.build_stream_generation_view


class _StateStub:
    def __init__(self, diagnostics_payload: dict) -> None:
        self._diagnostics_payload = diagnostics_payload
        self.intent_plan: list = []
        self.budget = None
        self.recovery_history: list = []
        self.provider_failure_kind = "none"
        self.provider_events: list = []

    def build_diagnostics_payload(self) -> dict:
        return dict(self._diagnostics_payload)


def test_resolve_stream_exception_completion_reason_resolves_budget_exit_reason() -> None:
    state = SimpleNamespace(
        provider_failure_kind="budget_exit",
        budget_exit_reason=lambda: "elapsed_budget_exceeded",
    )
    handler = SimpleNamespace(_state=state)

    assert (
        _resolve_stream_exception_completion_reason(handler)
        == "elapsed_budget_exceeded"
    )


@pytest.mark.parametrize(
    ("failure_kind", "expected_reason"),
    [
        ("provider_timeout", "provider_timeout"),
        ("provider_unavailable", "provider_unavailable"),
        ("provider_http_5xx", "provider_error"),
        ("provider_bad_response", "provider_error"),
        ("provider_rate_limit", "provider_error"),
        ("tool_timeout", "tool_error"),
        ("tool_execution_error", "tool_error"),
        ("server_interrupt", "interrupted"),
    ],
)
def test_resolve_stream_exception_completion_reason_maps_failure_kinds(
    failure_kind: str,
    expected_reason: str,
) -> None:
    state = SimpleNamespace(
        provider_failure_kind=failure_kind,
        budget_exit_reason=lambda: "",
    )
    handler = SimpleNamespace(_state=state)

    assert _resolve_stream_exception_completion_reason(handler) == expected_reason


def test_resolve_stream_exception_completion_reason_defaults_to_stream_error() -> None:
    assert _resolve_stream_exception_completion_reason(SimpleNamespace(_state=None)) == (
        "stream_execution_error"
    )

    state = SimpleNamespace(
        provider_failure_kind="none",
        budget_exit_reason=lambda: "",
    )
    handler = SimpleNamespace(_state=state)
    assert _resolve_stream_exception_completion_reason(handler) == "stream_execution_error"


def _decode_sse(payload: str) -> dict:
    return json.loads(payload.strip()[6:])


def test_build_initial_events_emits_trace_kb_feedback_and_optimize_event() -> None:
    seen_page_keys: list[str | None] = []
    handler = SimpleNamespace(
        request=SimpleNamespace(
            conversation_id=321,
            input_variables={"page_context": {"page_key": "orders:list"}},
            knowledge_base_feedback={"dropped_knowledge_base_ids": [1, 2]},
        ),
        _update_turn_progress=lambda **fields: seen_page_keys.append(
            fields.get("last_page_key")
        ),
    )

    events = build_initial_events(
        handler,
        optimize_event={"step": "tools_optimized"},
    )

    decoded = [_decode_sse(event) for event in events]

    assert any(
        item.get("event") == "conversation" and item.get("conversation_id") == 321
        for item in decoded
    )
    assert any(
        item.get("event") == "knowledge_base_feedback"
        and item.get("dropped_knowledge_base_ids") == [1, 2]
        for item in decoded
    )
    assert any(
        item.get("event") == "optimizing_tools"
        and item.get("step") == "tools_optimized"
        for item in decoded
    )
    assert any(
        item.get("event") == "turn_stage"
        and (item.get("stage") or {}).get("type") == "thinking"
        and (item.get("stage") or {}).get("status") == "running"
        for item in decoded
    )
    assert seen_page_keys == ["orders:list"]


def test_build_initial_events_accepts_explicit_generation_view_seam() -> None:
    seen_page_keys: list[str | None] = []
    delegate = SimpleNamespace(
        request=SimpleNamespace(
            conversation_id=654,
            input_variables={"page_context": {"page_key": "orders:detail"}},
            knowledge_base_feedback=None,
        ),
        _update_turn_progress=lambda **fields: seen_page_keys.append(
            fields.get("last_page_key")
        ),
    )
    handler = SimpleNamespace(
        _stream_generation_view=lambda: build_stream_generation_view(delegate),
    )

    events = build_initial_events(
        handler,
        optimize_event=None,
    )

    decoded = [_decode_sse(event) for event in events]

    assert any(
        item.get("event") == "conversation" and item.get("conversation_id") == 654
        for item in decoded
    )
    assert any(
        item.get("event") == "turn_stage"
        and (item.get("stage") or {}).get("type") == "thinking"
        for item in decoded
    )
    assert seen_page_keys == ["orders:detail"]


def test_build_replay_events_does_not_clear_for_untrusted_tool_evidence_replay() -> None:
    handler = SimpleNamespace(_visible_stream_content="streamed preview")

    events = _build_replay_events(
        handler,
        output="final answer",
        final_output_source="tool_evidence_completed",
        partial_reply_stream_chunks=["final answer"],
        completed_reply_stream_chunks=[],
    )

    decoded = [_decode_sse(event) for event in events]

    assert decoded == [{"event": "message", "delta": "final answer"}]


def test_build_replay_events_clears_for_untrusted_completed_replay() -> None:
    handler = SimpleNamespace(_visible_stream_content="streamed preview")

    events = _build_replay_events(
        handler,
        output="final answer",
        final_output_source="tool_evidence_completed",
        partial_reply_stream_chunks=[],
        completed_reply_stream_chunks=["final answer"],
    )

    decoded = [_decode_sse(event) for event in events]

    assert decoded == [
        {"event": "clear_content"},
        {"event": "message", "delta": "final answer"},
    ]


def test_reset_stream_state_uses_explicit_generation_view_seam() -> None:
    delegate = SimpleNamespace(
        prep=SimpleNamespace(stream_runtime={"turn": 2}),
        _output="hello",
        _reasoning_output="thoughts",
        _total_tokens=9,
        _completion_tokens_used=4,
        _runtime_model_info={"model_id": "gpt-5.4"},
        _runtime_turn_record={"turn": 1},
        _runtime_turn_record_source="provider",
        _runtime_turn_record_overlays={"source": "provider"},
        _on_complete_called=True,
        _visible_stream_content="visible",
        _clear_before_next_message=True,
        _next_runtime_context="stale",
    )
    handler = SimpleNamespace(
        _stream_generation_view=lambda: build_stream_generation_view(delegate),
    )

    reset_stream_state(handler)

    assert delegate._output == ""
    assert delegate._reasoning_output == ""
    assert delegate._total_tokens == 0
    assert delegate._completion_tokens_used == 0
    assert delegate._runtime_model_info is None
    assert delegate._runtime_turn_record is None
    assert delegate._runtime_turn_record_source is None
    assert delegate._runtime_turn_record_overlays == {}
    assert delegate._on_complete_called is False
    assert delegate._visible_stream_content == ""
    assert delegate._clear_before_next_message is False
    assert delegate._next_runtime_context == {"turn": 2}


def test_resolve_done_turn_outcome_prefers_diagnostics_payload() -> None:
    assert _resolve_done_turn_outcome(
        diagnostics_payload={"turn_outcome": "partial"},
        turn_record={"turn_outcome": "success"},
    ) == "partial"
    assert _resolve_done_turn_outcome(
        diagnostics_payload={},
        turn_record={"turn_outcome": "success"},
    ) == "success"


def test_build_result_turn_record_preserves_non_dict_payload() -> None:
    @dataclass(slots=True)
    class _TurnRecord:
        turn_outcome: str
        termination_reason: str
        protocol_path: str

    raw_turn_record = _TurnRecord(
        turn_outcome="success",
        termination_reason="completed",
        protocol_path="responses",
    )
    handler = SimpleNamespace(
        _runtime_turn_record=raw_turn_record,
        _runtime_turn_record_source=None,
        _runtime_turn_record_overlays={},
    )

    result_turn_record, resolved_protocol_path = _build_result_turn_record(
        handler,
        diagnostics_payload={},
        response_metadata={},
    )

    assert result_turn_record["turn_outcome"] == "success"
    assert result_turn_record["termination_reason"] == "completed"
    assert result_turn_record["protocol_path"] == "responses"
    assert resolved_protocol_path == "responses"


def test_build_terminal_result_hides_provider_state_when_disabled() -> None:
    handler = SimpleNamespace(
        request=SimpleNamespace(conversation_id=77),
        prep=SimpleNamespace(stream_runtime=None),
        start_time=0.0,
        engine=SimpleNamespace(_messages_to_dicts=messages_to_dicts),
        _state=_StateStub({"final_output_source": "stream_error"}),
        _runtime_turn_record=None,
        _runtime_turn_record_source=None,
        _runtime_turn_record_overlays={},
    )
    handler._state.provider_failure_kind = "provider_unavailable"
    handler._state.provider_events = [{"kind": "provider_unavailable"}]

    result = build_terminal_result(
        handler,
        messages=[],
        output="partial reply",
        error="upstream failed",
        interrupted=False,
        completion_reason="error",
        total_tokens=12,
        duration_ms=34,
        tool_results=[],
        rag_sources=None,
        include_provider_state=False,
    )

    assert result.provider_failure_kind == "none"
    assert result.provider_events == []


def test_done_payload_marks_partial_provider_failure_as_error_terminal() -> None:
    state = _StateStub(
        {
            "failure_kind": "provider_timeout",
            "turn_outcome": "partial",
            "final_output_source": "partial_output",
        }
    )
    state.provider_failure_kind = "provider_timeout"
    state.provider_events = [{"kind": "provider_timeout"}]
    handler = SimpleNamespace(
        request=SimpleNamespace(conversation_id=88),
        prep=SimpleNamespace(stream_runtime=None),
        start_time=0.0,
        engine=SimpleNamespace(_messages_to_dicts=messages_to_dicts),
        _state=state,
        _runtime_turn_record=None,
        _runtime_turn_record_source=None,
        _runtime_turn_record_overlays={},
    )

    result = build_terminal_result(
        handler,
        messages=[],
        output="",
        error="",
        interrupted=False,
        completion_reason="provider_failure_after_partial_progress",
        total_tokens=21,
        duration_ms=34,
        tool_results=[],
        rag_sources=[{"id": "src_9", "kind": "web", "title": "Evidence"}],
        include_provider_state=True,
    )
    artifacts = stream_finalization_pipeline.StreamFinalizationArtifacts(
        result=result,
        diagnostics_payload=result.diagnostics or {},
        response_metadata={},
        resolved_protocol_path="responses",
    )
    done_payload = build_done_event_payload(
        request=handler.request,
        artifacts=artifacts,
        on_complete_extra=None,
    )

    assert done_payload["completion_reason"] == "provider_failure_after_partial_progress"
    assert done_payload["turn_flow_complete"] is True
    assert done_payload["final_stage_status"] == "error"


def test_finalize_completed_output_scopes_duplicate_check_to_current_turn() -> None:
    delegate = SimpleNamespace(
        _visible_stream_content="",
        extract_action_buttons=lambda output: (output, None),
        should_preserve_streamed_assistant_output=lambda **_kwargs: False,
        reasoning_output="",
        current_turn_has_finalized_output=lambda **kwargs: (
            kwargs["finalized_output"]
            == "OK"
            and any(str(message.content or "").strip() == "OK" for message in kwargs["messages"])
        ),
        chunk_text_for_streaming=lambda text, _chunk_size=32: [text],
    )
    handler = SimpleNamespace(
        _stream_generation_view=lambda: build_stream_generation_view(delegate),
    )
    messages = [
        ChatMessage(role="assistant", content="OK"),
        ChatMessage(role="user", content="thanks"),
    ]

    output, chunks = _finalize_completed_output(
        handler,
        messages=messages,
        turn_start_message_index=1,
        output="OK",
        response=SimpleNamespace(message=ChatMessage(role="assistant", content="OK")),
        action_buttons=None,
        final_output_source="assistant",
    )

    assert output == "OK"
    assert chunks
    assistant_messages = [message for message in messages if message.role == "assistant"]
    assert len(assistant_messages) == 2
    assert assistant_messages[-1].content == "OK"


def test_finalize_completed_output_drops_untrusted_tool_evidence_finalization() -> None:
    delegate = SimpleNamespace(
        _visible_stream_content="",
        extract_action_buttons=lambda output: (output, None),
        should_preserve_streamed_assistant_output=lambda **_kwargs: False,
        reasoning_output="",
        current_turn_has_finalized_output=lambda **_kwargs: False,
        chunk_text_for_streaming=lambda text, _chunk_size=32: [text],
        last_visible_assistant_content=lambda _messages: "",
    )
    handler = SimpleNamespace(
        _stream_generation_view=lambda: build_stream_generation_view(delegate),
    )
    messages = [ChatMessage(role="user", content="latest updates?")]

    output, chunks = _finalize_completed_output(
        handler,
        messages=messages,
        turn_start_message_index=0,
        output="fetched evidence snippet",
        response=SimpleNamespace(
            message=ChatMessage(role="assistant", content="fetched evidence snippet")
        ),
        action_buttons=None,
        final_output_source="tool_evidence_completed",
    )

    assert output == ""
    assert chunks == []
    assert len(messages) == 1


def test_finalize_successful_turn_uses_streamed_tool_evidence_when_output_is_empty() -> (
    None
):
    from app.ai.engine.turn_executor import TurnExecutionResult

    summary = "AI Daily - Latest AI headlines and analysis."
    state = _StateStub({})
    delegate = SimpleNamespace(
        request=SimpleNamespace(conversation_id=303, agent_id=12, input_variables={}),
        start_time=0.0,
        prep=SimpleNamespace(
            rag_source_kinds=[],
            context_compacted=False,
            memory_flush_triggered=False,
            memory_recalled=False,
            prune_stats=None,
            tool_planner=None,
            execution_path="normal",
            stream_runtime=None,
        ),
        _state=state,
        _output=summary,
        _reasoning_output="",
        _total_tokens=0,
        _completion_tokens_used=0,
        _runtime_model_info=None,
        _runtime_turn_record=None,
        _runtime_turn_record_source=None,
        _runtime_turn_record_overlays={},
        _visible_stream_content=summary,
        _clear_before_next_message=False,
        _next_runtime_context=None,
    )
    handler = SimpleNamespace(
        _stream_generation_view=lambda: build_stream_generation_view(delegate),
    )
    messages = [ChatMessage(role="user", content="latest updates?")]
    response = ChatResponse(
        message=ChatMessage(role="assistant", content=""),
        total_tokens=12,
        output_tokens=6,
        metadata={"protocol_path": "responses"},
    )
    turn_execution = TurnExecutionResult(
        output="",
        total_tokens=12,
        completion_tokens_used=6,
        tool_results=[],
        response=response,
        partial=False,
        paused_for_consent=False,
        completion_reason="completed",
        final_output_source="tool_evidence_completed",
        action_buttons=None,
    )

    artifacts = stream_generation_pipeline.finalize_successful_turn(
        handler,
        messages=messages,
        rag_sources=None,
        turn_start_message_index=0,
        turn_execution=turn_execution,
        logger=SimpleNamespace(warning=lambda *args, **kwargs: None),
    )

    assert artifacts.result.output == summary
    assert artifacts.result.turn_record["final_output_source"] == "tool_evidence_completed"
    assert messages[-1].role == "assistant"
    assert messages[-1].content == summary


def test_finalize_completed_output_replays_replacement_for_untrusted_preview() -> None:
    delegate = SimpleNamespace(
        _visible_stream_content="旧预览内容",
        extract_action_buttons=lambda output: (output, None),
        should_preserve_streamed_assistant_output=lambda **_kwargs: False,
        reasoning_output="",
        current_turn_has_finalized_output=lambda **_kwargs: False,
        should_replay_finalized_output=lambda **kwargs: (
            kwargs["streamed_output"] != kwargs["finalized_output"]
            and bool(kwargs["finalized_output"])
        ),
        chunk_text_for_streaming=lambda text, _chunk_size=32: [text],
        last_visible_assistant_content=lambda _messages: "",
    )
    handler = SimpleNamespace(
        _stream_generation_view=lambda: build_stream_generation_view(delegate),
    )
    messages = [ChatMessage(role="user", content="latest updates?")]

    output, chunks = _finalize_completed_output(
        handler,
        messages=messages,
        turn_start_message_index=0,
        output="新的整理结果",
        response=SimpleNamespace(
            message=ChatMessage(role="assistant", content="新的整理结果")
        ),
        action_buttons=None,
        final_output_source="tool_evidence_completed",
    )

    assert output == "新的整理结果"
    assert chunks == ["新的整理结果"]
    assert messages[-1].role == "assistant"
    assert messages[-1].content == "新的整理结果"


def test_finalize_completed_output_preserves_streamed_summary_over_generic_fallback() -> (
    None
):
    delegate = SimpleNamespace(
        _visible_stream_content="AI Daily - Latest AI headlines and analysis.",
        extract_action_buttons=lambda output: (output, None),
        should_preserve_streamed_assistant_output=lambda **_kwargs: False,
        reasoning_output="",
        current_turn_has_finalized_output=lambda **_kwargs: False,
        should_replay_finalized_output=lambda **_kwargs: True,
        chunk_text_for_streaming=lambda text, _chunk_size=32: [text],
        last_visible_assistant_content=lambda _messages: "",
    )
    handler = SimpleNamespace(
        _stream_generation_view=lambda: build_stream_generation_view(delegate),
    )
    messages = [ChatMessage(role="user", content="latest updates?")]

    output, chunks = _finalize_completed_output(
        handler,
        messages=messages,
        turn_start_message_index=0,
        output="这次处理没有成功生成最终答复，请再试一次。",
        response=SimpleNamespace(
            message=ChatMessage(role="assistant", content="这次处理没有成功生成最终答复，请再试一次。")
        ),
        action_buttons=None,
        final_output_source="tool_evidence_completed",
    )

    assert output == "AI Daily - Latest AI headlines and analysis."
    assert chunks == []
    assert messages[-1].role == "assistant"
    assert messages[-1].content == "AI Daily - Latest AI headlines and analysis."


def test_finalize_partial_output_rejects_untrusted_failure_snippet() -> None:
    state = _StateStub({})
    state.provider_failure_kind = "provider_unavailable"
    delegate = SimpleNamespace(
        _state=state,
        _visible_stream_content="",
        _output="fetched snippet that should not be final answer",
        current_turn_has_finalized_output=lambda **_kwargs: False,
        should_replay_finalized_output=lambda **kwargs: (
            kwargs["streamed_output"] != kwargs["finalized_output"]
            and bool(kwargs["finalized_output"])
        ),
        chunk_text_for_streaming=lambda text, _chunk_size=32: [text],
        last_visible_assistant_content=lambda _messages: "",
    )
    handler = SimpleNamespace(
        _stream_generation_view=lambda: build_stream_generation_view(delegate),
    )
    messages = [ChatMessage(role="user", content="latest updates?")]

    output, replay_chunks = _finalize_partial_output(
        handler,
        messages=messages,
        turn_start_message_index=0,
        output="fetched snippet that should not be final answer",
        tool_results=[],
        action_buttons=None,
        completion_reason="provider_failure_after_partial_progress",
    )

    assert output
    assert output != "fetched snippet that should not be final answer"
    assert messages[-1].role == "assistant"
    assert messages[-1].content == output
    assert replay_chunks == [output]


def test_finalize_partial_output_keeps_trustworthy_streamed_assistant_text() -> None:
    state = _StateStub({})
    state.provider_failure_kind = "provider_unavailable"
    delegate = SimpleNamespace(
        _state=state,
        _visible_stream_content="partial assistant answer",
        _output="irrelevant local buffer",
        current_turn_has_finalized_output=lambda **_kwargs: False,
        should_replay_finalized_output=lambda **kwargs: (
            kwargs["streamed_output"] != kwargs["finalized_output"]
            and bool(kwargs["finalized_output"])
        ),
        chunk_text_for_streaming=lambda text, _chunk_size=32: [text],
        last_visible_assistant_content=lambda _messages: "partial assistant answer",
    )
    handler = SimpleNamespace(
        _stream_generation_view=lambda: build_stream_generation_view(delegate),
    )
    messages = [ChatMessage(role="user", content="latest updates?")]

    output, replay_chunks = _finalize_partial_output(
        handler,
        messages=messages,
        turn_start_message_index=0,
        output="fallback synthesis text",
        tool_results=[],
        action_buttons=None,
        completion_reason="provider_failure_after_partial_progress",
    )

    assert output == "partial assistant answer"
    assert replay_chunks == []
    assert messages[-1].role == "assistant"
    assert messages[-1].content == "partial assistant answer"


def test_finalize_successful_turn_projects_turn_record_and_done_payload() -> None:
    from app.ai.engine.turn_executor import TurnExecutionResult

    diagnostics_payload = {
        "selected_tool_names": ["web_search"],
        "selected_skill_names": ["skill.a"],
        "context_sources": ["kb:1"],
    }
    state = _StateStub(diagnostics_payload)
    delegate = SimpleNamespace(
        request=SimpleNamespace(
            conversation_id=101,
            agent_id=9,
            input_variables={},
        ),
        start_time=0.0,
        prep=SimpleNamespace(
            rag_source_kinds=["kb"],
            context_compacted=False,
            memory_flush_triggered=False,
            memory_recalled=False,
            prune_stats=None,
            tool_planner=None,
            execution_path="normal",
            stream_runtime=None,
        ),
        _state=state,
        _output="",
        _reasoning_output="",
        _total_tokens=0,
        _completion_tokens_used=0,
        _runtime_model_info=None,
        _runtime_turn_record=None,
        _runtime_turn_record_source=None,
        _runtime_turn_record_overlays={},
        _visible_stream_content="",
        _clear_before_next_message=False,
        _next_runtime_context=None,
    )
    handler = SimpleNamespace(
        _stream_generation_view=lambda: build_stream_generation_view(delegate),
    )
    runtime_turn_record = {
        "turn_outcome": "success",
        "termination_reason": "completed",
        "protocol_path": "responses",
    }
    response = ChatResponse(
        message=ChatMessage(role="assistant", content="OK"),
        total_tokens=12,
        output_tokens=6,
        metadata={
            "runtime_turn_record": runtime_turn_record,
            "runtime_model_info": {
                "provider_id": 11,
                "provider_name": "Provider",
                "model_id": 22,
                "model_name": "Model",
            },
            "protocol_path": "responses",
        },
    )
    turn_execution = TurnExecutionResult(
        output="OK",
        total_tokens=12,
        completion_tokens_used=6,
        tool_results=[],
        response=response,
        partial=False,
        paused_for_consent=False,
        completion_reason="completed",
        final_output_source="assistant",
        action_buttons=None,
    )
    messages = [ChatMessage(role="user", content="hi")]

    artifacts = stream_generation_pipeline.finalize_successful_turn(
        handler,
        messages=messages,
        rag_sources=None,
        turn_start_message_index=0,
        turn_execution=turn_execution,
        logger=SimpleNamespace(warning=lambda *args, **kwargs: None),
    )

    turn_record = artifacts.result.turn_record
    assert turn_record["execution_path"] == "normal"
    assert turn_record["protocol_path"] == "responses"
    assert turn_record["final_output_source"] == "assistant"
    assert turn_record["turn_outcome"] == "success"
    assert turn_record["termination_reason"] == "completed"
    assert artifacts.diagnostics_payload["final_output_source"] == "assistant"

    done_payload = build_done_event_payload(
        request=delegate.request,
        artifacts=artifacts,
        on_complete_extra={"persisted_message_count": 1},
    )

    assert done_payload["turn_record"] == turn_record
    assert done_payload["turn_outcome"] == "success"
    assert done_payload["protocol_path"] == "responses"
    assert done_payload["termination_reason"] == "completed"
    assert done_payload["completion_reason"] == "completed"
    assert done_payload["turn_flow_complete"] is True
    assert done_payload["final_stage_status"] == "completed"
    assert "trace_id" in done_payload
    assert done_payload["selected_tool_names"] == ["web_search"]
    assert done_payload["selected_skill_names"] == ["skill.a"]
    assert done_payload["context_sources"] == ["kb:1"]
    assert done_payload["persisted_message_count"] == 1


@pytest.mark.parametrize(
    ("timeline", "expected_status"),
    [
        ([{"id": "completed", "type": "completed", "status": "completed"}], "completed"),
        ([{"id": "failed", "type": "failed", "status": "error"}], "error"),
        ([{"id": "failed", "type": "failed", "status": "interrupted"}], "interrupted"),
    ],
)
def test_build_done_event_payload_uses_turn_flow_final_stage_status(
    timeline: list[dict[str, object]],
    expected_status: str,
) -> None:
    artifacts = stream_finalization_pipeline.StreamFinalizationArtifacts(
        result=SimpleNamespace(
            total_tokens=9,
            duration_ms=12,
            context_compacted=False,
            memory_flush_triggered=False,
            memory_recalled=False,
            prune_stats=None,
            rag_source_kinds=[],
            turn_record={"turn_flow": {"timeline": timeline}},
            completion_reason="completed",
        ),
        diagnostics_payload={},
        response_metadata={},
        resolved_protocol_path="responses",
    )
    payload = build_done_event_payload(
        request=SimpleNamespace(conversation_id=55),
        artifacts=artifacts,
        on_complete_extra=None,
    )

    assert payload["turn_flow_complete"] is True
    assert payload["completion_reason"] == "completed"
    assert payload["final_stage_status"] == expected_status


def test_sync_success_result_matches_stream_turn_projection() -> None:
    from app.ai.engine.turn_executor import TurnExecutionResult

    diagnostics_payload = {}
    runtime_turn_record = {
        "turn_outcome": "success",
        "termination_reason": "completed",
        "protocol_path": "responses",
    }

    state = _StateStub(diagnostics_payload)
    delegate = SimpleNamespace(
        request=SimpleNamespace(conversation_id=202, agent_id=11, input_variables={}),
        start_time=0.0,
        prep=SimpleNamespace(
            rag_source_kinds=[],
            context_compacted=False,
            memory_flush_triggered=False,
            memory_recalled=False,
            prune_stats=None,
            tool_planner=None,
            execution_path="normal",
            stream_runtime=None,
        ),
        _state=state,
        _output="",
        _reasoning_output="",
        _total_tokens=0,
        _completion_tokens_used=0,
        _runtime_model_info=None,
        _runtime_turn_record=None,
        _runtime_turn_record_source=None,
        _runtime_turn_record_overlays={},
        _visible_stream_content="",
        _clear_before_next_message=False,
        _next_runtime_context=None,
    )
    handler = SimpleNamespace(
        _stream_generation_view=lambda: build_stream_generation_view(delegate),
    )
    stream_response = ChatResponse(
        message=ChatMessage(role="assistant", content="hello"),
        total_tokens=12,
        output_tokens=6,
        metadata={
            "runtime_turn_record": runtime_turn_record,
            "runtime_model_info": {"model_id": 1, "model_name": "Model"},
            "protocol_path": "responses",
        },
    )
    turn_execution = TurnExecutionResult(
        output="hello",
        total_tokens=12,
        completion_tokens_used=6,
        tool_results=[],
        response=stream_response,
        partial=False,
        paused_for_consent=False,
        completion_reason="completed",
        final_output_source="assistant",
        action_buttons=None,
    )
    stream_messages = [ChatMessage(role="user", content="hello")]

    stream_artifacts = stream_generation_pipeline.finalize_successful_turn(
        handler,
        messages=stream_messages,
        rag_sources=None,
        turn_start_message_index=0,
        turn_execution=turn_execution,
        logger=SimpleNamespace(warning=lambda *args, **kwargs: None),
    )

    sync_state = _StateStub(diagnostics_payload)
    sync_prep = SimpleNamespace(
        rag_sources=None,
        rag_source_kinds=[],
        context_compacted=False,
        memory_flush_triggered=False,
        memory_recalled=False,
        prune_stats=None,
        tool_planner=None,
        execution_path="normal",
    )
    sync_request = SimpleNamespace(conversation_id=202)
    sync_response = ChatResponse(
        message=ChatMessage(role="assistant", content="hello"),
        total_tokens=12,
        output_tokens=6,
        metadata={
            "runtime_turn_record": runtime_turn_record,
            "runtime_model_info": {"model_id": 1, "model_name": "Model"},
            "protocol_path": "responses",
        },
    )
    sync_messages = [ChatMessage(role="user", content="hello")]

    sync_result = build_sync_success_result(
        output="hello",
        response=sync_response,
        messages=sync_messages,
        tool_results=[],
        total_tokens=12,
        start_time=0.0,
        request=sync_request,
        prep=sync_prep,
        state=sync_state,
        paused_for_consent=False,
        partial=False,
        completion_reason="completed",
        final_output_source="assistant",
        messages_to_dicts=messages_to_dicts,
    )

    stream_turn_record = stream_artifacts.result.turn_record
    sync_turn_record = sync_result.turn_record

    for key in (
        "execution_path",
        "protocol_path",
        "final_output_source",
        "turn_outcome",
        "termination_reason",
    ):
        assert stream_turn_record[key] == sync_turn_record[key]
