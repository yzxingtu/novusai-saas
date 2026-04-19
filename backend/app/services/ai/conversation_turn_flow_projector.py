"""Turn-flow read-model projection helpers for assistant messages."""

from __future__ import annotations

from typing import Any

from app.services.ai.conversation_diagnostics_projector import (
    ConversationDiagnosticsProjector,
)
from app.services.ai.turn_failure_normalizer import (
    derive_completed_tool_names,
    has_incomplete_promissory_page_reply,
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

_DEFAULT_ERROR_SURFACE_MESSAGE = (
    "The request ended before a final answer was produced."
)
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
_HOSTED_SEARCH_PROGRESS_KINDS = frozenset(
    {"web_search_in_progress", "provider_search_in_progress", "search_in_progress"}
)
_HOSTED_SEARCH_TOOL_NAMES = frozenset({"web_search", "fetch_url"})
_HOSTED_SEARCH_INTENT_MARKERS = (
    "web_research",
    "web-search",
    "web search",
    "search",
    "research",
    "联网",
    "检索",
)


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
    return [str(item).strip() for item in value if str(item).strip()]


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


def _extract_progress_kinds(payload: dict[str, Any], turn_meta: dict[str, Any]) -> set[str]:
    kinds = {
        kind
        for kind in (
            _to_non_empty_str(event.get("kind"))
            for event in _normalize_provider_events(turn_meta.get("provider_events"))
        )
        if kind
    }
    turn_record = payload.get("turn_record")
    turn_record_payload = dict(turn_record) if isinstance(turn_record, dict) else {}
    turn_record_metadata = turn_record_payload.get("metadata")
    turn_record_metadata_payload = (
        dict(turn_record_metadata) if isinstance(turn_record_metadata, dict) else {}
    )
    for raw_kind in turn_record_metadata_payload.get("stream_progress_kinds") or []:
        kind = _to_non_empty_str(raw_kind)
        if kind:
            kinds.add(kind)
    if bool(turn_record_metadata_payload.get("web_search_in_progress")):
        kinds.add("web_search_in_progress")
    return kinds


def _resolve_tool_selection_counts(
    candidate_tools: list[str],
    selected_tools: list[str],
) -> tuple[int, int]:
    selected_count = len(selected_tools)
    candidate_count = len(candidate_tools) or selected_count
    return max(candidate_count, selected_count), selected_count


def _summarize_hosted_search_progress(terminal_status: str) -> str:
    if terminal_status == "error":
        return "联网搜索在等待结果返回时超时"
    if terminal_status == "interrupted":
        return "联网搜索在等待结果返回时被中断"
    if terminal_status == "completed":
        return "已发起联网搜索并等待提供商返回结果"
    return "正在联网搜索并等待结果返回"


def _summarize_retrieval_progress(
    *,
    evidence_count: int,
    has_hosted_search_progress: bool,
    terminal_status: str,
) -> str:
    if evidence_count > 0:
        return f"整理了 {evidence_count} 条证据"
    if has_hosted_search_progress:
        if terminal_status == "error":
            return "搜索未返回可展示证据"
        if terminal_status == "interrupted":
            return "搜索在返回证据前被中断"
        return "正在等待搜索证据返回"
    return "整理了 0 条证据"


def _normalize_identifier_tokens(values: list[str]) -> set[str]:
    normalized: set[str] = set()
    for item in values:
        token = _to_non_empty_str(item)
        if token:
            normalized.add(token.lower())
    return normalized


def _looks_like_hosted_search_intent(turn_meta: dict[str, Any]) -> bool:
    planner = (
        dict(turn_meta.get("tool_planner") or {})
        if isinstance(turn_meta.get("tool_planner"), dict)
        else {}
    )
    tokens = [
        _to_non_empty_str(planner.get("family")),
        _to_non_empty_str(planner.get("intent")),
        _to_non_empty_str(turn_meta.get("continuation_source")),
    ]
    for token in tokens:
        lowered = str(token or "").strip().lower()
        if lowered and any(marker in lowered for marker in _HOSTED_SEARCH_INTENT_MARKERS):
            return True
    return False


def _derive_error_surface(metadata: dict[str, Any]) -> dict[str, Any] | None:
    raw = metadata.get("error_surface")
    if isinstance(raw, dict):
        payload = {
            "message": _to_non_empty_str(raw.get("message")),
            "error_type": _to_non_empty_str(raw.get("error_type")),
            "trace_id": _to_non_empty_str(raw.get("trace_id")),
            "debug_message": _to_non_empty_str(raw.get("debug_message")),
        }
        if any(payload.values()):
            return payload

    payload = {
        "message": _to_non_empty_str(
            metadata.get("error_message")
            or metadata.get("friendly_message")
            or metadata.get("public_error_message")
        ),
        "error_type": _to_non_empty_str(metadata.get("error_type")),
        "trace_id": _to_non_empty_str(
            metadata.get("error_trace_id") or metadata.get("trace_id")
        ),
        "debug_message": _to_non_empty_str(metadata.get("error_debug_message")),
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
        (idx for idx, stage in enumerate(timeline) if stage.get("type") == "answer_assembly"),
        None,
    )
    answer_summary = (
        "答复生成失败" if status == "error" else "答复生成中断"
    )
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
    message = _to_non_empty_str(payload.get("message")) or _to_non_empty_str(
        metadata.get("error_message")
        or metadata.get("friendly_message")
        or metadata.get("public_error_message")
    )
    if not message:
        message = _DEFAULT_ERROR_SURFACE_MESSAGE
    error_type = _to_non_empty_str(payload.get("error_type")) or _normalize_failure_kind(
        failure_kind
    )
    if not error_type and final_output_source and not _is_trusted_final_output_source(
        final_output_source
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
    debug_message = _to_non_empty_str(payload.get("debug_message")) or _to_non_empty_str(
        metadata.get("error_debug_message")
    )
    return {
        "message": message,
        "error_type": error_type,
        "trace_id": trace_id,
        "debug_message": debug_message,
    }


def _map_source_kind(raw_kind: Any) -> str:
    kind = str(raw_kind or "").strip().lower()
    if kind in {"web", "web_search"}:
        return "web"
    if kind in {"knowledge", "knowledge_base", "kb", "formal_kb"}:
        return "knowledge_base"
    if kind in {"page", "page_read", "page_write", "page_runtime"}:
        return "page"
    if kind in {"memory", "long_term_memory", "session_memory"}:
        return "memory"
    if kind in {"tool", "tool_call"}:
        return "tool"
    return "knowledge_base"


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
        final_output_source
        and not _is_trusted_final_output_source(final_output_source)
    )


def _resolve_failure_text_content_fallback(
    *,
    text_content: str | None,
    terminal_status: str,
    failure_kind: str | None,
    final_output_source: str | None,
) -> str | None:
    if terminal_status not in {"error", "interrupted"}:
        return text_content
    if _is_untrusted_final_output_failure(
        failure_kind=failure_kind,
        final_output_source=final_output_source,
    ):
        return None
    return text_content


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

        if (
            (stage_type == "thinking" and stage_status == "error")
            or (
                stage_type == "tool_selection"
                and selected_tools
                and stage_status == "skipped"
            )
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
    return {
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
    return {
        "summary": _to_non_empty_str(raw.get("summary")) or fallback_summary,
        "sections": normalized_sections,
        "source_chip_ids": _normalize_string_list(raw.get("source_chip_ids"))
        or fallback_source_chip_ids,
        "confidence_label": _to_non_empty_str(raw.get("confidence_label")),
        "follow_up_suggestions": _normalize_string_list(
            raw.get("follow_up_suggestions")
        ),
    }


def _resolve_canonical_turn_flow_payload(
    raw_turn_flow: Any,
    *,
    metadata: dict[str, Any] | None,
) -> dict[str, Any] | None:
    metadata_payload = dict(metadata) if isinstance(metadata, dict) else {}
    turn_record = ConversationDiagnosticsProjector.normalize_turn_record_payload(
        metadata_payload.get("turn_record")
    )
    turn_record_payload = dict(turn_record or {}) if isinstance(turn_record, dict) else {}
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
    ) -> dict[str, Any] | None:
        raw_payload = _resolve_canonical_turn_flow_payload(raw, metadata=metadata)
        if raw_payload is None:
            return None
        metadata_payload = dict(metadata) if isinstance(metadata, dict) else {}
        diagnostics = (
            ConversationDiagnosticsProjector.extract_turn_diagnostics_from_metadata(
                metadata_payload
            )
            if metadata_payload
            else {}
        )
        completed_tool_names = derive_completed_tool_names(diagnostics.get("intent_plan"))
        selected_tools = _normalize_string_list(diagnostics.get("selected_tool_names"))
        if not selected_tools:
            selected_tools = list(completed_tool_names)
        text_content = _to_non_empty_str(content)
        evidence = _normalize_evidence(raw_payload.get("evidence"))
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
        if has_incomplete_promissory_page_reply(
            diagnostics=diagnostics,
            content=content,
        ):
            effective_failure_kind = (
                effective_failure_kind or "incomplete_promissory_reply"
            )
            if effective_completion_reason in {None, "completed", "stop"}:
                effective_completion_reason = "incomplete_promissory_reply"
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
        timeline = _stabilize_timeline_statuses(
            timeline,
            selected_tools=selected_tools,
            completed_tool_names=completed_tool_names,
        )
        failure_text_content = _resolve_failure_text_content_fallback(
            text_content=text_content,
            terminal_status=terminal_status,
            failure_kind=effective_failure_kind,
            final_output_source=effective_final_output_source,
        )
        answer_card = _normalize_answer_card(
            raw_payload.get("answer_card"),
            fallback_summary=_to_non_empty_str(raw_payload.get("summary"))
            or failure_text_content,
            fallback_source_chip_ids=[item["id"] for item in evidence],
        )
        if (
            failure_text_content
            and terminal_status in {"error", "interrupted"}
            and _looks_like_missing_final_answer_summary(answer_card.get("summary"))
        ):
            answer_card["summary"] = failure_text_content
            sections = answer_card.get("sections")
            if isinstance(sections, list) and sections:
                normalized_sections: list[dict[str, Any]] = []
                for index, item in enumerate(sections):
                    section = dict(item) if isinstance(item, dict) else {}
                    if index == 0:
                        section["content"] = failure_text_content
                    normalized_sections.append(section)
                answer_card["sections"] = normalized_sections
            else:
                answer_card["sections"] = [
                    {
                        "title": "Answer",
                        "content": failure_text_content,
                    }
                ]
            answer_card["confidence_label"] = "low"
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
        turn_meta = ConversationDiagnosticsProjector.extract_turn_diagnostics_from_metadata(
            payload
        )
        turn_outcome = _to_non_empty_str(turn_meta.get("turn_outcome"))
        completion_reason = _to_non_empty_str(
            payload.get("completion_reason") or turn_meta.get("termination_reason")
        )
        interrupted = bool(payload.get("interrupted")) or completion_reason == "interrupted"
        failure_kind = _normalize_failure_kind(turn_meta.get("failure_kind"))
        final_output_source = _to_non_empty_str(turn_meta.get("final_output_source"))
        if has_incomplete_promissory_page_reply(
            diagnostics=turn_meta,
            content=content,
        ):
            failure_kind = failure_kind or "incomplete_promissory_reply"
            if completion_reason in {None, "completed", "stop"}:
                completion_reason = "incomplete_promissory_reply"
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
            dict(item) for item in (tool_calls or []) if isinstance(item, dict)
        ]
        text_content = _to_non_empty_str(content)
        completed_tool_names = derive_completed_tool_names(turn_meta.get("intent_plan"))
        selected_tools = _normalize_string_list(turn_meta.get("selected_tool_names"))
        if not selected_tools:
            selected_tools = list(completed_tool_names)
        candidate_tools = _normalize_string_list(turn_meta.get("candidate_tool_names"))
        progress_kinds = _extract_progress_kinds(payload, turn_meta)
        selected_tool_tokens = _normalize_identifier_tokens(selected_tools)
        candidate_tool_tokens = _normalize_identifier_tokens(candidate_tools)
        has_hosted_search_tool_signal = bool(
            _HOSTED_SEARCH_TOOL_NAMES & selected_tool_tokens
        )
        has_hosted_search_candidate_signal = bool(
            _HOSTED_SEARCH_TOOL_NAMES & candidate_tool_tokens
        )
        has_hosted_search_intent_signal = _looks_like_hosted_search_intent(turn_meta)
        has_hosted_search_progress = bool(
            _HOSTED_SEARCH_PROGRESS_KINDS
            & _normalize_identifier_tokens(list(progress_kinds))
        )
        if not has_hosted_search_progress and not normalized_tool_calls:
            has_hosted_search_progress = bool(
                has_hosted_search_tool_signal
                or (
                    has_hosted_search_candidate_signal
                    and (
                        has_hosted_search_intent_signal
                        or terminal_status in {"error", "interrupted"}
                    )
                )
            )
        unfinished_intents = _normalize_string_list(turn_meta.get("unfinished_intents"))
        rag_sources = payload.get("rag_sources")
        rag_items = [dict(item) for item in rag_sources if isinstance(item, dict)] if isinstance(rag_sources, list) else []
        context_sources = [
            dict(item) for item in (turn_meta.get("context_sources") or []) if isinstance(item, dict)
        ]

        evidence: list[dict[str, Any]] = []
        for idx, source in enumerate(rag_items):
            evidence.append(
                {
                    "id": f"ev_rag_{idx + 1}",
                    "kind": _map_source_kind(source.get("kind") or source.get("source_kind")),
                    "title": _to_non_empty_str(
                        source.get("title")
                        or source.get("source")
                        or source.get("name")
                        or source.get("chunk_id")
                    )
                    or f"Source {idx + 1}",
                    "url": _to_non_empty_str(source.get("url") or source.get("source_url")),
                    "snippet": _to_non_empty_str(source.get("snippet") or source.get("content")),
                    "badge": _to_non_empty_str(source.get("badge")),
                    "score": _normalize_optional_float(source.get("score")),
                    "tool_call_id": None,
                    "source_ref": _to_non_empty_str(source.get("source_ref") or source.get("chunk_id")),
                }
            )

        for idx, call in enumerate(normalized_tool_calls):
            call_id = _to_non_empty_str(call.get("id")) or f"tool_{idx + 1}"
            if not (
                call.get("result_link")
                or call.get("summary")
                or call.get("display_name")
                or call.get("name")
            ):
                continue
            evidence.append(
                {
                    "id": f"ev_tool_{call_id}",
                    "kind": "tool",
                    "title": _to_non_empty_str(
                        call.get("display_name") or call.get("name")
                    )
                    or f"Tool {idx + 1}",
                    "url": _to_non_empty_str(call.get("result_link")),
                    "snippet": _to_non_empty_str(call.get("summary")),
                    "badge": _to_non_empty_str(call.get("error_type")),
                    "score": None,
                    "tool_call_id": call_id,
                    "source_ref": call_id,
                }
            )

        timeline: list[dict[str, Any]] = []
        thinking_content = _to_non_empty_str(payload.get("thinking_content"))
        thinking_summary = _summarize_thinking_content(thinking_content)
        if thinking_content or turn_meta.get("intent_plan") or turn_meta.get("tool_planner"):
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

        if normalized_tool_calls or selected_tools or has_hosted_search_progress or unfinished_intents:
            tool_call_ids = [
                _to_non_empty_str(call.get("id"))
                for call in normalized_tool_calls
                if _to_non_empty_str(call.get("id"))
            ]
            if normalized_tool_calls:
                tool_execution_status = "completed"
                tool_execution_summary = f"执行了 {len(normalized_tool_calls)} 个工具调用"
            elif has_hosted_search_progress:
                tool_execution_status = (
                    terminal_status
                    if terminal_status in {"error", "interrupted"}
                    else ("running" if not text_content and not completion_reason else "completed")
                )
                tool_execution_summary = _summarize_hosted_search_progress(
                    tool_execution_status
                )
            elif completed_tool_names:
                tool_execution_status = "completed"
                tool_execution_summary = f"执行了 {len(completed_tool_names)} 个工具调用"
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
                tool_execution_summary = f"执行了 {len(normalized_tool_calls)} 个工具调用"
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

        has_retrieval_signal = bool(rag_items) or any(
            _map_source_kind(item.get("kind")) in {"web", "knowledge_base", "memory"}
            for item in context_sources
        )
        if has_retrieval_signal or has_hosted_search_progress:
            retrieval_summary = _summarize_retrieval_progress(
                evidence_count=len(evidence),
                has_hosted_search_progress=has_hosted_search_progress,
                terminal_status=terminal_status,
            )
            if evidence:
                retrieval_status = "completed"
            elif has_hosted_search_progress:
                retrieval_status = (
                    terminal_status
                    if terminal_status in {"error", "interrupted"}
                    else "running"
                )
            else:
                retrieval_status = "skipped"
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
                    "metrics": {"evidence_count": len(evidence)},
                    "tool_call_ids": [],
                    "source_refs": [item["id"] for item in evidence],
                }
            )

        if text_content or payload.get("answer_card") or terminal_status in {"error", "interrupted"}:
            timeline.append(
                {
                    "id": "answer_assembly",
                    "type": "answer_assembly",
                    "status": terminal_status,
                    "title": "答案生成",
                    "summary": (
                        "已生成最终答复"
                        if terminal_status == "completed"
                        else ("答复生成中断" if terminal_status == "interrupted" else "答复生成失败")
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
                    else ("本轮中断" if terminal_status == "interrupted" else "本轮结束")
                ),
                "summary": completion_reason
                or (
                    "completed"
                    if terminal_status == "completed"
                    else ("interrupted" if terminal_status == "interrupted" else "error")
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

        failure_text_content = _resolve_failure_text_content_fallback(
            text_content=text_content,
            terminal_status=terminal_status,
            failure_kind=failure_kind,
            final_output_source=final_output_source,
        )
        answer_card = _normalize_answer_card(
            payload.get("answer_card"),
            fallback_summary=failure_text_content,
            fallback_source_chip_ids=[item["id"] for item in evidence],
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
            }
        ]
        return {
            "timeline": _normalize_timeline(timeline),
            "evidence": [],
            "answer_card": _normalize_answer_card(
                {},
                fallback_summary=_to_non_empty_str(last_error.get("friendly_message")),
                fallback_source_chip_ids=[],
            ),
            "completion_reason": completion_reason,
            "interrupted": interrupted,
            "error_surface": (
                {
                    "message": _to_non_empty_str(last_error.get("friendly_message")),
                    "error_type": error_type,
                    "trace_id": _to_non_empty_str(last_error.get("trace_id")),
                    "debug_message": _to_non_empty_str(last_error.get("debug_message")),
                }
                if last_error
                else None
            ),
        }


__all__ = ["ConversationTurnFlowProjector"]
