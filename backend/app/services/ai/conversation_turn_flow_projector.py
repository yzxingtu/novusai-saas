"""Turn-flow read-model projection helpers for assistant messages."""

from __future__ import annotations

import json
from typing import Any

from app.services.ai.conversation_diagnostics_projector import (
    ConversationDiagnosticsProjector,
)
from app.services.ai.turn_failure_normalizer import (
    derive_completed_tool_names,
)
from app.services.ai.turn_failure_normalizer import (
    derive_terminal_status as _derive_terminal_status_from_normalizer,
)
from app.services.ai.turn_failure_normalizer import (
    is_trusted_final_output_source as _is_trusted_final_output_source,
)
from app.services.ai.turn_failure_normalizer import (
    normalize_failure_kind as _normalize_failure_kind_from_normalizer,
)

_DEFAULT_TIMELINE_STAGE_TYPES = {
    "thinking",
    "tool_selection",
    "tool_execution",
    "retrieval",
    "answer_assembly",
    "completed",
    "failed",
}

_DEFAULT_STAGE_STATUSES = {"running", "completed", "skipped", "error", "interrupted"}

_DEFAULT_ERROR_SURFACE_MESSAGE = "The request ended before a final answer was produced."
_PUBLIC_THINKING_STAGE_SUMMARY = "已完成思考与规划"
_MISSING_FINAL_ANSWER_SUMMARIES = frozenset(
    {
        "no trusted assistant final answer.",
        "no trusted final answer.",
        "no assistant final answer.",
        "无可信最终答复",
        "无可信最终答案",
    }
)
_LEGACY_TOOL_CALLS_METADATA_KEYS = (
    "canonical_tool_calls",
    "canonicalToolCalls",
)


def _strip_trace_suffix(text: str) -> str:
    trace_marker = " [trace_id="
    if trace_marker in text:
        return text.split(trace_marker, 1)[0].strip()
    return text.strip()


def _summarize_thinking_content(value: Any, *, max_length: int = 160) -> str | None:
    text = _to_non_empty_str(value)
    if not text:
        return None
    return _PUBLIC_THINKING_STAGE_SUMMARY


