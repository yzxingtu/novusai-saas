from __future__ import annotations

import json
import sys
import types
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from types import SimpleNamespace

ENGINE_DIR = Path(__file__).resolve().parents[3] / "app" / "ai" / "engine"
if "app.ai.engine" not in sys.modules:
    engine_pkg = types.ModuleType("app.ai.engine")
    engine_pkg.__path__ = [str(ENGINE_DIR)]
    sys.modules["app.ai.engine"] = engine_pkg

stream_generation_support = import_module("app.ai.engine.stream_generation_support")
stream_generation_view = import_module("app.ai.engine.stream_generation_view")
_build_replay_events = stream_generation_support._build_replay_events
_build_result_turn_record = stream_generation_support._build_result_turn_record
_resolve_done_turn_outcome = stream_generation_support._resolve_done_turn_outcome
build_initial_events = stream_generation_support.build_initial_events
reset_stream_state = stream_generation_support.reset_stream_state
StreamGenerationView = stream_generation_view.StreamGenerationView
build_stream_generation_view = stream_generation_view.build_stream_generation_view


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
