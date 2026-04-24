"""Shared execution-result projection helpers for conversation runtimes."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .final_output_policy import is_trusted_assistant_final_output_source
from .turn_flow_projector import build_turn_flow_view_model
from .types import ExecutionResult

_TURN_DIAGNOSTIC_KEYS = (
    "intent_plan",
    "budget",
    "budget_status",
    "budget_exit_reason",
    "elapsed_over_limit",
    "elapsed_over_limit_ms",
    "elapsed_limit_ms",
    "candidate_tool_names",
    "retry_events",
    "partial_exit_reason",
    "unfinished_intents",
    "provider_events",
    "failure_kind",
    "tool_planner",
    "active_intent_id",
    "continuation_source",
    "conversation_outcome",
    "assistant_claimed_tool_call_without_tool_event",
    "contract_breach_type",
    "final_output_source",
    "post_tool_completion_state",
    "auto_fetch_gate_reason",
    "turn_flow",
)


@dataclass(frozen=True)
class TurnProjection:
    """Projected turn-record and diagnostics payload for terminal result assembly."""

    diagnostics: dict[str, Any]
    turn_record: dict[str, Any]


def coerce_turn_record_payload(raw_turn_record: Any) -> dict[str, Any]:
    """Normalize runtime turn-record objects into plain dict payloads."""

    if isinstance(raw_turn_record, dict):
        return dict(raw_turn_record)
    if raw_turn_record is not None and hasattr(raw_turn_record, "__dataclass_fields__"):
        return asdict(raw_turn_record)
    if raw_turn_record is not None and hasattr(raw_turn_record, "__dict__"):
        return dict(getattr(raw_turn_record, "__dict__", {}) or {})
    return {}


def build_turn_projection(
    *,
    raw_turn_record: Any,
    diagnostics_payload: dict[str, Any],
    execution_path: str | None,
    completion_reason: str | None,
    partial: bool,
    final_output_source: str | None,
    protocol_path: str | None = None,
    default_turn_outcome: str | None = None,
    force_completion_reason_in_turn_record: bool = False,
) -> TurnProjection:
    """Project orchestration diagnostics into a stable turn-record payload."""

    projected_diagnostics = dict(diagnostics_payload or {})
    if partial:
        projected_diagnostics["partial_exit_reason"] = (
            completion_reason or projected_diagnostics.get("partial_exit_reason")
        )
    projected_diagnostics["final_output_source"] = final_output_source

    turn_record_payload = coerce_turn_record_payload(raw_turn_record)
    turn_record_payload["execution_path"] = execution_path
    if protocol_path:
        turn_record_payload["protocol_path"] = protocol_path
    for key in _TURN_DIAGNOSTIC_KEYS:
        turn_record_payload[key] = projected_diagnostics.get(key)

    raw_turn_outcome = str(turn_record_payload.get("turn_outcome") or "").strip()
    raw_termination_reason = str(
        turn_record_payload.get("termination_reason") or ""
    ).strip()
    partial_exit_reason = str(
        projected_diagnostics.get("partial_exit_reason") or ""
    ).strip()

    if partial and completion_reason:
        turn_record_payload["turn_outcome"] = "partial"
        turn_record_payload["termination_reason"] = completion_reason
        turn_record_payload["partial_exit_reason"] = (
            partial_exit_reason or completion_reason
        )
    else:
        if raw_turn_outcome:
            turn_record_payload["turn_outcome"] = raw_turn_outcome
        elif default_turn_outcome:
            turn_record_payload["turn_outcome"] = default_turn_outcome

        if force_completion_reason_in_turn_record and completion_reason:
            turn_record_payload["termination_reason"] = completion_reason
        elif raw_termination_reason:
            turn_record_payload["termination_reason"] = raw_termination_reason

        if partial_exit_reason:
            turn_record_payload["partial_exit_reason"] = partial_exit_reason

    metadata = dict(turn_record_payload.get("metadata") or {})
    metadata["orchestration"] = projected_diagnostics
    metadata["turn_diagnostics"] = projected_diagnostics
    turn_record_payload["metadata"] = metadata

    return TurnProjection(
        diagnostics=projected_diagnostics,
        turn_record=turn_record_payload,
    )


def build_execution_result(
    *,
    success: bool,
    output: str,
    messages: list[dict[str, Any]],
    tool_results: list[Any],
    total_tokens: int,
    duration_ms: int,
    conversation_id: int | None,
    runtime_model_info: dict[str, Any] | None,
    error: str = "",
    partial: bool = False,
    interrupted: bool = False,
    completion_reason: str | None = None,
    rag_sources: list[dict[str, Any]] | None = None,
    rag_source_kinds: list[str] | None = None,
    context_compacted: bool = False,
    memory_flush_triggered: bool = False,
    memory_recalled: bool = False,
    prune_stats: dict[str, Any] | None = None,
    tool_planner: dict[str, Any] | None = None,
    turn_projection: TurnProjection | None = None,
    intent_plan: list[Any] | None = None,
    execution_path: str | None = None,
    execution_budget: dict[str, Any] | None = None,
    recovery_history: list[dict[str, Any]] | None = None,
    provider_failure_kind: str = "none",
    provider_events: list[dict[str, Any]] | None = None,
    diagnostics: dict[str, Any] | None = None,
) -> ExecutionResult:
    """Assemble a stable ExecutionResult from pre-projected terminal artifacts."""

    runtime_info = (
        dict(runtime_model_info or {}) if isinstance(runtime_model_info, dict) else {}
    )
    diagnostics_payload = (
        turn_projection.diagnostics
        if turn_projection is not None
        else (dict(diagnostics) if diagnostics is not None else None)
    )
    diagnostics_payload = (
        dict(diagnostics_payload) if isinstance(diagnostics_payload, dict) else {}
    )
    turn_record_payload = (
        turn_projection.turn_record
        if turn_projection is not None and isinstance(turn_projection.turn_record, dict)
        else None
    )
    existing_turn_flow = diagnostics_payload.get("turn_flow")
    if not isinstance(existing_turn_flow, dict) and isinstance(turn_record_payload, dict):
        existing_turn_flow = turn_record_payload.get("turn_flow")

    if not isinstance(existing_turn_flow, dict):
        resolved_final_output_source = str(
            diagnostics_payload.get("final_output_source")
            or (turn_record_payload or {}).get("final_output_source")
            or ""
        ).strip() or None
        turn_flow_output = (
            str(output or "")
            if is_trusted_assistant_final_output_source(resolved_final_output_source)
            else ""
        )
        projected_turn_flow = build_turn_flow_view_model(
            diagnostics_payload=diagnostics_payload,
            turn_record=turn_record_payload,
            rag_sources=rag_sources,
            tool_results=tool_results,
            output=turn_flow_output,
            completion_reason=completion_reason,
            interrupted=interrupted,
            error=error,
        )
        diagnostics_payload["turn_flow"] = projected_turn_flow
        if isinstance(turn_record_payload, dict):
            turn_record_payload["turn_flow"] = projected_turn_flow
            turn_record_metadata = dict(turn_record_payload.get("metadata") or {})
            turn_record_metadata["turn_flow"] = projected_turn_flow
            orchestration_payload = dict(turn_record_metadata.get("orchestration") or {})
            orchestration_payload["turn_flow"] = projected_turn_flow
            turn_record_metadata["orchestration"] = orchestration_payload
            turn_record_metadata["turn_diagnostics"] = dict(orchestration_payload)
            turn_record_payload["metadata"] = turn_record_metadata

    result = ExecutionResult(
        success=success,
        output=output,
        messages=list(messages),
        tool_results=list(tool_results),
        total_tokens=total_tokens,
        duration_ms=duration_ms,
        conversation_id=conversation_id,
        runtime_model_id=runtime_info.get("model_id"),
        runtime_model_name=runtime_info.get("model_name"),
        runtime_provider_id=runtime_info.get("provider_id"),
        runtime_provider_name=runtime_info.get("provider_name"),
        error=error,
        partial=partial,
        completion_reason=completion_reason or "",
        rag_sources=rag_sources,
        rag_source_kinds=list(rag_source_kinds or []),
        context_compacted=context_compacted,
        memory_flush_triggered=memory_flush_triggered,
        memory_recalled=memory_recalled,
        prune_stats=prune_stats,
        tool_planner=tool_planner,
        turn_record=turn_record_payload,
        intent_plan=list(intent_plan or []),
        execution_path=execution_path,
        execution_budget=execution_budget,
        recovery_history=list(recovery_history or []),
        provider_failure_kind=provider_failure_kind,
        provider_events=list(provider_events or []),
        diagnostics=diagnostics_payload,
    )
    if interrupted:
        result.interrupted = True
    return result


__all__ = [
    "TurnProjection",
    "build_execution_result",
    "build_turn_projection",
    "coerce_turn_record_payload",
]