def _to_non_empty_str(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    if text.lower() in {"none", "null", "undefined"}:
        return None
    return text


def _to_public_error_str(value: Any) -> str | None:
    text = _to_non_empty_str(value)
    if not text:
        return None
    cleaned = _strip_trace_suffix(text)
    return cleaned or None


def _normalize_optional_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _normalize_optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalize_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    normalized: list[str] = []
    for item in value:
        text = _to_non_empty_str(item)
        if text and text not in normalized:
            normalized.append(text)
    return normalized


def _normalize_line_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    normalized: list[str] = []
    for item in value:
        text = _to_non_empty_str(item)
        if text:
            normalized.append(text)
    return normalized


def _normalize_provider_events(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    normalized: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        payload = dict(item)
        kind = _to_non_empty_str(payload.get("kind"))
        if kind:
            payload["kind"] = kind
        normalized.append(payload)
    return normalized


def _resolve_tool_selection_counts(
    candidate_tools: list[str],
    selected_tools: list[str],
) -> tuple[int, int]:
    selected_count = len(selected_tools)
    candidate_count = len(candidate_tools) or selected_count
    return max(candidate_count, selected_count), selected_count


def _summarize_retrieval_progress(
    *,
    evidence_count: int,
    terminal_status: str,
) -> str:
    del terminal_status
    if evidence_count > 0:
        return f"整理了 {evidence_count} 条证据"
    return "整理了 0 条证据"


def _derive_error_surface(metadata: dict[str, Any]) -> dict[str, Any] | None:
    raw = metadata.get("error_surface")
    if isinstance(raw, dict):
        payload = {
            "message": _to_public_error_str(raw.get("message")),
            "error_type": _to_non_empty_str(raw.get("error_type")),
            "trace_id": _to_non_empty_str(raw.get("trace_id")),
            "debug_message": _to_public_error_str(raw.get("debug_message")),
        }
        if any(payload.values()):
            return payload

    payload = {
        "message": _to_public_error_str(
            metadata.get("error_message")
            or metadata.get("friendly_message")
            or metadata.get("public_error_message")
        ),
        "error_type": _to_non_empty_str(metadata.get("error_type")),
        "trace_id": _to_non_empty_str(
            metadata.get("error_trace_id") or metadata.get("trace_id")
        ),
        "debug_message": _to_public_error_str(metadata.get("error_debug_message")),
    }
    if any(payload.values()):
        return payload
    return None


def _derive_terminal_status(
    *,
    turn_outcome: str | None,
    completion_reason: str | None,
    interrupted: bool,
    failure_kind: str | None,
    final_output_source: str | None = None,
) -> str:
    return _derive_terminal_status_from_normalizer(
        turn_outcome=turn_outcome,
        completion_reason=completion_reason,
        interrupted=interrupted,
        failure_kind=failure_kind,
        final_output_source=final_output_source,
    )


def _normalize_failure_kind(value: Any) -> str | None:
    return _normalize_failure_kind_from_normalizer(value)


def _find_terminal_stage_index(timeline: list[dict[str, Any]]) -> int | None:
    for index in range(len(timeline) - 1, -1, -1):
        stage = timeline[index]
        stage_type = _to_non_empty_str(stage.get("type"))
        stage_id = _to_non_empty_str(stage.get("id"))
        if stage_type in {"completed", "failed"} or stage_id == "terminal":
            return index
    return None


def _build_terminal_stage(
    *,
    terminal_status: str,
    completion_reason: str | None,
    source_refs: list[str],
) -> dict[str, Any]:
    reason = completion_reason or (
        "error" if terminal_status in {"error", "interrupted"} else "completed"
    )
    if terminal_status == "error":
        title = "本轮失败"
        stage_type = "failed"
    elif terminal_status == "interrupted":
        title = "本轮中断"
        stage_type = "failed"
    else:
        title = "本轮结束"
        stage_type = "completed"
    return {
        "id": "terminal",
        "type": stage_type,
        "status": terminal_status,
        "title": title,
        "summary": reason,
        "detail_lines": [],
        "started_at_ms": None,
        "ended_at_ms": None,
        "duration_ms": None,
        "metrics": {},
        "tool_call_ids": [],
        "source_refs": list(source_refs),
    }


def _ensure_answer_assembly_stage(
    timeline: list[dict[str, Any]],
    *,
    status: str,
    source_refs: list[str],
) -> list[dict[str, Any]]:
    answer_index = next(
        (
            idx
            for idx, stage in enumerate(timeline)
            if stage.get("type") == "answer_assembly"
        ),
        None,
    )
    answer_summary = "答复生成失败" if status == "error" else "答复生成中断"
    answer_payload = {
        "id": "answer_assembly",
        "type": "answer_assembly",
        "status": status,
        "title": "答案生成",
        "summary": answer_summary,
        "detail_lines": [],
        "started_at_ms": None,
        "ended_at_ms": None,
        "duration_ms": None,
        "metrics": {},
        "tool_call_ids": [],
        "source_refs": list(source_refs),
    }
    if answer_index is None:
        terminal_index = _find_terminal_stage_index(timeline)
        if terminal_index is None:
            timeline.append(answer_payload)
        else:
            timeline.insert(terminal_index, answer_payload)
        return timeline

    stage = dict(timeline[answer_index])
    stage["status"] = status
    if status == "error":
        stage["summary"] = "答复生成失败"
    elif status == "interrupted":
        stage["summary"] = "答复生成中断"
    if not _normalize_string_list(stage.get("source_refs")):
        stage["source_refs"] = list(source_refs)
    timeline[answer_index] = stage
    return timeline


def _apply_terminal_stage_semantics(
    timeline: list[dict[str, Any]],
    *,
    terminal_status: str,
    completion_reason: str | None,
    source_refs: list[str],
) -> list[dict[str, Any]]:
    patched = [dict(item) for item in timeline]
    if terminal_status in {"error", "interrupted"}:
        patched = _ensure_answer_assembly_stage(
            patched,
            status=terminal_status,
            source_refs=source_refs,
        )

    terminal_payload = _build_terminal_stage(
        terminal_status=terminal_status,
        completion_reason=completion_reason,
        source_refs=source_refs,
    )
    terminal_index = _find_terminal_stage_index(patched)
    if terminal_index is None:
        patched.append(terminal_payload)
    else:
        existing = dict(patched[terminal_index])
        existing.update(
            {
                "id": terminal_payload["id"],
                "type": terminal_payload["type"],
                "status": terminal_payload["status"],
                "title": terminal_payload["title"],
                "summary": terminal_payload["summary"],
            }
        )
        if not _normalize_string_list(existing.get("source_refs")):
            existing["source_refs"] = list(source_refs)
        patched[terminal_index] = existing
    return _normalize_timeline(patched)


def _ensure_error_surface(
    *,
    error_surface: dict[str, Any] | None,
    metadata: dict[str, Any],
    terminal_status: str,
    completion_reason: str | None,
    failure_kind: str | None,
    final_output_source: str | None = None,
) -> dict[str, Any] | None:
    if terminal_status != "error":
        return error_surface
    payload = dict(error_surface or {})
    message = _to_public_error_str(payload.get("message")) or _to_public_error_str(
        metadata.get("error_message")
        or metadata.get("friendly_message")
        or metadata.get("public_error_message")
    )
    if not message:
        message = _DEFAULT_ERROR_SURFACE_MESSAGE
    error_type = _to_non_empty_str(
        payload.get("error_type")
    ) or _normalize_failure_kind(failure_kind)
    if (
        not error_type
        and final_output_source
        and not _is_trusted_final_output_source(final_output_source)
    ):
        error_type = "untrusted_final_output_source"
    if not error_type:
        metadata_error_type = _to_non_empty_str(metadata.get("error_type"))
        if metadata_error_type and metadata_error_type not in {"completed", "stop"}:
            error_type = metadata_error_type
        elif completion_reason and completion_reason not in {"completed", "stop"}:
            error_type = completion_reason
        else:
            error_type = "stream_execution_error"
    trace_id = _to_non_empty_str(payload.get("trace_id")) or _to_non_empty_str(
        metadata.get("error_trace_id") or metadata.get("trace_id")
    )
    debug_message = _to_public_error_str(
        payload.get("debug_message")
    ) or _to_public_error_str(metadata.get("error_debug_message"))
    return {
        "message": message,
        "error_type": error_type,
        "trace_id": trace_id,
        "debug_message": debug_message,
    }


def _map_source_kind(raw_kind: Any) -> str:
    kind = str(raw_kind or "").strip().lower()
    if kind == "web":
        return "knowledge_base"
    if kind in {"knowledge", "knowledge_base", "kb", "formal_kb"}:
        return "knowledge_base"
    if kind in {"memory", "long_term_memory", "session_memory"}:
        return "memory"
    if kind in {"tool", "tool_call"}:
        return "tool"
    return "knowledge_base"


def _map_legacy_source_kind(raw_kind: Any) -> str:
    return _map_source_kind(raw_kind)


def _is_user_facing_evidence_item(item: dict[str, Any]) -> bool:
    kind = _map_source_kind(item.get("kind"))
    if kind == "tool":
        return bool(
            _to_non_empty_str(item.get("tool_call_id"))
            or _to_non_empty_str(item.get("tool_name"))
            or _to_non_empty_str(item.get("source_ref"))
            or _to_non_empty_str(item.get("output"))
            or _to_non_empty_str(item.get("error"))
            or _to_non_empty_str(item.get("result_link"))
            or _to_non_empty_str(item.get("status"))
        )
    return bool(
        _to_non_empty_str(item.get("url"))
        or _to_non_empty_str(item.get("snippet"))
        or _to_non_empty_str(item.get("badge"))
        or _to_non_empty_str(item.get("source_ref"))
        or _normalize_optional_float(item.get("score")) is not None
    )


def _normalize_timeline_item(item: Any) -> dict[str, Any] | None:
    if not isinstance(item, dict):
        return None
    stage_type = _to_non_empty_str(item.get("type")) or "thinking"
    if stage_type not in _DEFAULT_TIMELINE_STAGE_TYPES:
        stage_type = "thinking"
    status = _to_non_empty_str(item.get("status")) or "completed"
    if status not in _DEFAULT_STAGE_STATUSES:
        status = "completed"
    summary = _to_non_empty_str(item.get("summary"))
    detail_lines = _normalize_line_list(item.get("detail_lines"))
    if stage_type == "thinking":
        summary = _PUBLIC_THINKING_STAGE_SUMMARY
        detail_lines = []
    metrics = item.get("metrics")
    return {
        "id": _to_non_empty_str(item.get("id")) or stage_type,
        "type": stage_type,
        "status": status,
        "title": _to_non_empty_str(item.get("title")),
        "summary": summary,
        "detail_lines": detail_lines,
        "started_at_ms": _normalize_optional_int(item.get("started_at_ms")),
        "ended_at_ms": _normalize_optional_int(item.get("ended_at_ms")),
        "duration_ms": _normalize_optional_int(item.get("duration_ms")),
        "metrics": dict(metrics) if isinstance(metrics, dict) else {},
        "tool_call_ids": _normalize_string_list(item.get("tool_call_ids")),
        "source_refs": _normalize_string_list(item.get("source_refs")),
    }


def _normalize_timeline(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    normalized: list[dict[str, Any]] = []
    for item in value:
        stage = _normalize_timeline_item(item)
        if stage is not None:
            normalized.append(stage)
    return normalized


def _looks_like_missing_final_answer_summary(value: Any) -> bool:
    summary = (_to_non_empty_str(value) or "").strip().lower()
    return bool(summary and summary in _MISSING_FINAL_ANSWER_SUMMARIES)


def _is_untrusted_final_output_failure(
    *,
    failure_kind: str | None,
    final_output_source: str | None,
) -> bool:
    if _normalize_failure_kind(failure_kind) == "untrusted_final_output_source":
        return True
    return bool(
        final_output_source and not _is_trusted_final_output_source(final_output_source)
    )


def _has_safe_untrusted_fallback_output(*sources: Any) -> bool:
    for source in sources:
        payload = dict(source) if isinstance(source, dict) else {}
        if not payload:
            continue
        if bool(payload.get("untrusted_final_output_fallback_applied")) or bool(
            payload.get("stripped_untrusted_final_output")
        ):
            return True
    return False


def _resolve_failure_text_content_fallback(
    *,
    text_content: str | None,
    terminal_status: str,
    failure_kind: str | None,
    final_output_source: str | None,
    safe_untrusted_fallback_output: bool = False,
) -> str | None:
    if terminal_status not in {"error", "interrupted"}:
        return text_content
    if (
        _is_untrusted_final_output_failure(
            failure_kind=failure_kind,
            final_output_source=final_output_source,
        )
        and not safe_untrusted_fallback_output
    ):
        return None
    if _is_untrusted_final_output_failure(
        failure_kind=failure_kind,
        final_output_source=final_output_source,
    ):
        return text_content
    return text_content


def _specific_error_surface_message(error_surface: dict[str, Any] | None) -> str | None:
    if not isinstance(error_surface, dict):
        return None
    message = _to_public_error_str(error_surface.get("message"))
    if not message or message == _DEFAULT_ERROR_SURFACE_MESSAGE:
        return None
    return message


def _apply_failure_answer_summary_fallback(
    answer_card: dict[str, Any],
    *,
    fallback_summary: str | None,
) -> dict[str, Any]:
    replacement = _to_non_empty_str(fallback_summary)
    if not replacement:
        return answer_card
    current_summary = _to_non_empty_str(answer_card.get("summary"))
    if current_summary and not _looks_like_missing_final_answer_summary(
        current_summary
    ):
        return answer_card

    patched = dict(answer_card)
    patched["summary"] = replacement
    sections = patched.get("sections")
    if isinstance(sections, list) and sections:
        normalized_sections: list[dict[str, Any]] = []
        for index, item in enumerate(sections):
            section = dict(item) if isinstance(item, dict) else {}
            if index == 0:
                section["content"] = replacement
            normalized_sections.append(section)
        patched["sections"] = normalized_sections
    else:
        patched["sections"] = [
            {
                "title": "Answer",
                "content": replacement,
            }
        ]
    patched["confidence_label"] = "low"
    return patched


def _stage_tool_call_count(stage: dict[str, Any]) -> int:
    metrics = stage.get("metrics")
    metrics_payload = dict(metrics) if isinstance(metrics, dict) else {}
    return (
        _normalize_optional_int(metrics_payload.get("tool_call_count"))
        or len(_normalize_string_list(stage.get("tool_call_ids")))
        or 0
    )


def _stabilize_timeline_statuses(
    timeline: list[dict[str, Any]],
    *,
    selected_tools: list[str],
    completed_tool_names: list[str],
) -> list[dict[str, Any]]:
    if not timeline:
        return timeline

    stable_timeline: list[dict[str, Any]] = []
    completed_tool_count = len(completed_tool_names)
    for item in timeline:
        stage = dict(item)
        stage_type = _to_non_empty_str(stage.get("type"))
        stage_status = _to_non_empty_str(stage.get("status"))

        if (stage_type == "thinking" and stage_status == "error") or (
            stage_type == "tool_selection"
            and selected_tools
            and stage_status == "skipped"
        ):
            stage["status"] = "completed"
        elif stage_type == "tool_execution":
            observed_tool_count = _stage_tool_call_count(stage)
            effective_tool_count = observed_tool_count or completed_tool_count
            if effective_tool_count > 0:
                stage["status"] = "completed"
                summary = _to_non_empty_str(stage.get("summary"))
                if summary in {
                    None,
                    "工具已进入执行阶段，但未等到返回结果",
                    "工具执行在返回结果前被中断",
                }:
                    stable_summary = f"执行了 {effective_tool_count} 个工具调用"
                    stage["summary"] = stable_summary
                    stage["detail_lines"] = [stable_summary]
                metrics = dict(stage.get("metrics") or {})
                metrics.setdefault("tool_call_count", effective_tool_count)
                stage["metrics"] = metrics

        stable_timeline.append(stage)

    return _normalize_timeline(stable_timeline)


def _normalize_evidence_item(item: Any) -> dict[str, Any] | None:
    if not isinstance(item, dict):
        return None
    evidence_id = _to_non_empty_str(item.get("id"))
    if not evidence_id:
        return None
    payload = {
        "id": evidence_id,
        "kind": _map_source_kind(item.get("kind")),
        "title": _to_non_empty_str(item.get("title")) or "Source",
        "url": _to_non_empty_str(item.get("url")),
        "snippet": _to_non_empty_str(item.get("snippet")),
        "badge": _to_non_empty_str(item.get("badge")),
        "score": _normalize_optional_float(item.get("score")),
        "tool_call_id": _to_non_empty_str(item.get("tool_call_id")),
        "source_ref": _to_non_empty_str(item.get("source_ref")),
    }
    if payload["kind"] != "tool":
        return payload if _is_user_facing_evidence_item(payload) else None

    arguments_value = _normalize_tool_call_arguments(
        item.get("arguments")
        if item.get("arguments") is not None
        else (
            dict(item.get("function")) if isinstance(item.get("function"), dict) else {}
        ).get("arguments")
    )
    if arguments_value is not None:
        payload["arguments"] = arguments_value

    optional_fields = {
        "display_name": _to_non_empty_str(item.get("display_name")),
        "duration_ms": _normalize_optional_int(item.get("duration_ms")),
        "error": _to_non_empty_str(item.get("error")),
        "error_type": _to_non_empty_str(item.get("error_type")),
        "output": _to_non_empty_str(item.get("output")),
        "result_link": _to_non_empty_str(item.get("result_link")) or payload["url"],
        "skill_name": _to_non_empty_str(item.get("skill_name")),
        "skill_type": _to_non_empty_str(item.get("skill_type")),
        "started_at": _normalize_optional_int(item.get("started_at")),
        "status": _to_non_empty_str(item.get("status")),
        "summary_payload": (
            dict(item.get("summary_payload"))
            if isinstance(item.get("summary_payload"), dict)
            else None
        ),
        "tool_name": _to_non_empty_str(item.get("tool_name")) or payload["source_ref"],
    }
    for key, value in optional_fields.items():
        if value is not None:
            payload[key] = value
    return payload if _is_user_facing_evidence_item(payload) else None


def _normalize_tool_call_arguments(value: Any) -> dict[str, Any] | None:
    if isinstance(value, dict):
        return dict(value)
    raw = _to_non_empty_str(value)
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        return {"raw": raw}
    if isinstance(parsed, dict):
        return dict(parsed)
    return {"raw": raw}


def _resolve_tool_calls(tool_calls: Any) -> list[dict[str, Any]]:
    resolved: list[dict[str, Any]] = []
    if not isinstance(tool_calls, list):
        return resolved
    resolved.extend(dict(item) for item in tool_calls if isinstance(item, dict))
    return resolved


def _resolve_legacy_tool_calls(metadata: dict[str, Any] | None) -> list[dict[str, Any]]:
    resolved: list[dict[str, Any]] = []

    def _extend(candidate: Any) -> None:
        if not isinstance(candidate, list):
            return
        resolved.extend(dict(item) for item in candidate if isinstance(item, dict))

    metadata_payload = dict(metadata) if isinstance(metadata, dict) else {}
    turn_record = ConversationDiagnosticsProjector.normalize_turn_record_payload(
        metadata_payload.get("turn_record")
    )
    turn_record_payload = (
        dict(turn_record or {}) if isinstance(turn_record, dict) else {}
    )
    turn_record_metadata = (
        dict(turn_record_payload.get("metadata") or {})
        if isinstance(turn_record_payload.get("metadata"), dict)
        else {}
    )

    for key in _LEGACY_TOOL_CALLS_METADATA_KEYS:
        _extend(metadata_payload.get(key))
        _extend(turn_record_payload.get(key))
        _extend(turn_record_metadata.get(key))
        for metadata_key in ("orchestration", "turn_diagnostics"):
            nested = turn_record_metadata.get(metadata_key)
            if isinstance(nested, dict):
                _extend(nested.get(key))

    return resolved


def _build_tool_evidence_from_tool_call(
    call: dict[str, Any],
    index: int,
) -> dict[str, Any] | None:
    call_id = _to_non_empty_str(call.get("id")) or f"tool_{index + 1}"
    tool_name = _to_non_empty_str(call.get("name")) or _to_non_empty_str(
        (
            dict(call.get("function")) if isinstance(call.get("function"), dict) else {}
        ).get("name")
    )
    display_name = _to_non_empty_str(call.get("display_name"))
    summary = _to_non_empty_str(call.get("summary"))
    result_link = _to_non_empty_str(call.get("result_link"))
    output = _to_non_empty_str(call.get("output"))
    if not (tool_name or display_name or summary or result_link or output):
        return None

    payload: dict[str, Any] = {
        "id": f"ev_tool_{call_id}",
        "kind": "tool",
        "title": display_name or tool_name or f"Tool {index + 1}",
        "url": result_link,
        "snippet": summary,
        "badge": _to_non_empty_str(call.get("error_type")),
        "score": None,
        "tool_call_id": call_id,
        "source_ref": tool_name or call_id,
        "tool_name": tool_name or call_id,
        "status": "success" if call.get("success") else "error",
    }

    arguments_value = _normalize_tool_call_arguments(
        call.get("arguments")
        if call.get("arguments") is not None
        else (
            dict(call.get("function")) if isinstance(call.get("function"), dict) else {}
        ).get("arguments")
    )
    if arguments_value is not None:
        payload["arguments"] = arguments_value

    optional_fields = {
        "display_name": display_name,
        "duration_ms": _normalize_optional_int(call.get("duration_ms")),
        "error": _to_non_empty_str(call.get("error")),
        "error_type": _to_non_empty_str(call.get("error_type")),
        "output": output,
        "result_link": result_link,
        "skill_name": _to_non_empty_str(call.get("skill_name")),
        "skill_type": _to_non_empty_str(call.get("skill_type")),
        "started_at": _normalize_optional_int(call.get("started_at")),
        "summary_payload": (
            dict(call.get("summary_payload"))
            if isinstance(call.get("summary_payload"), dict)
            else None
        ),
    }
    for key, value in optional_fields.items():
        if value is not None:
            payload[key] = value
    return payload


def _build_legacy_rag_evidence(
    source: dict[str, Any],
    index: int,
) -> dict[str, Any]:
    return {
        "id": _to_non_empty_str(source.get("source_ref") or source.get("chunk_id"))
        or f"ev_rag_{index + 1}",
        "kind": _map_legacy_source_kind(
            source.get("kind") or source.get("source_kind")
        ),
        "title": _to_non_empty_str(
            source.get("title")
            or source.get("source")
            or source.get("name")
            or source.get("chunk_id")
        )
        or f"Source {index + 1}",
        "url": _to_non_empty_str(source.get("url") or source.get("source_url")),
        "snippet": _to_non_empty_str(source.get("snippet") or source.get("content")),
        "badge": _to_non_empty_str(source.get("badge")),
        "score": _normalize_optional_float(source.get("score")),
        "tool_call_id": None,
        "source_ref": _to_non_empty_str(
            source.get("source_ref") or source.get("chunk_id")
        ),
    }


def _evidence_identity(item: dict[str, Any]) -> str:
    kind = _to_non_empty_str(item.get("kind")) or "knowledge_base"
    if kind == "tool":
        return (
            f"tool:{_to_non_empty_str(item.get('tool_call_id'))}"
            or f"tool:{_to_non_empty_str(item.get('tool_name'))}"
            or f"tool:{_to_non_empty_str(item.get('source_ref'))}"
            or f"tool:{_to_non_empty_str(item.get('id'))}"
        )
    return (
        f"{kind}:{_to_non_empty_str(item.get('url'))}"
        or f"{kind}:{_to_non_empty_str(item.get('source_ref'))}"
        or f"{kind}:{_to_non_empty_str(item.get('id'))}"
    )


def _merge_evidence_item(
    current: dict[str, Any], incoming: dict[str, Any]
) -> dict[str, Any]:
    merged = dict(current)
    for key, value in incoming.items():
        if value is None:
            continue
        existing = merged.get(key)
        if existing in (None, "", [], {}):
            merged[key] = value
    return merged


def _merge_missing_evidence(
    existing: list[dict[str, Any]],
    supplemental: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    merged = [dict(item) for item in existing]
    indexed = {_evidence_identity(item): index for index, item in enumerate(merged)}
    for item in supplemental:
        key = _evidence_identity(item)
        existing_index = indexed.get(key)
        if existing_index is None:
            indexed[key] = len(merged)
            merged.append(dict(item))
            continue
        merged[existing_index] = _merge_evidence_item(merged[existing_index], item)
    return merged


def _supplement_evidence_from_tool_calls(
    evidence: list[dict[str, Any]],
    tool_calls: Any,
) -> list[dict[str, Any]]:
    if not isinstance(tool_calls, list) or not tool_calls:
        return evidence
    supplemental = [
        item
        for index, raw_call in enumerate(tool_calls)
        if isinstance(raw_call, dict)
        for item in [_build_tool_evidence_from_tool_call(raw_call, index)]
        if item is not None
    ]
    if not supplemental:
        return evidence
    return _merge_missing_evidence(evidence, supplemental)


def _ensure_timeline_refs(
    timeline: list[dict[str, Any]],
    *,
    evidence: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not timeline or not evidence:
        return timeline
    tool_call_ids = [
        tool_call_id
        for tool_call_id in (
            _to_non_empty_str(item.get("tool_call_id"))
            for item in evidence
            if _map_source_kind(item.get("kind")) == "tool"
        )
        if tool_call_id
    ]
    source_refs = [
        evidence_id
        for evidence_id in (
            _to_non_empty_str(item.get("id"))
            for item in evidence
            if _map_source_kind(item.get("kind")) != "tool"
        )
        if evidence_id
    ]
    stabilized: list[dict[str, Any]] = []
    for stage in timeline:
        next_stage = dict(stage)
        if (
            next_stage.get("type") == "tool_execution"
            and not _normalize_string_list(next_stage.get("tool_call_ids"))
            and tool_call_ids
        ):
            next_stage["tool_call_ids"] = list(tool_call_ids)
        if (
            next_stage.get("type") == "retrieval"
            and not _normalize_string_list(next_stage.get("source_refs"))
            and source_refs
        ):
            next_stage["source_refs"] = list(source_refs)
        stabilized.append(next_stage)
    return stabilized


def _normalize_evidence(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    normalized: list[dict[str, Any]] = []
    for item in value:
        payload = _normalize_evidence_item(item)
        if payload is not None:
            normalized.append(payload)
    return normalized


def _normalize_answer_card(
    raw_answer_card: Any,
    *,
    fallback_summary: str | None,
    fallback_source_chip_ids: list[str],
) -> dict[str, Any]:
    raw = dict(raw_answer_card or {}) if isinstance(raw_answer_card, dict) else {}
    sections = raw.get("sections")
    normalized_sections: list[dict[str, Any]] = []
    if isinstance(sections, list):
        for item in sections:
            if not isinstance(item, dict):
                continue
            normalized_sections.append(
                {
                    "title": _to_non_empty_str(item.get("title")),
                    "content": _to_non_empty_str(item.get("content")),
                }
            )
    valid_source_chip_ids = set(fallback_source_chip_ids)
    raw_source_chip_ids = [
        item
        for item in _normalize_string_list(raw.get("source_chip_ids"))
        if item in valid_source_chip_ids
    ]
    return {
        "summary": _to_non_empty_str(raw.get("summary")) or fallback_summary,
        "sections": normalized_sections,
        "source_chip_ids": raw_source_chip_ids or fallback_source_chip_ids,
        "confidence_label": _to_non_empty_str(raw.get("confidence_label")),
        "follow_up_suggestions": _normalize_string_list(
            raw.get("follow_up_suggestions")
        ),
    }


def _sanitize_timeline_evidence_refs(
    timeline: list[dict[str, Any]],
    *,
    evidence: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not timeline:
        return timeline
    valid_evidence_ids = {
        evidence_id
        for evidence_id in (_to_non_empty_str(item.get("id")) for item in evidence)
        if evidence_id
    }
    retrieval_evidence_ids = {
        item_id
        for item in evidence
        for item_id in [_to_non_empty_str(item.get("id"))]
        if item_id and _map_source_kind(item.get("kind")) != "tool"
    }
    sanitized: list[dict[str, Any]] = []
    for item in timeline:
        stage = dict(item)
        stage_refs = [
            source_ref
            for source_ref in _normalize_string_list(stage.get("source_refs"))
            if source_ref in valid_evidence_ids
        ]
        if stage.get("type") == "retrieval":
            retrieval_refs = [
                source_ref
                for source_ref in stage_refs
                if source_ref in retrieval_evidence_ids
            ]
            if not retrieval_refs and retrieval_evidence_ids:
                retrieval_refs = list(retrieval_evidence_ids)
            metrics = dict(stage.get("metrics") or {})
            metrics["source_count"] = len(retrieval_refs)
            metrics["evidence_count"] = len(retrieval_refs)
            stage["metrics"] = metrics
            stage["source_refs"] = retrieval_refs
            if not retrieval_refs:
                summary = "整理了 0 条证据"
                stage["status"] = "skipped"
                stage["summary"] = summary
                stage["detail_lines"] = [summary]
            elif stage.get("status") == "skipped":
                stage["status"] = "completed"
            sanitized.append(stage)
            continue
        if "source_refs" in stage:
            stage["source_refs"] = stage_refs
        sanitized.append(stage)
    return _normalize_timeline(sanitized)


def _resolve_canonical_turn_flow_payload(
    raw_turn_flow: Any,
    *,
    metadata: dict[str, Any] | None,
) -> dict[str, Any] | None:
    metadata_payload = dict(metadata) if isinstance(metadata, dict) else {}
    turn_record = ConversationDiagnosticsProjector.normalize_turn_record_payload(
        metadata_payload.get("turn_record")
    )
    turn_record_payload = (
        dict(turn_record or {}) if isinstance(turn_record, dict) else {}
    )
    turn_record_metadata = (
        dict(turn_record_payload.get("metadata") or {})
        if isinstance(turn_record_payload.get("metadata"), dict)
        else {}
    )
    turn_record_diagnostics = (
        dict(turn_record_metadata.get("turn_diagnostics") or {})
        if isinstance(turn_record_metadata.get("turn_diagnostics"), dict)
        else {}
    )

    for candidate in (
        turn_record_payload.get("turn_flow"),
        turn_record_metadata.get("turn_flow"),
        turn_record_diagnostics.get("turn_flow"),
        raw_turn_flow,
        metadata_payload.get("turn_flow"),
    ):
        if isinstance(candidate, dict):
            return dict(candidate)
    return None


class ConversationTurnFlowProjector:
    """Build and normalize the stable `turn_flow` read-model contract."""

    @classmethod
    def normalize_turn_flow(
        cls,
        raw: Any,
        *,
        turn_outcome: str | None = None,
        completion_reason: str | None = None,
        interrupted: bool | None = None,
        failure_kind: str | None = None,
        final_output_source: str | None = None,
        metadata: dict[str, Any] | None = None,
        content: Any = None,
        tool_calls: Any = None,
    ) -> dict[str, Any] | None:
        raw_payload = _resolve_canonical_turn_flow_payload(raw, metadata=metadata)
        if raw_payload is None:
            return None
        metadata_payload = dict(metadata) if isinstance(metadata, dict) else {}
        resolved_tool_calls = _resolve_tool_calls(tool_calls)
        diagnostics = (
            ConversationDiagnosticsProjector.extract_turn_diagnostics_from_metadata(
                metadata_payload
            )
            if metadata_payload
            else {}
        )
        completed_tool_names = derive_completed_tool_names(
            diagnostics.get("intent_plan")
        )
        selected_tools = _normalize_string_list(diagnostics.get("selected_tool_names"))
        if not selected_tools:
            selected_tools = list(completed_tool_names)
        text_content = _to_non_empty_str(content)
        evidence = _normalize_evidence(raw_payload.get("evidence"))
        evidence = _supplement_evidence_from_tool_calls(evidence, resolved_tool_calls)
        source_refs = [item["id"] for item in evidence]
        effective_completion_reason = _to_non_empty_str(
            completion_reason or raw_payload.get("completion_reason")
        )
        effective_failure_kind = _normalize_failure_kind(
            failure_kind or raw_payload.get("failure_kind")
        )
        effective_final_output_source = _to_non_empty_str(
            final_output_source or raw_payload.get("final_output_source")
        )
        effective_interrupted = bool(raw_payload.get("interrupted"))
        if interrupted is not None:
            effective_interrupted = bool(interrupted) or effective_interrupted
        terminal_status = _derive_terminal_status(
            turn_outcome=_to_non_empty_str(turn_outcome),
            completion_reason=effective_completion_reason,
            interrupted=effective_interrupted,
            failure_kind=effective_failure_kind,
            final_output_source=effective_final_output_source,
        )
        timeline = _apply_terminal_stage_semantics(
            _normalize_timeline(raw_payload.get("timeline")),
            terminal_status=terminal_status,
            completion_reason=effective_completion_reason,
            source_refs=source_refs,
        )
        timeline = _ensure_timeline_refs(timeline, evidence=evidence)
        timeline = _sanitize_timeline_evidence_refs(timeline, evidence=evidence)
        timeline = _stabilize_timeline_statuses(
            timeline,
            selected_tools=selected_tools,
            completed_tool_names=completed_tool_names,
        )
        safe_untrusted_fallback_output = _has_safe_untrusted_fallback_output(
            raw_payload,
            metadata_payload,
        )
        failure_text_content = _resolve_failure_text_content_fallback(
            text_content=text_content,
            terminal_status=terminal_status,
            failure_kind=effective_failure_kind,
            final_output_source=effective_final_output_source,
            safe_untrusted_fallback_output=safe_untrusted_fallback_output,
        )
        error_context = dict(raw_payload)
        if metadata_payload:
            error_context.update(metadata_payload)
        error_surface = _ensure_error_surface(
            error_surface=_derive_error_surface(raw_payload),
            metadata=error_context,
            terminal_status=terminal_status,
            completion_reason=effective_completion_reason,
            failure_kind=effective_failure_kind,
            final_output_source=effective_final_output_source,
        )
        failure_answer_summary = (
            failure_text_content or _specific_error_surface_message(error_surface)
        )
        answer_card = _normalize_answer_card(
            raw_payload.get("answer_card"),
            fallback_summary=_to_non_empty_str(raw_payload.get("summary"))
            or failure_answer_summary,
            fallback_source_chip_ids=[item["id"] for item in evidence],
        )
        if terminal_status in {"error", "interrupted"}:
            answer_card = _apply_failure_answer_summary_fallback(
                answer_card,
                fallback_summary=failure_answer_summary,
            )
        return {
            "timeline": timeline,
            "evidence": evidence,
            "answer_card": answer_card,
            "completion_reason": effective_completion_reason,
            "interrupted": effective_interrupted,
            "error_surface": error_surface,
        }

    @classmethod
    def project_from_message_payload(
        cls,
        message: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        if not isinstance(message, dict):
            return None
        if str(message.get("role") or "") != "assistant":
            return None
        metadata = message.get("metadata")
        metadata_payload = dict(metadata) if isinstance(metadata, dict) else {}
        return cls.project_from_metadata(
            metadata_payload,
            content=message.get("content"),
            tool_calls=message.get("tool_calls"),
            token_count=message.get("token_count"),
        )

    @classmethod
    def project_from_metadata(
        cls,
        metadata: dict[str, Any] | None,
        *,
        content: Any = None,
        tool_calls: Any = None,
        token_count: Any = None,
    ) -> dict[str, Any]:
        payload = dict(metadata or {})
        turn_meta = (
            ConversationDiagnosticsProjector.extract_turn_diagnostics_from_metadata(
                payload
            )
        )
        turn_outcome = _to_non_empty_str(turn_meta.get("turn_outcome"))
        completion_reason = _to_non_empty_str(
            payload.get("completion_reason") or turn_meta.get("termination_reason")
        )
        interrupted = (
            bool(payload.get("interrupted")) or completion_reason == "interrupted"
        )
        failure_kind = _normalize_failure_kind(turn_meta.get("failure_kind"))
        final_output_source = _to_non_empty_str(turn_meta.get("final_output_source"))
        terminal_status = _derive_terminal_status(
            turn_outcome=turn_outcome,
            completion_reason=completion_reason,
            interrupted=interrupted,
            failure_kind=failure_kind,
            final_output_source=final_output_source,
        )
        existing = cls.normalize_turn_flow(
            payload.get("turn_flow"),
            turn_outcome=turn_outcome,
            completion_reason=completion_reason,
            interrupted=interrupted,
            failure_kind=failure_kind,
            final_output_source=final_output_source,
            metadata=payload,
            content=content,
            tool_calls=tool_calls,
        )
        if existing:
            return existing
        error_surface = _ensure_error_surface(
            error_surface=_derive_error_surface(payload),
            metadata=payload,
            terminal_status=terminal_status,
            completion_reason=completion_reason,
            failure_kind=failure_kind,
            final_output_source=final_output_source,
        )

        normalized_tool_calls = [
            dict(item)
            for item in _resolve_tool_calls(tool_calls)
            if isinstance(item, dict)
        ]
        text_content = _to_non_empty_str(content)
        completed_tool_names = derive_completed_tool_names(turn_meta.get("intent_plan"))
        selected_tools = _normalize_string_list(turn_meta.get("selected_tool_names"))
        if not selected_tools:
            selected_tools = list(completed_tool_names)
        candidate_tools = _normalize_string_list(turn_meta.get("candidate_tool_names"))
        unfinished_intents = _normalize_string_list(turn_meta.get("unfinished_intents"))
        context_sources = [
            dict(item)
            for item in (turn_meta.get("context_sources") or [])
            if isinstance(item, dict)
        ]
        del context_sources
        canonical_evidence: list[dict[str, Any]] = []
        legacy_projection_allowed = not canonical_evidence and not normalized_tool_calls
        legacy_tool_calls = (
            _resolve_legacy_tool_calls(payload) if legacy_projection_allowed else []
        )
        if not normalized_tool_calls and legacy_projection_allowed:
            normalized_tool_calls = [dict(item) for item in legacy_tool_calls]
        rag_sources = payload.get("rag_sources") if legacy_projection_allowed else None
        rag_items = (
            [dict(item) for item in rag_sources if isinstance(item, dict)]
            if isinstance(rag_sources, list)
            else []
        )

        evidence: list[dict[str, Any]] = [dict(item) for item in canonical_evidence]
        for idx, source in enumerate(rag_items):
            evidence.append(_build_legacy_rag_evidence(source, idx))

        for idx, call in enumerate(normalized_tool_calls):
            item = _build_tool_evidence_from_tool_call(call, idx)
            if item is not None:
                evidence.append(item)

        timeline: list[dict[str, Any]] = []
        thinking_content = (
            _to_non_empty_str(payload.get("thinking_content"))
            if legacy_projection_allowed
            and not turn_meta.get("intent_plan")
            and not turn_meta.get("tool_planner")
            else None
        )
        thinking_summary = _summarize_thinking_content(thinking_content)
        if (
            thinking_content
            or turn_meta.get("intent_plan")
            or turn_meta.get("tool_planner")
        ):
            timeline.append(
                {
                    "id": "thinking",
                    "type": "thinking",
                    "status": "completed",
                    "title": "已思考",
                    "summary": thinking_summary or _PUBLIC_THINKING_STAGE_SUMMARY,
                    "detail_lines": [],
                    "started_at_ms": None,
                    "ended_at_ms": None,
                    "duration_ms": None,
                    "metrics": {},
                    "tool_call_ids": [],
                    "source_refs": [],
                }
            )

        if candidate_tools or selected_tools or turn_meta.get("tool_planner"):
            tool_total_count, selected_count = _resolve_tool_selection_counts(
                candidate_tools,
                selected_tools,
            )
            tool_selection_summary = (
                f"已从 {tool_total_count} 个工具中筛选 {selected_count} 个"
            )
            timeline.append(
                {
                    "id": "tool_selection",
                    "type": "tool_selection",
                    "status": "completed" if selected_tools else "skipped",
                    "title": "工具筛选",
                    "summary": tool_selection_summary,
                    "detail_lines": [tool_selection_summary],
                    "started_at_ms": None,
                    "ended_at_ms": None,
                    "duration_ms": None,
                    "metrics": {
                        "candidate_count": tool_total_count,
                        "selected_count": selected_count,
                    },
                    "tool_call_ids": [],
                    "source_refs": [],
                }
            )

        if normalized_tool_calls or selected_tools or unfinished_intents:
            tool_call_ids = [
                _to_non_empty_str(call.get("id"))
                for call in normalized_tool_calls
                if _to_non_empty_str(call.get("id"))
            ]
            if normalized_tool_calls:
                tool_execution_status = "completed"
                tool_execution_summary = (
                    f"执行了 {len(normalized_tool_calls)} 个工具调用"
                )
            elif completed_tool_names:
                tool_execution_status = "completed"
                tool_execution_summary = (
                    f"执行了 {len(completed_tool_names)} 个工具调用"
                )
            elif terminal_status == "error" and (selected_tools or unfinished_intents):
                tool_execution_status = "error"
                tool_execution_summary = "工具已进入执行阶段，但未等到返回结果"
            elif terminal_status == "interrupted" and (
                selected_tools or unfinished_intents
            ):
                tool_execution_status = "interrupted"
                tool_execution_summary = "工具执行在返回结果前被中断"
            else:
                tool_execution_status = "skipped" if selected_tools else "completed"
                tool_execution_summary = (
                    f"执行了 {len(normalized_tool_calls)} 个工具调用"
                )
            timeline.append(
                {
                    "id": "tool_execution",
                    "type": "tool_execution",
                    "status": tool_execution_status,
                    "title": "工具执行",
                    "summary": tool_execution_summary,
                    "detail_lines": [tool_execution_summary],
                    "started_at_ms": None,
                    "ended_at_ms": None,
                    "duration_ms": None,
                    "metrics": {
                        "tool_call_count": len(normalized_tool_calls),
                    },
                    "tool_call_ids": tool_call_ids,
                    "source_refs": [],
                }
            )

        retrieval_evidence = [
            item for item in evidence if _map_source_kind(item.get("kind")) != "tool"
        ]
        has_retrieval_signal = bool(rag_items or retrieval_evidence)
        if has_retrieval_signal:
            retrieval_summary = _summarize_retrieval_progress(
                evidence_count=len(retrieval_evidence),
                terminal_status=terminal_status,
            )
            retrieval_status = "completed" if retrieval_evidence else "skipped"
            timeline.append(
                {
                    "id": "retrieval",
                    "type": "retrieval",
                    "status": retrieval_status,
                    "title": "检索与取证",
                    "summary": retrieval_summary,
                    "detail_lines": [retrieval_summary],
                    "started_at_ms": None,
                    "ended_at_ms": None,
                    "duration_ms": None,
                    "metrics": {
                        "evidence_count": len(retrieval_evidence),
                        "source_count": len(retrieval_evidence),
                    },
                    "tool_call_ids": [],
                    "source_refs": [item["id"] for item in retrieval_evidence],
                }
            )

        if (
            text_content
            or payload.get("answer_card")
            or terminal_status in {"error", "interrupted"}
        ):
            timeline.append(
                {
                    "id": "answer_assembly",
                    "type": "answer_assembly",
                    "status": terminal_status,
                    "title": "答案生成",
                    "summary": (
                        "已生成最终答复"
                        if terminal_status == "completed"
                        else (
                            "答复生成中断"
                            if terminal_status == "interrupted"
                            else "答复生成失败"
                        )
                    ),
                    "detail_lines": [],
                    "started_at_ms": None,
                    "ended_at_ms": None,
                    "duration_ms": None,
                    "metrics": {
                        "token_count": _normalize_optional_int(token_count),
                        "content_chars": len(text_content or ""),
                    },
                    "tool_call_ids": [],
                    "source_refs": [item["id"] for item in evidence],
                }
            )

        timeline.append(
            {
                "id": "terminal",
                "type": (
                    "failed"
                    if terminal_status in {"error", "interrupted"}
                    else "completed"
                ),
                "status": terminal_status,
                "title": (
                    "本轮失败"
                    if terminal_status == "error"
                    else (
                        "本轮中断" if terminal_status == "interrupted" else "本轮结束"
                    )
                ),
                "summary": completion_reason
                or (
                    "completed"
                    if terminal_status == "completed"
                    else (
                        "interrupted" if terminal_status == "interrupted" else "error"
                    )
                ),
                "detail_lines": [],
                "started_at_ms": None,
                "ended_at_ms": None,
                "duration_ms": None,
                "metrics": {},
                "tool_call_ids": [],
                "source_refs": [item["id"] for item in evidence],
            }
        )

        safe_untrusted_fallback_output = _has_safe_untrusted_fallback_output(
            payload,
            turn_meta,
        )
        failure_text_content = _resolve_failure_text_content_fallback(
            text_content=text_content,
            terminal_status=terminal_status,
            failure_kind=failure_kind,
            final_output_source=final_output_source,
            safe_untrusted_fallback_output=safe_untrusted_fallback_output,
        )
        failure_answer_summary = (
            failure_text_content or _specific_error_surface_message(error_surface)
        )
        answer_card = _normalize_answer_card(
            payload.get("answer_card"),
            fallback_summary=failure_answer_summary,
            fallback_source_chip_ids=[item["id"] for item in evidence],
        )
        if terminal_status in {"error", "interrupted"}:
            answer_card = _apply_failure_answer_summary_fallback(
                answer_card,
                fallback_summary=failure_answer_summary,
            )
        return {
            "timeline": _apply_terminal_stage_semantics(
                _normalize_timeline(timeline),
                terminal_status=terminal_status,
                completion_reason=completion_reason,
                source_refs=[item["id"] for item in evidence],
            ),
            "evidence": _normalize_evidence(evidence),
            "answer_card": answer_card,
            "completion_reason": completion_reason,
            "interrupted": interrupted,
            "error_surface": error_surface,
        }

    @classmethod
    def build_error_only_turn_flow(
        cls,
        *,
        conversation_last_error: dict[str, Any] | None,
    ) -> dict[str, Any]:
        last_error = dict(conversation_last_error or {})
        completion_reason = "stream_execution_error" if last_error else None
        error_type = _to_non_empty_str(last_error.get("error_type"))
        interrupted = bool(last_error.get("partial"))
        timeline = [
            {
                "id": "answer_assembly",
                "type": "answer_assembly",
                "status": "error" if last_error else "skipped",
                "title": "答案生成",
                "summary": "答复生成失败" if last_error else "无答复内容",
                "detail_lines": [],
                "started_at_ms": None,
                "ended_at_ms": None,
                "duration_ms": None,
                "metrics": {},
                "tool_call_ids": [],
                "source_refs": [],
            },
            {
                "id": "terminal",
                "type": "failed" if last_error else "completed",
                "status": "error" if last_error else "completed",
                "title": "本轮失败" if last_error else "本轮结束",
                "summary": completion_reason,
                "detail_lines": [],
                "started_at_ms": None,
                "ended_at_ms": None,
                "duration_ms": None,
                "metrics": {},
                "tool_call_ids": [],
                "source_refs": [],
            },
        ]
        return {
            "timeline": _normalize_timeline(timeline),
            "evidence": [],
            "answer_card": _normalize_answer_card(
                {},
                fallback_summary=_to_public_error_str(
                    last_error.get("friendly_message")
                ),
                fallback_source_chip_ids=[],
            ),
            "completion_reason": completion_reason,
            "interrupted": interrupted,
            "error_surface": (
                {
                    "message": _to_public_error_str(last_error.get("friendly_message")),
                    "error_type": error_type,
                    "trace_id": _to_non_empty_str(last_error.get("trace_id")),
                    "debug_message": _to_public_error_str(
                        last_error.get("debug_message")
                    ),
                }
                if last_error
                else None
            ),
        }


__all__ = ["ConversationTurnFlowProjector"]
