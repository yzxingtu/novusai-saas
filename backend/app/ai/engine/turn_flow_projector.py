"""Turn-flow projection and canonical-stream event helpers."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.ai.runtime.contracts import (
    TurnAnswerCard,
    TurnEvidenceItem,
    TurnFlowStage,
    TurnFlowViewModel,
)
from app.middleware.trace import trace_id_var

from .final_output_policy import is_trusted_assistant_final_output_source

_CANONICAL_STAGE_ORDER = (
    "thinking",
    "tool_selection",
    "tool_execution",
    "retrieval",
    "answer_assembly",
)

_TERMINAL_FAILURE_COMPLETION_REASONS = frozenset(
    {
        "budget_exit",
        "elapsed_budget_exceeded",
        "prompt_budget_exceeded",
        "completion_budget_exceeded",
        "tool_round_budget_exceeded",
        "tool_result_budget_exceeded",
        "candidate_tool_budget_exceeded",
        "error",
        "provider_failure_after_partial_progress",
        "provider_timeout",
        "provider_unavailable",
        "provider_error",
        "tool_error",
        "tool_round_failed",
        "stream_execution_error",
        "terminal_failure",
    }
)
_TERMINAL_FAILURE_KINDS = frozenset(
    {
        "provider_timeout",
        "provider_unavailable",
        "provider_error",
        "provider_http_5xx",
        "provider_bad_response",
        "tool_error",
        "tool_round_failed",
        "tool_execution_error",
        "tool_timeout",
        "stream_execution_error",
    }
)
_SAFE_TURN_FAILURE_MESSAGE = "The assistant could not finish this turn. Please retry."


def _strip_trace_suffix(text: str) -> str:
    trace_marker = " [trace_id="
    if trace_marker in text:
        return text.split(trace_marker, 1)[0].strip()
    return text.strip()


def _as_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return list(value)
    if isinstance(value, tuple):
        return list(value)
    return []


def _as_text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _as_public_error_text(value: Any) -> str | None:
    text = _as_text(value)
    if not text:
        return None
    cleaned = _strip_trace_suffix(text)
    return cleaned or None


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def _as_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalize_token(value: Any) -> str:
    return str(value or "").strip().lower()


def _has_safe_untrusted_fallback_output(
    *,
    diagnostics_payload: Mapping[str, Any],
    turn_record: Mapping[str, Any],
) -> bool:
    sources = (
        diagnostics_payload,
        _as_dict(turn_record.get("metadata")),
        turn_record,
    )
    return any(
        bool(_as_dict(source).get("untrusted_final_output_fallback_applied"))
        or bool(_as_dict(source).get("stripped_untrusted_final_output"))
        for source in sources
    )


def _resolved_turn_outcome(
    *,
    diagnostics_payload: Mapping[str, Any],
    turn_record: Mapping[str, Any],
) -> str:
    candidates = (
        turn_record.get("turn_outcome"),
        diagnostics_payload.get("turn_outcome"),
        diagnostics_payload.get("conversation_outcome"),
    )
    for candidate in candidates:
        normalized = _normalize_token(candidate)
        if normalized:
            return normalized
    return ""


def _resolved_failure_kind(
    *,
    diagnostics_payload: Mapping[str, Any],
    turn_record: Mapping[str, Any],
) -> str:
    candidates = (
        diagnostics_payload.get("failure_kind"),
        _as_dict(diagnostics_payload.get("failures")).get("failure_kind"),
        turn_record.get("failure_kind"),
        _as_dict(turn_record.get("failures")).get("failure_kind"),
    )
    for candidate in candidates:
        normalized = _normalize_token(candidate)
        if normalized and normalized != "none":
            return normalized
    return ""


def _is_terminal_failure(
    *,
    completion_reason: str | None,
    turn_outcome: str,
    failure_kind: str,
) -> bool:
    normalized_reason = _normalize_token(completion_reason)
    normalized_failure_kind = _normalize_token(failure_kind)
    if normalized_reason in _TERMINAL_FAILURE_COMPLETION_REASONS:
        return True
    if normalized_failure_kind in _TERMINAL_FAILURE_KINDS:
        return True
    return bool(turn_outcome == "partial" and normalized_failure_kind)


_RETIRED_RAG_EVIDENCE_KINDS = {"page", "web", "search", "url"}


def _evidence_kind_from_source(source: Mapping[str, Any]) -> str | None:
    raw_kind = (
        str(
            source.get("kind")
            or source.get("source_kind")
            or source.get("type")
            or source.get("source_type")
            or ""
        )
        .strip()
        .lower()
    )
    if raw_kind in {"kb", "knowledge_base", "knowledge"}:
        return "knowledge_base"
    if raw_kind in {"doc", "document", "file"}:
        return "document"
    if raw_kind in {"tool", "tool_result", "function"}:
        return "tool"
    if raw_kind in {"memory", "long_term_memory", "session_memory"}:
        return "memory"
    if raw_kind in _RETIRED_RAG_EVIDENCE_KINDS:
        return None
    return None


def _has_user_facing_source_payload(source: Mapping[str, Any]) -> bool:
    source_metadata = _as_dict(source.get("metadata"))
    for key in (
        "source_ref",
        "chunk_id",
        "doc_id",
        "document_id",
        "id",
        "url",
        "source_url",
        "snippet",
        "content",
        "summary",
    ):
        if _as_text(source.get(key)) or _as_text(source_metadata.get(key)):
            return True
    return _as_float(source.get("score") or source_metadata.get("score")) is not None


def build_turn_evidence_items(
    rag_sources: list[dict[str, Any]] | None,
) -> list[TurnEvidenceItem]:
    evidence_items: list[TurnEvidenceItem] = []
    for index, raw_source in enumerate(rag_sources or []):
        source = _as_dict(raw_source)
        if not _has_user_facing_source_payload(source):
            continue
        source_metadata = _as_dict(source.get("metadata"))
        url = _as_text(source.get("url")) or _as_text(
            source_metadata.get("url") or source_metadata.get("source_url")
        )
        source_ref = (
            _as_text(source.get("source_ref"))
            or _as_text(source.get("id"))
            or _as_text(source_metadata.get("source_ref"))
            or _as_text(source_metadata.get("id"))
        )
        evidence_kind = _evidence_kind_from_source(source)
        if evidence_kind is None:
            continue
        title = (
            _as_text(source.get("title"))
            or _as_text(source.get("name"))
            or _as_text(source_metadata.get("title"))
            or _as_text(source_metadata.get("name"))
            or _as_text(source.get("snippet"))
            or _as_text(source_metadata.get("snippet"))
            or f"Source {index + 1}"
        )
        evidence_items.append(
            TurnEvidenceItem(
                id=_as_text(source.get("id")) or f"evidence_{index + 1}",
                kind=evidence_kind,
                title=title,
                url=url,
                snippet=_as_text(
                    source.get("snippet")
                    or source.get("summary")
                    or source_metadata.get("snippet")
                    or source_metadata.get("content")
                    or source_metadata.get("summary")
                ),
                badge=_as_text(
                    source.get("badge")
                    or source.get("label")
                    or source_metadata.get("badge")
                    or source_metadata.get("label")
                ),
                score=_as_float(source.get("score") or source_metadata.get("score")),
                tool_call_id=_as_text(
                    source.get("tool_call_id")
                    or source.get("toolCallId")
                    or source_metadata.get("tool_call_id")
                    or source_metadata.get("toolCallId")
                ),
                source_ref=source_ref,
            )
        )
    return evidence_items


def _resolve_evidence_sources(
    *,
    diagnostics_payload: dict[str, Any],
    turn_record: dict[str, Any],
    rag_sources: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    del diagnostics_payload, turn_record
    return [_as_dict(item) for item in _as_list(rag_sources) if _as_dict(item)]


def _tool_result_payload(result: Any) -> dict[str, Any]:
    if isinstance(result, Mapping):
        return dict(result)
    raw_payload = getattr(result, "__dict__", None)
    return dict(raw_payload or {}) if isinstance(raw_payload, dict) else {}


def _tool_evidence_snippet(
    *,
    summary: str | None,
    output: str | None,
    error: str | None,
    max_length: int = 280,
) -> str | None:
    candidate = summary or error or output
    text = _as_text(candidate)
    if not text:
        return None
    compact = " ".join(text.split())
    if len(compact) <= max_length:
        return compact
    return f"{compact[: max_length - 3]}..."


def build_tool_evidence_items(
    tool_results: list[Any] | None,
) -> list[TurnEvidenceItem]:
    evidence_items: list[TurnEvidenceItem] = []
    for index, raw_result in enumerate(tool_results or []):
        result = _tool_result_payload(raw_result)
        tool_name = _as_text(result.get("name")) or f"tool_{index + 1}"
        tool_call_id = _as_text(result.get("tool_call_id")) or _as_text(
            result.get("id")
        )
        display_name = _as_text(result.get("display_name"))
        output = _as_text(result.get("output"))
        error = _as_public_error_text(result.get("error"))
        summary = _as_text(result.get("summary"))
        summary_payload = _as_dict(result.get("summary_payload")) or None
        success = bool(result.get("success")) and not error
        evidence_items.append(
            TurnEvidenceItem(
                id=tool_call_id or f"tool_{index + 1}_{tool_name}",
                kind="tool",
                title=display_name or tool_name,
                arguments=_as_dict(result.get("arguments")) or None,
                badge=_as_text(result.get("error_type")),
                display_name=display_name,
                duration_ms=(
                    _as_int(result.get("duration_ms"))
                    if result.get("duration_ms") is not None
                    else None
                ),
                error=error,
                error_type=_as_text(result.get("error_type")),
                output=output,
                result_link=_as_text(result.get("result_link")),
                skill_name=_as_text(result.get("skill_name")),
                skill_type=_as_text(result.get("skill_type")),
                snippet=_tool_evidence_snippet(
                    summary=summary,
                    output=output,
                    error=error,
                ),
                source_ref=tool_name,
                started_at=(
                    _as_int(result.get("started_at"))
                    if result.get("started_at") is not None
                    else None
                ),
                status="success" if success else "error",
                summary_payload=summary_payload,
                tool_call_id=tool_call_id,
                tool_name=tool_name,
                url=_as_text(result.get("result_link")),
            )
        )
    return evidence_items


def build_turn_evidence_events(
    rag_sources: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    evidence_items = build_turn_evidence_items(rag_sources)
    if not evidence_items:
        return [
            _canonical_stage_update_payload(
                stage_type="retrieval",
                status="skipped",
                title="Retrieval",
                summary="No evidence retrieved",
                metrics={"source_count": 0},
            )
        ]

    events: list[dict[str, Any]] = [
        _canonical_stage_update_payload(
            stage_type="retrieval",
            status="completed",
            title="Retrieval",
            summary=f"Retrieved {len(evidence_items)} sources",
            metrics={"source_count": len(evidence_items)},
            source_refs=[item.id for item in evidence_items],
        )
    ]
    for item in evidence_items:
        events.append({"event": "turn_evidence", "evidence": item.to_dict()})
    return events


def _extract_turn_events(
    diagnostics_payload: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for raw_event in _as_list(_as_dict(diagnostics_payload).get("turn_events")):
        event = _as_dict(raw_event)
        kind = _as_text(event.get("kind"))
        if not kind:
            continue
        events.append(
            {
                "kind": kind,
                "timestamp_ms": _as_int(event.get("timestamp_ms"), 0),
                "data": _as_dict(event.get("data")),
            }
        )
    return events


def _count_turn_events(turn_events: list[dict[str, Any]], kind: str) -> int:
    return sum(1 for event in turn_events if event.get("kind") == kind)


def _normalize_provider_events(
    diagnostics_payload: dict[str, Any],
) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for raw_event in _as_list(diagnostics_payload.get("provider_events")):
        event = _as_dict(raw_event)
        kind = _as_text(event.get("kind"))
        if not kind:
            continue
        event["kind"] = kind
        normalized.append(event)
    return normalized


def _has_provider_event_kind(diagnostics_payload: dict[str, Any], kind: str) -> bool:
    normalized_kind = _normalize_token(kind)
    return any(
        _normalize_token(event.get("kind")) == normalized_kind
        for event in _normalize_provider_events(diagnostics_payload)
    )


def _tool_selection_stage(
    diagnostics_payload: dict[str, Any],
) -> TurnFlowStage:
    filtering = _as_dict(diagnostics_payload.get("tool_filtering"))
    all_tools_count = _as_int(filtering.get("all_tools_count"), 0)
    candidate_tools_count = _as_int(filtering.get("candidate_tools_count"), 0)
    status = "completed"
    if all_tools_count > 0 and candidate_tools_count <= 0:
        status = "skipped"
    summary = f"Selected {candidate_tools_count} of {all_tools_count} tools"
    return TurnFlowStage(
        id="tool_selection",
        type="tool_selection",
        status=status,  # type: ignore[arg-type]
        title="Tool Selection",
        summary=summary,
        detail_lines=[summary],
        metrics={
            "all_tools_count": all_tools_count,
            "candidate_tools_count": candidate_tools_count,
            "filtering_reason": _as_text(filtering.get("filtering_reason")),
        },
    )


def _tool_execution_stage(
    turn_events: list[dict[str, Any]],
    tool_selection_stage: TurnFlowStage,
    diagnostics_payload: dict[str, Any],
    terminal_failure: bool,
    tool_results: list[Any] | None = None,
) -> TurnFlowStage:
    round_count = _count_turn_events(turn_events, "turn.tool_round")
    completed_count = _count_turn_events(turn_events, "turn.tool_completed")
    failed_count = _count_turn_events(turn_events, "turn.tool_failed")
    normalized_tool_results = [
        _tool_result_payload(result)
        for result in (tool_results or [])
        if _tool_result_payload(result)
    ]
    tool_call_ids = [
        tool_call_id
        for tool_call_id in (
            _as_text(result.get("tool_call_id")) or _as_text(result.get("id"))
            for result in normalized_tool_results
        )
        if tool_call_id
    ]
    if normalized_tool_results:
        completed_count = sum(
            1 for result in normalized_tool_results if result.get("success")
        )
        failed_count = len(normalized_tool_results) - completed_count
        round_count = max(round_count, len(normalized_tool_results))
    status = "skipped"
    summary = "No tools executed"
    if round_count > 0 or completed_count > 0 or failed_count > 0:
        status = "error" if failed_count > 0 else "completed"
        summary = (
            f"Executed {completed_count + failed_count} tool calls"
            if failed_count <= 0
            else f"Tool execution finished with {failed_count} failures"
        )
    elif tool_selection_stage.status == "completed":
        status = "completed"
        summary = "Tool selection completed without execution"
    return TurnFlowStage(
        id="tool_execution",
        type="tool_execution",
        status=status,  # type: ignore[arg-type]
        title="Tool Execution",
        summary=summary,
        detail_lines=[summary],
        metrics={
            "tool_call_count": completed_count + failed_count,
            "tool_rounds": round_count,
            "completed_tool_calls": completed_count,
            "failed_tool_calls": failed_count,
        },
        tool_call_ids=tool_call_ids,
    )


def _retrieval_stage(evidence_items: list[TurnEvidenceItem]) -> TurnFlowStage:
    if evidence_items:
        summary = f"Retrieved {len(evidence_items)} sources"
        return TurnFlowStage(
            id="retrieval",
            type="retrieval",
            status="completed",
            title="Retrieval",
            summary=summary,
            detail_lines=[summary],
            metrics={"source_count": len(evidence_items)},
            source_refs=[item.id for item in evidence_items],
        )
    return TurnFlowStage(
        id="retrieval",
        type="retrieval",
        status="skipped",
        title="Retrieval",
        summary="No evidence retrieved",
        detail_lines=["No evidence retrieved"],
        metrics={"source_count": 0},
    )


def _answer_assembly_stage(
    *,
    output: str,
    interrupted: bool,
    terminal_failure: bool,
    error_surface: dict[str, Any] | None,
) -> TurnFlowStage:
    if interrupted:
        status = "interrupted"
        summary = "Answer assembly interrupted"
    elif terminal_failure or error_surface:
        status = "error"
        summary = "Answer assembly failed"
    elif output:
        status = "completed"
        summary = "Answer assembled"
    else:
        status = "skipped"
        summary = "No answer content"
    return TurnFlowStage(
        id="answer_assembly",
        type="answer_assembly",
        status=status,  # type: ignore[arg-type]
        title="Answer Assembly",
        summary=summary,
        detail_lines=[summary],
    )


def _final_stage(
    *,
    completion_reason: str | None,
    interrupted: bool,
    terminal_failure: bool,
    error_surface: dict[str, Any] | None,
) -> TurnFlowStage:
    reason = _as_text(completion_reason) or "completed"
    if interrupted:
        return TurnFlowStage(
            id="failed",
            type="failed",
            status="interrupted",
            title="Interrupted",
            summary=reason,
            detail_lines=[reason],
        )
    if terminal_failure or error_surface:
        return TurnFlowStage(
            id="failed",
            type="failed",
            status="error",
            title="Failed",
            summary=reason,
            detail_lines=[reason],
        )
    return TurnFlowStage(
        id="completed",
        type="completed",
        status="completed",
        title="Completed",
        summary=reason,
        detail_lines=[reason],
    )


def _answer_card(
    *,
    output: str,
    evidence_items: list[TurnEvidenceItem],
    completion_reason: str | None,
    terminal_failure: bool,
    final_output_source: str | None,
    error: str | None,
    safe_untrusted_fallback_output: str | None = None,
) -> TurnAnswerCard:
    trusted_output = (
        output.strip()
        if is_trusted_assistant_final_output_source(final_output_source)
        else ""
    )
    safe_fallback_output = str(safe_untrusted_fallback_output or "").strip()
    safe_error = _as_public_error_text(error) or ""
    if trusted_output:
        summary = trusted_output
    elif safe_fallback_output:
        summary = safe_fallback_output
    elif terminal_failure and safe_error:
        summary = safe_error
    else:
        summary = "No trusted assistant final answer."
    if len(summary) > 280:
        summary = f"{summary[:277]}..."
    confidence = "medium" if (trusted_output or safe_fallback_output) else "low"
    if trusted_output and (completion_reason or "") in {"completed", "stop"}:
        confidence = "high"
    if terminal_failure or (completion_reason or "") in {"error", "interrupted"}:
        confidence = "low"
    source_chip_ids = [item.id for item in evidence_items]
    return TurnAnswerCard(
        summary=summary,
        sections=[{"id": "final_answer", "title": "Answer", "content": summary}],
        source_chip_ids=source_chip_ids,
        confidence_label=confidence,
        follow_up_suggestions=[],
    )


def build_turn_flow_view_model(
    *,
    diagnostics_payload: dict[str, Any] | None,
    turn_record: dict[str, Any] | None,
    rag_sources: list[dict[str, Any]] | None,
    tool_results: list[Any] | None = None,
    output: str,
    completion_reason: str | None,
    interrupted: bool,
    error: str | None = None,
) -> dict[str, Any]:
    diagnostics = _as_dict(diagnostics_payload)
    record = _as_dict(turn_record)
    resolved_completion_reason = (
        _as_text(completion_reason)
        or _as_text(record.get("termination_reason"))
        or _as_text(diagnostics.get("termination_reason"))
        or "completed"
    )
    turn_outcome = _resolved_turn_outcome(
        diagnostics_payload=diagnostics,
        turn_record=record,
    )
    final_output_source = (
        _as_text(diagnostics.get("final_output_source"))
        or _as_text(record.get("final_output_source"))
        or None
    )
    safe_untrusted_fallback_output = (
        str(output or "").strip()
        if _has_safe_untrusted_fallback_output(
            diagnostics_payload=diagnostics,
            turn_record=record,
        )
        else ""
    )
    trusted_output = (
        str(output or "").strip()
        if is_trusted_assistant_final_output_source(final_output_source)
        else ""
    )
    failure_kind = _resolved_failure_kind(
        diagnostics_payload=diagnostics,
        turn_record=record,
    )
    terminal_failure = _is_terminal_failure(
        completion_reason=resolved_completion_reason,
        turn_outcome=turn_outcome,
        failure_kind=failure_kind,
    )
    untrusted_failure_output = bool(
        terminal_failure and final_output_source == "partial_output"
    )

    error_message = _as_public_error_text(error) or _as_public_error_text(
        record.get("error_message")
    )
    if not error_message and terminal_failure:
        error_message = (
            _as_public_error_text(safe_untrusted_fallback_output)
            or _SAFE_TURN_FAILURE_MESSAGE
        )
    if not error_message and _normalize_token(resolved_completion_reason) == "error":
        error_message = "Turn finished with an execution error."
    error_surface = (
        {
            "message": error_message,
            "trace_id": trace_id_var.get() or None,
            "failure_kind": failure_kind or None,
            **(
                {"error_type": "untrusted_final_output_source"}
                if untrusted_failure_output
                else {}
            ),
        }
        if error_message
        else None
    )

    retrieval_sources = _resolve_evidence_sources(
        diagnostics_payload=diagnostics,
        turn_record=record,
        rag_sources=rag_sources,
    )
    rag_evidence_items = build_turn_evidence_items(retrieval_sources)
    tool_evidence_items = build_tool_evidence_items(tool_results)
    evidence_items = [*rag_evidence_items, *tool_evidence_items]
    turn_events = _extract_turn_events(diagnostics)
    tool_selection = _tool_selection_stage(diagnostics)
    timeline: list[TurnFlowStage] = [
        TurnFlowStage(
            id="thinking",
            type="thinking",
            status=(
                "interrupted"
                if interrupted
                else "error"
                if error_surface
                else "completed"
            ),
            title="Thinking",
            summary="Reasoning summary generated",
            detail_lines=["Reasoning summary generated"],
            started_at_ms=0,
            ended_at_ms=max(
                [0, *[_as_int(event.get("timestamp_ms"), 0) for event in turn_events]]
            ),
        ),
        tool_selection,
        _tool_execution_stage(
            turn_events,
            tool_selection,
            diagnostics,
            terminal_failure,
            tool_results=tool_results,
        ),
        _retrieval_stage(rag_evidence_items),
        _answer_assembly_stage(
            output=trusted_output or safe_untrusted_fallback_output,
            interrupted=interrupted,
            terminal_failure=terminal_failure,
            error_surface=error_surface,
        ),
    ]
    timeline.append(
        _final_stage(
            completion_reason=resolved_completion_reason,
            interrupted=interrupted,
            terminal_failure=terminal_failure,
            error_surface=error_surface,
        )
    )
    answer_card = _answer_card(
        output=str(output or ""),
        evidence_items=evidence_items,
        completion_reason=resolved_completion_reason,
        terminal_failure=terminal_failure,
        final_output_source=final_output_source,
        error=error_message,
        safe_untrusted_fallback_output=safe_untrusted_fallback_output,
    )
    flow = TurnFlowViewModel(
        timeline=timeline,
        evidence=evidence_items,
        answer_card=answer_card,
        completion_reason=resolved_completion_reason,
        interrupted=bool(interrupted),
        error_surface=error_surface,
    )
    return flow.to_dict()


def resolve_final_stage_status(turn_flow: Mapping[str, Any] | None) -> str:
    timeline = _as_list(_as_dict(turn_flow).get("timeline"))
    if not timeline:
        return "completed"
    final_stage = _as_dict(timeline[-1])
    status = _as_text(final_stage.get("status"))
    return status or "completed"


def _canonical_stage_payload(
    *,
    event: str,
    stage_type: str,
    status: str,
    title: str,
    summary: str | None = None,
    detail_lines: list[str] | None = None,
    metrics: dict[str, Any] | None = None,
    tool_call_ids: list[str] | None = None,
    source_refs: list[str] | None = None,
) -> dict[str, Any]:
    stage = TurnFlowStage(
        id=stage_type,
        type=stage_type,  # type: ignore[arg-type]
        status=status,  # type: ignore[arg-type]
        title=title,
        summary=summary,
        detail_lines=list(detail_lines or []),
        metrics=dict(metrics or {}),
        tool_call_ids=list(tool_call_ids or []),
        source_refs=list(source_refs or []),
    ).to_dict()
    return {"event": event, "stage": stage}


def _canonical_stage_event_payload(**kwargs: Any) -> dict[str, Any]:
    return _canonical_stage_payload(event="turn_stage", **kwargs)


def _canonical_stage_update_payload(**kwargs: Any) -> dict[str, Any]:
    return _canonical_stage_payload(event="turn_stage_update", **kwargs)


def build_tool_selection_turn_flow_events(
    *,
    total: int,
    selected: int,
) -> list[dict[str, Any]]:
    summary = f"Selected {selected} of {total} tools"
    metrics = {"all_tools_count": total, "candidate_tools_count": selected}
    return [
        _canonical_stage_event_payload(
            stage_type="tool_selection",
            status="running",
            title="Tool Selection",
            summary=summary,
            metrics=metrics,
        ),
        _canonical_stage_update_payload(
            stage_type="tool_selection",
            status="skipped" if total > 0 and selected == 0 else "completed",
            title="Tool Selection",
            summary=summary,
            metrics=metrics,
        ),
    ]


def build_thinking_turn_flow_event(
    *,
    summary: str | None = None,
) -> dict[str, Any]:
    return _canonical_stage_update_payload(
        stage_type="thinking",
        status="running",
        title="Thinking",
        summary=summary or "Thinking in progress",
    )


def build_tool_execution_started_event(
    *,
    tool_name: str,
    tool_call_id: str | None = None,
) -> dict[str, Any]:
    tool_call_ids = [tool_call_id] if tool_call_id else None
    return _canonical_stage_update_payload(
        stage_type="tool_execution",
        status="running",
        title="Tool Execution",
        summary=f"Calling {tool_name or 'tool'}",
        tool_call_ids=tool_call_ids,
    )


def build_tool_execution_result_event(
    *,
    tool_name: str,
    success: bool,
    duration_ms: int = 0,
    tool_call_id: str | None = None,
) -> dict[str, Any]:
    tool_call_ids = [tool_call_id] if tool_call_id else None
    return _canonical_stage_update_payload(
        stage_type="tool_execution",
        status="completed" if success else "error",
        title="Tool Execution",
        summary=(
            f"{tool_name or 'tool'} completed"
            if success
            else f"{tool_name or 'tool'} failed"
        ),
        metrics={"duration_ms": duration_ms},
        tool_call_ids=tool_call_ids,
    )


def build_answer_assembly_turn_flow_event() -> dict[str, Any]:
    return _canonical_stage_update_payload(
        stage_type="answer_assembly",
        status="running",
        title="Answer Assembly",
        summary="Streaming answer content",
    )


def build_initial_turn_flow_events(
    *,
    optimize_event: Any,
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = [
        _canonical_stage_event_payload(
            stage_type="thinking",
            status="running",
            title="Thinking",
            summary="Planning response",
        )
    ]
    if isinstance(optimize_event, Mapping):
        events.extend(
            build_tool_selection_turn_flow_events(
                total=_as_int(optimize_event.get("total"), 0),
                selected=_as_int(optimize_event.get("selected"), 0),
            )
        )
    return events


def build_turn_answer_card_event(
    turn_flow: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    answer_card = _as_dict(_as_dict(turn_flow).get("answer_card"))
    if not answer_card:
        return None
    return {
        "event": "turn_answer_card",
        "answer_card": answer_card,
        "source_chip_ids": _as_list(answer_card.get("source_chip_ids")),
    }


__all__ = [
    "build_answer_assembly_turn_flow_event",
    "build_initial_turn_flow_events",
    "build_turn_answer_card_event",
    "build_turn_evidence_events",
    "build_turn_evidence_items",
    "build_turn_flow_view_model",
    "build_thinking_turn_flow_event",
    "build_tool_execution_result_event",
    "build_tool_execution_started_event",
    "build_tool_selection_turn_flow_events",
    "resolve_final_stage_status",
]
