from __future__ import annotations

import json
import sys
import types
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from types import SimpleNamespace

from app.ai.types import ChatMessage, ChatResponse, messages_to_dicts

ENGINE_DIR = Path(__file__).resolve().parents[3] / "app" / "ai" / "engine"
if "app.ai.engine" not in sys.modules:
    engine_pkg = types.ModuleType("app.ai.engine")
    engine_pkg.__path__ = [str(ENGINE_DIR)]
    sys.modules["app.ai.engine"] = engine_pkg

stream_generation_support = import_module("app.ai.engine.stream_generation_support")
stream_generation_view = import_module("app.ai.engine.stream_generation_view")
stream_finalization_support = import_module("app.ai.engine.stream_finalization_support")
conversation_sync_result_support = import_module(
    "app.ai.engine.conversation_sync_result_support"
)
_build_replay_events = stream_generation_support._build_replay_events
_build_result_turn_record = stream_finalization_support.build_result_turn_record
build_done_event_payload = stream_finalization_support.build_done_event_payload
_finalize_completed_output = stream_generation_support._finalize_completed_output
_resolve_done_turn_outcome = stream_finalization_support.resolve_done_turn_outcome
build_initial_events = stream_generation_support.build_initial_events
build_sync_success_result = (
    conversation_sync_result_support.build_sync_success_result
)
reset_stream_state = stream_generation_support.reset_stream_state
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

    assert decoded[0]["event"] == "conversation"
    assert decoded[0]["conversation_id"] == 321
    assert decoded[1]["event"] == "knowledge_base_feedback"
    assert decoded[1]["dropped_knowledge_base_ids"] == [1, 2]
    assert decoded[2] == {"event": "optimizing_tools", "step": "tools_optimized"}
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

    assert decoded == [{"event": "conversation", "conversation_id": 654}]
    assert seen_page_keys == ["orders:detail"]


def test_build_replay_events_clears_streamed_content_before_tool_evidence_replay() -> None:
    handler = SimpleNamespace(_visible_stream_content="streamed preview")

    events = _build_replay_events(
        handler,
        output="final answer",
        final_output_source="tool_evidence_completed",
        partial_reply_stream_chunks=["final answer"],
        completed_reply_stream_chunks=[],
    )

    decoded = [_decode_sse(event) for event in events]

    assert decoded[0] == {"event": "clear_content"}
    assert decoded[1] == {"event": "message", "delta": "final answer"}


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


def test_finalize_completed_output_scopes_duplicate_check_to_current_turn() -> None:
    delegate = SimpleNamespace(
        _visible_stream_content="OK",
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

    artifacts = stream_generation_support.finalize_successful_turn(
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
    assert done_payload["selected_tool_names"] == ["web_search"]
    assert done_payload["selected_skill_names"] == ["skill.a"]
    assert done_payload["context_sources"] == ["kb:1"]
    assert done_payload["persisted_message_count"] == 1


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

    stream_artifacts = stream_generation_support.finalize_successful_turn(
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
