# FROZEN: do not add new dependencies
"""Focused helpers for stream finalization payloads and turn records."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.middleware.trace import trace_id_var

from .conversation_result_projector import coerce_turn_record_payload
from .stream_generation_view import build_stream_generation_view
from .turn_flow_projector import resolve_final_stage_status
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
    return build_stream_generation_view(handler)


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
    if isinstance(diagnostics_payload, dict) and diagnostics_payload.get(
        "turn_outcome"
    ):
        return diagnostics_payload.get("turn_outcome")
    if isinstance(turn_record, dict):
        return turn_record.get("turn_outcome")
    return None


def _as_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def resolve_done_final_stage_status(
    *,
    turn_flow: dict[str, Any] | None,
    result: ExecutionResult,
) -> str:
    if bool(getattr(result, "interrupted", False)):
        return "interrupted"
    completion_reason = str(getattr(result, "completion_reason", "") or "").strip()
    if completion_reason == "interrupted":
        return "interrupted"
    if bool(getattr(result, "partial", False)):
        return "error"
    if bool(getattr(result, "partial", False)) or completion_reason not in {
        "",
        "completed",
        "stop",
    }:
        return "error"
    if _as_list(_as_dict(turn_flow).get("timeline")):
        return resolve_final_stage_status(turn_flow)
    return resolve_final_stage_status(turn_flow)


def build_done_event_payload(
    *,
    request: Any,
    artifacts: StreamFinalizationArtifacts,
    on_complete_extra: dict[str, Any] | None,
) -> dict[str, Any]:
    diagnostics_payload = artifacts.diagnostics_payload
    turn_record = artifacts.result.turn_record or diagnostics_payload
    turn_flow = None
    if isinstance(turn_record, dict):
        turn_flow = turn_record.get("turn_flow")
    if not isinstance(turn_flow, dict) and isinstance(diagnostics_payload, dict):
        turn_flow = diagnostics_payload.get("turn_flow")
    completion_reason = artifacts.result.completion_reason
    return {
        "event": "done",
        "conversation_id": getattr(request, "conversation_id", None),
        "trace_id": trace_id_var.get() or None,
        "completion_reason": completion_reason,
        "turn_flow_complete": True,
        "final_stage_status": resolve_done_final_stage_status(
            turn_flow=turn_flow if isinstance(turn_flow, dict) else None,
            result=artifacts.result,
        ),
        "total_tokens": artifacts.result.total_tokens,
        "duration_ms": artifacts.result.duration_ms,
        "context_compacted": artifacts.result.context_compacted,
        "memory_flush_triggered": artifacts.result.memory_flush_triggered,
        "memory_recalled": artifacts.result.memory_recalled,
        "prune_stats": artifacts.result.prune_stats,
        "rag_source_kinds": artifacts.result.rag_source_kinds,
        "turn_record": turn_record,
        "turn_outcome": resolve_done_turn_outcome(
            diagnostics_payload=diagnostics_payload,
            turn_record=artifacts.result.turn_record,
        ),
        "termination_reason": completion_reason,
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
    "resolve_done_final_stage_status",
    "resolve_done_turn_outcome",
]
