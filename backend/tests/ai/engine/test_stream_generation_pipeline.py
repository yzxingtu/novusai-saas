"""
Test type: behavioral
Scope: Stream generation finalization and cancellation semantics.
Mock strategy: runtime seams are exercised directly; fakes replace only transport-boundary objects.
"""

from __future__ import annotations

import asyncio
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
        self.preparation_diagnostics = dict(diagnostics_payload)
        self.intent_plan: list = []
        self.budget = None
        self.recovery_history: list = []
        self.provider_failure_kind = "none"
        self.provider_events: list = []

    def build_diagnostics_payload(self) -> dict:
        payload = dict(self._diagnostics_payload)
        payload.update(self.preparation_diagnostics)
        return payload

    def register_provider_failure(
        self,
        *,
        kind: str,
        event: dict | None = None,
    ) -> None:
        self.provider_failure_kind = kind
        if event:
            self.provider_events.append(dict(event))


def _build_stream_cancel_handler(
    *,
    state: _StateStub,
    streamed_output: str,
    on_complete=None,
):
    completion_results: list = []
    progress_updates: list[dict] = []

    async def _await_on_complete_before_done(result):
        completion_results.append(result)
        handler._on_complete_called = True
        return None

    handler = SimpleNamespace(
        request=SimpleNamespace(conversation_id=88, input_variables={}),
        agent=SimpleNamespace(id=9),
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
        start_time=0.0,
        engine=SimpleNamespace(_messages_to_dicts=messages_to_dicts, sandbox=None),
        _state=state,
        _output=streamed_output,
        _reasoning_output="",
        _total_tokens=0,
        _completion_tokens_used=0,
        _runtime_model_info=None,
        _runtime_turn_record=None,
        _runtime_turn_record_source=None,
        _runtime_turn_record_overlays={},
        _visible_stream_content=streamed_output,
        _clear_before_next_message=False,
        _next_runtime_context=None,
        _on_complete_called=False,
        _interrupted_stage="stream_generating",
        on_complete=on_complete,
        _update_turn_progress=lambda **fields: progress_updates.append(fields),
        _chunk_text_for_streaming=lambda text: [text],
        _await_on_complete_before_done=_await_on_complete_before_done,
        _pop_post_done_callback=lambda _extra: None,
        _schedule_background_callback=lambda _callback: None,
    )
    return handler, completion_results, progress_updates


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


@pytest.mark.asyncio
async def test_build_stream_exception_artifacts_hides_generated_provider_failure_partial_output() -> None:
    state = _StateStub({})
    state.provider_failure_kind = "provider_http_5xx"
    state.provider_events = [{"kind": "provider_http_5xx"}]

    async def _finalize_partial_output(**_kwargs):
        return "我先把已完成部分整理给你：这部分。", 18, 9

    handler = SimpleNamespace(
        request=SimpleNamespace(conversation_id=66, input_variables={}),
        agent=SimpleNamespace(id=3),
        prep=SimpleNamespace(
            rag_source_kinds=[],
            context_compacted=False,
            memory_flush_triggered=False,
            memory_recalled=False,
            prune_stats=None,
            tool_planner=None,
            execution_path="fast",
            stream_runtime=None,
        ),
        start_time=0.0,
        engine=SimpleNamespace(_messages_to_dicts=messages_to_dicts),
        runtime_contract=SimpleNamespace(
            finalize_partial_output=_finalize_partial_output,
        ),
        _state=state,
        _runtime_turn_record=None,
        _runtime_turn_record_source=None,
        _runtime_turn_record_overlays={},
        _output="",
        _reasoning_output="",
        _total_tokens=0,
        _completion_tokens_used=0,
        _visible_stream_content="",
        _clear_before_next_message=False,
        _next_runtime_context=None,
    )
    messages = [ChatMessage(role="user", content="latest updates?")]

    artifacts = await stream_execution_runtime._build_stream_exception_artifacts(
        handler,
        messages=messages,
        rag_sources=None,
        output="",
        total_tokens=0,
        all_tool_results=[],
        public_error_message="upstream failed",
        completion_reason="provider_error",
    )

    assert artifacts.result.output.strip()
    assert artifacts.replay_events
    assert len(messages) == 2
    assert artifacts.result.turn_record["final_output_source"] == "partial_output"
    assert (
        artifacts.result.turn_record["turn_flow"]["error_surface"]["error_type"]
        == "untrusted_final_output_source"
    )


