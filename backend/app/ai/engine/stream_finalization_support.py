"""Focused helpers for stream finalization payloads and turn records."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .conversation_result_projector import coerce_turn_record_payload
from .stream_generation_view import ensure_stream_generation_view
from .types import ExecutionResult


@dataclass(slots=True)
class StreamFinalizationArtifacts:
    result: ExecutionResult
    diagnostics_payload: dict[str, Any]
    response_metadata: dict[str, Any]
    resolved_protocol_path: str
    immediate_events: list[str] = field(default_factory=list)
    replay_events: list[str] = field(default_factory=list)


def _resolve_generation_view(handler: Any) -> Any:
    explicit = getattr(handler, "_stream_generation_view", None)
    if callable(explicit):
        return explicit()
    return ensure_stream_generation_view(handler)


def build_result_turn_record(
    handler: Any,
    *,
    diagnostics_payload: dict[str, Any],
    response_metadata: dict[str, Any],
) -> tuple[dict[str, Any], str]:
    view = _resolve_generation_view(handler)
    raw_turn_record = view.runtime_turn_record
    view.refresh_runtime_turn_record()
    refreshed_turn_record = coerce_turn_record_payload(view.runtime_turn_record)
    if raw_turn_record is not None:
        raw_payload = coerce_turn_record_payload(raw_turn_record)
        if raw_payload:
            raw_payload.update(refreshed_turn_record)
            result_turn_record = raw_payload
        else:
            result_turn_record = refreshed_turn_record
    else:
        result_turn_record = refreshed_turn_record
    resolved_protocol_path = view.resolved_protocol_path(
        diagnostics_payload=diagnostics_payload,
        turn_record=result_turn_record,
        response_metadata=response_metadata,
    )
    return result_turn_record, resolved_protocol_path


def resolve_done_turn_outcome(
    *,
    diagnostics_payload: dict[str, Any] | None,
    turn_record: dict[str, Any] | None,
) -> Any:
    if isinstance(diagnostics_payload, dict) and diagnostics_payload.get("turn_outcome"):
        return diagnostics_payload.get("turn_outcome")
    if isinstance(turn_record, dict):
        return turn_record.get("turn_outcome")
    return None


def build_done_event_payload(
    *,
    request: Any,
    artifacts: StreamFinalizationArtifacts,
    on_complete_extra: dict[str, Any] | None,
) -> dict[str, Any]:
    diagnostics_payload = artifacts.diagnostics_payload
    return {
        "event": "done",
        "conversation_id": getattr(request, "conversation_id", None),
        "total_tokens": artifacts.result.total_tokens,
        "duration_ms": artifacts.result.duration_ms,
        "context_compacted": artifacts.result.context_compacted,
        "memory_flush_triggered": artifacts.result.memory_flush_triggered,
        "memory_recalled": artifacts.result.memory_recalled,
        "prune_stats": artifacts.result.prune_stats,
        "rag_source_kinds": artifacts.result.rag_source_kinds,
        "turn_record": artifacts.result.turn_record or diagnostics_payload,
        "turn_outcome": resolve_done_turn_outcome(
            diagnostics_payload=diagnostics_payload,
            turn_record=artifacts.result.turn_record,
        ),
        "termination_reason": artifacts.result.completion_reason,
        "protocol_path": artifacts.resolved_protocol_path,
        "selected_tool_names": (
            diagnostics_payload.get("selected_tool_names")
            if isinstance(diagnostics_payload, dict)
            else None
        ),
        "selected_skill_names": (
            diagnostics_payload.get("selected_skill_names")
            if isinstance(diagnostics_payload, dict)
            else None
        ),
        "context_sources": (
            diagnostics_payload.get("context_sources")
            if isinstance(diagnostics_payload, dict)
            else None
        ),
        **(on_complete_extra or {}),
    }


__all__ = [
    "StreamFinalizationArtifacts",
    "build_done_event_payload",
    "build_result_turn_record",
    "resolve_done_turn_outcome",
]