def test_build_sync_exception_result_hides_provider_failure_partial_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.ai.engine.execution_state_machine import ExecutionStateMachine
    from app.ai.engine.types import IntentPlan, PreparedExecution, RecoveryDecision
    from app.ai.exceptions import ProviderError

    monkeypatch.setattr(
        conversation_sync_result_support.RecoveryManager,
        "decide",
        staticmethod(
            lambda *_args, **_kwargs: RecoveryDecision(
                action="return_partial",
                reason="provider_failure_after_partial_progress",
                provider_failure_kind="provider_http_5xx",
            )
        ),
    )
    monkeypatch.setattr(
        conversation_sync_result_support.RecoveryManager,
        "build_partial_output",
        staticmethod(lambda *_args, **_kwargs: "我先把已完成部分整理给你：这部分。"),
    )

    prep = PreparedExecution(
        execution_path="fast",
        intent_plan=[
            IntentPlan(
                intent_id="intent-web",
                kind="web_research",
                family="web_research",
                order=1,
                user_visible_label="网页调研",
                source_text="查一下最新情况",
            )
        ],
    )
    state = ExecutionStateMachine.from_prepared_execution(prep)

    try:
        result = conversation_sync_result_support.build_sync_exception_result(
            exc=ProviderError("upstream failed", status_code=502),
            request=SimpleNamespace(conversation_id=77),
            messages=[ChatMessage(role="user", content="latest updates?")],
            tool_results=[],
            state=state,
            prep=prep,
            start_time=0.0,
            messages_to_dicts=messages_to_dicts,
        )
    finally:
        context_token = getattr(state, "_context_token", None)
        if context_token is not None:
            from app.ai.engine.execution_state_machine import (
                reset_current_execution_state_machine,
            )

            reset_current_execution_state_machine(context_token)

    assert result.partial is True
    assert result.output.strip()
    assert result.turn_record["final_output_source"] == "partial_output"
    assert result.diagnostics["final_output_source"] == "partial_output"
    assert (
        result.turn_record["turn_flow"]["error_surface"]["error_type"]
        == "untrusted_final_output_source"
    )


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

    output, chunks, final_output_source = _finalize_completed_output(
        handler,
        messages=messages,
        turn_start_message_index=1,
        output="OK",
        response=SimpleNamespace(message=ChatMessage(role="assistant", content="OK")),
        tool_results=None,
        action_buttons=None,
        final_output_source="assistant",
    )

    assert output == "OK"
    assert chunks
    assert final_output_source == "assistant"
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

    output, chunks, final_output_source = _finalize_completed_output(
        handler,
        messages=messages,
        turn_start_message_index=0,
        output="fetched evidence snippet",
        response=SimpleNamespace(
            message=ChatMessage(role="assistant", content="fetched evidence snippet")
        ),
        tool_results=None,
        action_buttons=None,
        final_output_source="tool_evidence_completed",
    )

    assert output == ""
    assert chunks == []
    assert final_output_source == "tool_evidence_completed"
    assert len(messages) == 1


def test_finalize_completed_output_surfaces_safe_untrusted_fallback_without_streamed_content() -> (
    None
):
    delegate = SimpleNamespace(
        _state=SimpleNamespace(
            preparation_diagnostics={
                "stripped_untrusted_final_output": True,
                "untrusted_final_output_fallback_applied": True,
            }
        ),
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
    fallback = "这次处理没有成功生成最终答复，请再试一次。"

    output, chunks, final_output_source = _finalize_completed_output(
        handler,
        messages=messages,
        turn_start_message_index=0,
        output=fallback,
        response=SimpleNamespace(
            message=ChatMessage(role="assistant", content=fallback)
        ),
        tool_results=None,
        action_buttons=None,
        final_output_source="tool_evidence_completed",
    )

    assert output == fallback
    assert chunks == [fallback]
    assert final_output_source == "tool_evidence_completed"
    assert len(messages) == 2


def test_finalize_completed_output_promotes_safe_completed_web_evidence_over_generic_fallback() -> (
    None
):
    from app.ai.engine.types import IntentPlan

    recovered_summary = "根据已抓取到的内容，湖南今年暑假从7月6日开始。"
    state = _StateStub(
        {
            "stripped_untrusted_final_output": True,
            "untrusted_final_output_fallback_applied": True,
        }
    )
    state.intent_plan = [
        IntentPlan(
            intent_id="intent-web",
            kind="web_research",
            family="web_research",
            order=1,
            user_visible_label="放假时间",
            source_text="湖南学生放假时间",
            status="completed",
            requires_tools=True,
            allowed_tool_names=["fetch_url"],
            completion_signals=["fetch_url"],
            cached_result=recovered_summary,
            metadata={"cached_result": recovered_summary},
        )
    ]
    delegate = SimpleNamespace(
        _state=state,
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
    messages = [ChatMessage(role="user", content="湖南学生放假时间")]
    fallback = "这次处理没有成功生成最终答复，请再试一次。"

    output, chunks, final_output_source = _finalize_completed_output(
        handler,
        messages=messages,
        turn_start_message_index=0,
        output=fallback,
        response=SimpleNamespace(
            message=ChatMessage(role="assistant", content=fallback)
        ),
        tool_results=[],
        action_buttons=None,
        final_output_source="tool_evidence_completed",
    )

    assert output == recovered_summary
    assert chunks == [recovered_summary]
    assert final_output_source == "recovery_evidence"
    assert messages[-1].content == recovered_summary


def test_finalize_completed_output_keeps_generic_fallback_for_search_not_successful_gate() -> (
    None
):
    from app.ai.engine.types import IntentPlan

    recovered_summary = "根据已抓取到的内容，湖南今年暑假从7月6日开始。"
    state = _StateStub(
        {
            "stripped_untrusted_final_output": True,
            "untrusted_final_output_fallback_applied": True,
        }
    )
    state.intent_plan = [
        IntentPlan(
            intent_id="intent-web",
            kind="web_research",
            family="web_research",
            order=1,
            user_visible_label="放假时间",
            source_text="湖南学生放假时间",
            status="completed",
            requires_tools=True,
            allowed_tool_names=["fetch_url"],
            completion_signals=["fetch_url"],
            cached_result=recovered_summary,
            metadata={
                "cached_result": recovered_summary,
                "auto_fetch_gate_reason": "search_not_successful",
            },
        )
    ]
    delegate = SimpleNamespace(
        _state=state,
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
    messages = [ChatMessage(role="user", content="湖南学生放假时间")]
    fallback = "这次处理没有成功生成最终答复，请再试一次。"

    output, chunks, final_output_source = _finalize_completed_output(
        handler,
        messages=messages,
        turn_start_message_index=0,
        output=fallback,
        response=SimpleNamespace(
            message=ChatMessage(role="assistant", content=fallback)
        ),
        tool_results=[],
        action_buttons=None,
        final_output_source="tool_evidence_completed",
    )

    assert output == fallback
    assert chunks == [fallback]
    assert final_output_source == "tool_evidence_completed"
    assert messages[-1].content == fallback


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
        logger=SimpleNamespace(warning=lambda *_args, **_kwargs: None),
    )

    assert artifacts.result.output == summary
    assert artifacts.result.turn_record["final_output_source"] == "tool_evidence_completed"
    assert messages[-1].role == "assistant"
    assert messages[-1].content == summary


def test_finalize_successful_turn_promotes_safe_completed_web_evidence_to_recovery_output() -> (
    None
):
    from app.ai.engine.turn_executor import TurnExecutionResult
    from app.ai.engine.types import IntentPlan

    recovered_summary = "根据已抓取到的内容，湖南今年暑假从7月6日开始。"
    diagnostics_payload = {
        "stripped_untrusted_final_output": True,
        "untrusted_final_output_fallback_applied": True,
    }
    state = _StateStub(diagnostics_payload)
    state.intent_plan = [
        IntentPlan(
            intent_id="intent-web",
            kind="web_research",
            family="web_research",
            order=1,
            user_visible_label="放假时间",
            source_text="湖南学生放假时间",
            status="completed",
            requires_tools=True,
            allowed_tool_names=["fetch_url"],
            completion_signals=["fetch_url"],
            cached_result=recovered_summary,
            metadata={"cached_result": recovered_summary},
        )
    ]
    delegate = SimpleNamespace(
        request=SimpleNamespace(conversation_id=304, agent_id=12, input_variables={}),
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
    messages = [ChatMessage(role="user", content="湖南学生放假时间")]
    fallback = "这次处理没有成功生成最终答复，请再试一次。"
    response = ChatResponse(
        message=ChatMessage(role="assistant", content=fallback),
        total_tokens=12,
        output_tokens=6,
        metadata={"protocol_path": "responses"},
    )
    turn_execution = TurnExecutionResult(
        output=fallback,
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
        logger=SimpleNamespace(warning=lambda *_args, **_kwargs: None),
    )

    assert artifacts.result.output == recovered_summary
    assert artifacts.diagnostics_payload["final_output_source"] == "recovery_evidence"
    assert artifacts.result.turn_record["final_output_source"] == "recovery_evidence"
    assert (
        artifacts.result.turn_record["turn_flow"]["answer_card"]["summary"]
        == recovered_summary
    )
    assert messages[-1].content == recovered_summary


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

    output, chunks, final_output_source = _finalize_completed_output(
        handler,
        messages=messages,
        turn_start_message_index=0,
        output="新的整理结果",
        response=SimpleNamespace(
            message=ChatMessage(role="assistant", content="新的整理结果")
        ),
        tool_results=None,
        action_buttons=None,
        final_output_source="tool_evidence_completed",
    )

    assert output == "新的整理结果"
    assert chunks == ["新的整理结果"]
    assert final_output_source == "tool_evidence_completed"
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

    output, chunks, final_output_source = _finalize_completed_output(
        handler,
        messages=messages,
        turn_start_message_index=0,
        output="这次处理没有成功生成最终答复，请再试一次。",
        response=SimpleNamespace(
            message=ChatMessage(role="assistant", content="这次处理没有成功生成最终答复，请再试一次。")
        ),
        tool_results=None,
        action_buttons=None,
        final_output_source="tool_evidence_completed",
    )

    assert output == "AI Daily - Latest AI headlines and analysis."
    assert chunks == []
    assert final_output_source == "tool_evidence_completed"
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
        logger=SimpleNamespace(warning=lambda *_args, **_kwargs: None),
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


def test_hydrate_artifacts_turn_flow_from_canonical_tool_calls_updates_done_payload() -> (
    None
):
    raw_turn_flow = {
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
    }
    turn_record = {
        "turn_outcome": "success",
        "termination_reason": "completed",
        "protocol_path": "responses",
        "final_output_source": "assistant",
        "metadata": {
            "canonical_tool_calls": [
                {
                    "id": "tc_weather_1",
                    "type": "function",
                    "name": "get_current_weather",
                    "display_name": "天气查询",
                    "function": {"arguments": '{"city":"北京"}'},
                    "success": True,
                    "summary": "北京晴，18°C",
                    "summary_payload": {"temperature_c": 18},
                    "output": "北京晴，18°C",
                }
            ]
        },
        "turn_flow": raw_turn_flow,
    }
    artifacts = stream_finalization_pipeline.StreamFinalizationArtifacts(
        result=SimpleNamespace(
            total_tokens=9,
            duration_ms=12,
            context_compacted=False,
            memory_flush_triggered=False,
            memory_recalled=False,
            prune_stats=None,
            rag_source_kinds=[],
            output="北京当前天气如下。",
            interrupted=False,
            completion_reason="completed",
            turn_record=turn_record,
            diagnostics={"turn_flow": raw_turn_flow},
        ),
        diagnostics_payload={
            "final_output_source": "assistant",
            "turn_flow": raw_turn_flow,
        },
        response_metadata={},
        resolved_protocol_path="responses",
    )

    stream_execution_runtime._hydrate_artifacts_turn_flow_from_canonical_tool_calls(
        artifacts
    )

    hydrated_flow = artifacts.result.turn_record["turn_flow"]
    assert hydrated_flow["evidence"] == [
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
        stage for stage in hydrated_flow["timeline"] if stage["type"] == "tool_execution"
    )
    assert tool_execution["tool_call_ids"] == ["tc_weather_1"]

    done_payload = build_done_event_payload(
        request=SimpleNamespace(conversation_id=55),
        artifacts=artifacts,
        on_complete_extra=None,
    )

    assert done_payload["turn_record"]["turn_flow"] == hydrated_flow
    assert done_payload["turn_record"]["metadata"]["canonical_tool_calls"] == [
        {
            "id": "tc_weather_1",
            "type": "function",
            "name": "get_current_weather",
            "display_name": "天气查询",
            "function": {"arguments": '{"city":"北京"}'},
            "success": True,
            "summary": "北京晴，18°C",
            "summary_payload": {"temperature_c": 18},
            "output": "北京晴，18°C",
        }
    ]


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
        logger=SimpleNamespace(warning=lambda *_args, **_kwargs: None),
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


@pytest.mark.asyncio
async def test_handle_stream_cancelled_exception_preserves_provider_failure_reason_and_marks_partial_reply() -> None:
    state = _StateStub({})
    state.provider_failure_kind = "provider_timeout"
    state.provider_events = [{"kind": "provider_timeout"}]
    handler, completion_results, progress_updates = _build_stream_cancel_handler(
        state=state,
        streamed_output="先给你部分结果。",
        on_complete=object(),
    )
    messages = [ChatMessage(role="user", content="继续处理")]

    events = [
        event
        async for event in stream_execution_runtime._handle_stream_cancelled_exception(
            handler,
            exc=asyncio.CancelledError(
                "Cancelled via cancel scope after upstream timeout"
            ),
            executor_task=None,
            messages=messages,
            rag_sources=None,
            output="",
            total_tokens=0,
            all_tool_results=[],
            turn_start_message_index=0,
            logger=SimpleNamespace(
                warning=lambda *_args, **_kwargs: None,
                debug=lambda *_args, **_kwargs: None,
            ),
        )
    ]

    assert progress_updates
    assert completion_results
    result = completion_results[0]
    assert result.completion_reason == "provider_timeout"
    assert result.provider_failure_kind == "provider_timeout"
    assert result.output.startswith("先给你部分结果。")
    assert "AI 供应商请求超时" in result.output
    assert messages[-1].content == result.output
    assert any(
        _decode_sse(event).get("event") == "done"
        for event in events
        if event.strip().startswith("data: {")
    )
    assert events[-1] == stream_execution_runtime.SSEChunkEncoder.done()


@pytest.mark.asyncio
async def test_handle_stream_cancelled_exception_still_emits_done_marker_when_done_event_yield_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = _StateStub({})
    handler, completion_results, _progress_updates = _build_stream_cancel_handler(
        state=state,
        streamed_output="",
        on_complete=object(),
    )

    def _raise_done_event(*_args, **_kwargs):
        raise ConnectionResetError("client disconnected")

    monkeypatch.setattr(
        stream_execution_runtime,
        "build_done_event",
        _raise_done_event,
    )

    events = [
        event
        async for event in stream_execution_runtime._handle_stream_cancelled_exception(
            handler,
            exc=asyncio.CancelledError("client disconnected"),
            executor_task=None,
            messages=[ChatMessage(role="user", content="hello")],
            rag_sources=None,
            output="",
            total_tokens=0,
            all_tool_results=[],
            turn_start_message_index=0,
            logger=SimpleNamespace(
                warning=lambda *_args, **_kwargs: None,
                debug=lambda *_args, **_kwargs: None,
            ),
        )
    ]

    assert completion_results
    assert events[-1] == stream_execution_runtime.SSEChunkEncoder.done()


@pytest.mark.asyncio
async def test_run_stream_execution_treats_named_cancelled_base_exception_as_interrupted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cancelled_type = type("CancelledError", (BaseException,), {})
    state = _StateStub({})
    handler, completion_results, progress_updates = _build_stream_cancel_handler(
        state=state,
        streamed_output="",
        on_complete=object(),
    )
    handler.prep.messages = [ChatMessage(role="user", content="继续处理")]
    handler.prep.rag_sources = None
    handler.prep.optimize_event = None

    async def _raise_named_cancelled() -> None:
        raise cancelled_type("cancelled via runtime transport")

    async def _drain_runtime_events(*_args, executor_task, **_kwargs):
        await executor_task
        if False:  # pragma: no cover - keep async-generator contract explicit
            yield ""

    handler._run_with_turn_executor = _raise_named_cancelled
    monkeypatch.setattr(
        stream_execution_runtime,
        "drain_runtime_events",
        _drain_runtime_events,
    )

    logger = SimpleNamespace(
        warning=lambda *_args, **_kwargs: None,
        error=lambda *_args, **_kwargs: None,
        debug=lambda *_args, **_kwargs: None,
    )
    events = [
        event
        async for event in stream_execution_runtime.run_stream_execution(
            handler,
            logger=logger,
        )
    ]

    assert progress_updates
    assert completion_results
    assert completion_results[0].interrupted is True
    assert completion_results[0].completion_reason == "interrupted"
    assert any(
        _decode_sse(event).get("event") == "done"
        for event in events
        if event.strip().startswith("data: {")
    )
    assert events[-1] == stream_execution_runtime.SSEChunkEncoder.done()

