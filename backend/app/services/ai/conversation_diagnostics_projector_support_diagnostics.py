"""Turn diagnostics extraction helpers for conversation diagnostics projector."""

from __future__ import annotations

from typing import Any

from app.ai.engine.recovery_web_research_gate import (
    project_canonical_web_research_diagnostics,
)
from app.ai.json_safe import normalize_json_safe_dict
from app.schemas.ai.invalid_ai_runtime_input import (
    DISALLOWED_AI_RUNTIME_INPUT_KEYS,
    DISALLOWED_AI_RUNTIME_INPUT_PREFIXES,
    DISALLOWED_AI_RUNTIME_INPUT_VALUES,
    is_invalid_ai_runtime_tool_family,
    is_invalid_ai_runtime_tool_name,
    normalize_ai_runtime_token,
)
from app.services.ai.turn_failure_normalizer import derive_budget_projection


def _normalize_turn_record_payload(turn_record: Any) -> dict[str, Any] | None:
    payload = normalize_json_safe_dict(turn_record)
    if not payload:
        return None
    return sanitize_diagnostics_payload(payload)


def _to_non_empty_str(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    if text.lower() in {"none", "null", "undefined"}:
        return None
    return text


_DIAGNOSTIC_NAME_LIST_KEYS = frozenset(
    {
        "allowed_tool_names",
        "candidate_tool_names",
        "completed_by_tool_names",
        "inventory_selected_skill_names",
        "inventory_selected_tool_names",
        "leaked_tool_names",
        "resolved_tool_names",
        "selected_skill_names",
        "selected_tool_names",
        "startup_preview_semantic_families",
        "startup_preview_tool_names",
        "tool_names",
    }
)
_DIAGNOSTIC_CONTEXT_SOURCE_KEYS = frozenset(
    {"context_sources", "sources", "runtime_context_sources"}
)
_DIAGNOSTIC_INTENT_PLAN_KEYS = frozenset({"intent_plan", "intents"})
_DIAGNOSTIC_RETRY_EVENT_KEYS = frozenset({"retry_events"})
_DIAGNOSTIC_SCALAR_REFERENCE_KEYS = frozenset(
    {
        "continuation_source",
        "family",
        "last_tool_name",
        "retry_family",
        "semantic_family",
    }
)


def is_invalid_runtime_diagnostics_reference(value: Any) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    token = normalize_ai_runtime_token(text)
    return (
        is_invalid_ai_runtime_tool_name(token)
        or is_invalid_ai_runtime_tool_family(token)
        or token in DISALLOWED_AI_RUNTIME_INPUT_KEYS
        or token in DISALLOWED_AI_RUNTIME_INPUT_VALUES
        or token.startswith(DISALLOWED_AI_RUNTIME_INPUT_PREFIXES)
    )


def normalize_live_diagnostics_reference(value: Any) -> str | None:
    text = _to_non_empty_str(value)
    if not text or is_invalid_runtime_diagnostics_reference(text):
        return None
    return text


def _normalize_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    normalized: list[str] = []
    for item in value:
        text = normalize_live_diagnostics_reference(item)
        if text and text not in normalized:
            normalized.append(text)
    return normalized


def _sanitize_list_payload(value: list[Any]) -> list[Any]:
    normalized: list[Any] = []
    for item in value:
        if isinstance(item, dict):
            payload = sanitize_diagnostics_payload(item)
            if payload:
                normalized.append(payload)
            continue
        if isinstance(item, list):
            payload = _sanitize_list_payload(item)
            if payload:
                normalized.append(payload)
            continue
        if isinstance(item, str):
            text = normalize_live_diagnostics_reference(item)
            if text:
                normalized.append(text)
            continue
        normalized.append(item)
    return normalized


def sanitize_diagnostics_payload(value: Any) -> dict[str, Any] | None:
    payload = _normalize_json_dict(value)
    if not payload:
        return None

    sanitized: dict[str, Any] = {}
    for raw_key, raw_value in payload.items():
        key = str(raw_key)
        if is_invalid_runtime_diagnostics_reference(key):
            continue

        if key in _DIAGNOSTIC_NAME_LIST_KEYS:
            if isinstance(raw_value, list):
                sanitized[key] = _normalize_string_list(raw_value)
            elif isinstance(raw_value, dict):
                nested = sanitize_diagnostics_payload(raw_value)
                if nested:
                    sanitized[key] = nested
            continue
        if key in _DIAGNOSTIC_CONTEXT_SOURCE_KEYS:
            sources = _normalize_context_sources(raw_value)
            if sources:
                sanitized[key] = sources
            continue
        if key in _DIAGNOSTIC_INTENT_PLAN_KEYS:
            intent_plan = _normalize_intent_plan(raw_value)
            if intent_plan:
                sanitized[key] = intent_plan
            continue
        if key in _DIAGNOSTIC_RETRY_EVENT_KEYS:
            retry_events = _normalize_retry_events(raw_value)
            if retry_events:
                sanitized[key] = retry_events
            continue
        if key == "tool_planner":
            tool_planner = _sanitize_tool_planner(raw_value)
            if tool_planner:
                sanitized[key] = tool_planner
            continue
        if key in _DIAGNOSTIC_SCALAR_REFERENCE_KEYS:
            text = normalize_live_diagnostics_reference(raw_value)
            if text:
                sanitized[key] = text
            continue

        if isinstance(raw_value, dict):
            nested = sanitize_diagnostics_payload(raw_value)
            if nested:
                sanitized[key] = nested
            continue
        if isinstance(raw_value, list):
            nested_list = _sanitize_list_payload(raw_value)
            sanitized[key] = nested_list
            continue
        if isinstance(raw_value, str) and is_invalid_runtime_diagnostics_reference(
            raw_value
        ):
            continue
        sanitized[key] = raw_value

    return sanitized


def _normalize_context_sources(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    normalized: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        source_name = _to_non_empty_str(item.get("name"))
        source_kind = _to_non_empty_str(item.get("kind"))
        if not source_name and not source_kind:
            continue
        if is_invalid_runtime_diagnostics_reference(
            source_name
        ) or is_invalid_runtime_diagnostics_reference(source_kind):
            continue
        metadata = sanitize_diagnostics_payload(item.get("metadata")) or {}
        normalized.append(
            {
                "kind": source_kind,
                "name": source_name,
                "active": bool(item.get("active", True)),
                "metadata": metadata,
            }
        )
    return normalized


def _normalize_optional_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _map_legacy_rag_kind(raw_kind: Any) -> str:
    kind = str(raw_kind or "").strip().lower()
    if kind in {"web", "web_search"}:
        return "web"
    if kind in {"memory", "long_term_memory", "session_memory"}:
        return "memory"
    if kind in {"tool", "tool_call"}:
        return "tool"
    return "knowledge_base"


def _build_legacy_rag_evidence(
    source: dict[str, Any],
    index: int,
) -> dict[str, Any]:
    source_ref = _to_non_empty_str(source.get("source_ref") or source.get("chunk_id"))
    return {
        "id": source_ref or f"ev_rag_{index + 1}",
        "kind": _map_legacy_rag_kind(source.get("kind") or source.get("source_kind")),
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
        "source_ref": source_ref,
    }


def _ensure_legacy_message_turn_flow(metadata: dict[str, Any]) -> None:
    if not isinstance(metadata, dict):
        return
    if isinstance(metadata.get("turn_flow"), dict):
        return
    if any(
        isinstance(metadata.get(key), dict)
        for key in (
            "turn_record",
            "turn_diagnostics",
        )
    ):
        return

    thinking_content = _to_non_empty_str(metadata.get("thinking_content"))
    rag_items = [
        dict(item)
        for item in (metadata.get("rag_sources") or [])
        if isinstance(item, dict)
    ]
    if not thinking_content and not rag_items:
        return

    evidence = [
        _build_legacy_rag_evidence(source, index)
        for index, source in enumerate(rag_items)
    ]
    timeline: list[dict[str, Any]] = []
    if thinking_content:
        timeline.append(
            {
                "id": "thinking",
                "type": "thinking",
                "status": "completed",
                "title": "已思考",
                "summary": "已完成思考与规划",
                "detail_lines": [],
                "started_at_ms": None,
                "ended_at_ms": None,
                "duration_ms": None,
                "metrics": {},
                "tool_call_ids": [],
                "source_refs": [],
            }
        )
    if evidence:
        source_refs = [item["id"] for item in evidence]
        retrieval_summary = f"整理了 {len(evidence)} 条证据"
        timeline.append(
            {
                "id": "retrieval",
                "type": "retrieval",
                "status": "completed",
                "title": "检索与取证",
                "summary": retrieval_summary,
                "detail_lines": [retrieval_summary],
                "started_at_ms": None,
                "ended_at_ms": None,
                "duration_ms": None,
                "metrics": {"evidence_count": len(evidence)},
                "tool_call_ids": [],
                "source_refs": source_refs,
            }
        )

    metadata["turn_flow"] = {
        "timeline": timeline,
        "evidence": evidence,
        "answer_card": {
            "summary": None,
            "sections": [],
            "source_chip_ids": [item["id"] for item in evidence],
        },
        "completion_reason": _to_non_empty_str(metadata.get("completion_reason")),
        "interrupted": bool(metadata.get("interrupted")),
        "error_surface": None,
    }


def _normalize_json_dict(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    return {
        str(key): value[key] for key in value if isinstance(key, str) or key is not None
    }


def _normalize_intent_plan(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    normalized: list[dict[str, Any]] = []
    for item in value:
        payload = _normalize_json_dict(item)
        if not payload:
            continue
        raw_kind = _to_non_empty_str(payload.get("kind"))
        raw_family = _to_non_empty_str(payload.get("family"))
        if is_invalid_runtime_diagnostics_reference(
            raw_kind
        ) or is_invalid_runtime_diagnostics_reference(raw_family):
            continue
        normalized.append(
            {
                "intent_id": _to_non_empty_str(payload.get("intent_id")),
                "kind": raw_kind,
                "family": raw_family,
                "order": int(payload.get("order") or 0) or None,
                "user_visible_label": _to_non_empty_str(
                    payload.get("user_visible_label")
                ),
                "source_text": _to_non_empty_str(payload.get("source_text")),
                "status": _to_non_empty_str(payload.get("status")),
                "allowed_tool_names": _normalize_string_list(
                    payload.get("allowed_tool_names")
                ),
                "completed_by_tool_names": _normalize_string_list(
                    payload.get("completed_by_tool_names")
                ),
                "failure_reason": _to_non_empty_str(payload.get("failure_reason")),
            }
        )
    return normalized


def _normalize_retry_events(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    normalized: list[dict[str, Any]] = []
    for item in value:
        payload = _normalize_json_dict(item)
        if not payload:
            continue
        retry_family = _to_non_empty_str(payload.get("retry_family"))
        if is_invalid_runtime_diagnostics_reference(retry_family):
            continue
        metadata = sanitize_diagnostics_payload(payload.get("metadata")) or {}
        normalized.append(
            {
                "action": _to_non_empty_str(payload.get("action")),
                "target_intent_id": _to_non_empty_str(payload.get("target_intent_id")),
                "retry_family": retry_family,
                "allowed_tool_names": _normalize_string_list(
                    payload.get("allowed_tool_names")
                ),
                "completed_intent_ids": _normalize_string_list(
                    payload.get("completed_intent_ids")
                ),
                "unfinished_intent_ids": _normalize_string_list(
                    payload.get("unfinished_intent_ids")
                ),
                "reason": _to_non_empty_str(payload.get("reason")),
                "provider_failure_kind": _to_non_empty_str(
                    payload.get("provider_failure_kind")
                ),
                "metadata": metadata,
            }
        )
    return normalized


def _sanitize_tool_planner(value: Any) -> dict[str, Any] | None:
    payload = _normalize_json_dict(value)
    if not payload:
        return None
    if is_invalid_runtime_diagnostics_reference(
        payload.get("intent")
    ) or is_invalid_runtime_diagnostics_reference(payload.get("family")):
        return None
    return sanitize_diagnostics_payload(payload)


def _normalize_provider_events(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    normalized: list[dict[str, Any]] = []
    for item in value:
        payload = _normalize_json_dict(item)
        if not payload:
            continue
        normalized.append(dict(payload))
    return normalized


def _normalize_turn_skill_activation(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None

    selected_tool_names = _normalize_string_list(value.get("selected_tool_names"))
    selected_skill_names = _normalize_string_list(value.get("selected_skill_names"))
    inventory_selected_tool_names = _normalize_string_list(
        value.get("inventory_selected_tool_names")
    )
    inventory_selected_skill_names = _normalize_string_list(
        value.get("inventory_selected_skill_names")
    )
    reason = _to_non_empty_str(value.get("reason"))
    applied = bool(value.get("applied"))

    if not (
        applied
        or reason
        or selected_tool_names
        or selected_skill_names
        or inventory_selected_tool_names
        or inventory_selected_skill_names
    ):
        return None

    return {
        "applied": applied,
        "reason": reason,
        "tool_count": int(value.get("tool_count") or len(selected_tool_names) or 0),
        "selected_tool_names": selected_tool_names,
        "skill_count": int(value.get("skill_count") or len(selected_skill_names) or 0),
        "selected_skill_names": selected_skill_names,
        "inventory_tool_count": int(
            value.get("inventory_tool_count") or len(inventory_selected_tool_names) or 0
        ),
        "inventory_selected_tool_names": inventory_selected_tool_names,
        "inventory_skill_count": int(
            value.get("inventory_skill_count")
            or len(inventory_selected_skill_names)
            or 0
        ),
        "inventory_selected_skill_names": inventory_selected_skill_names,
    }


def normalize_turn_skill_activation_payload(value: Any) -> dict[str, Any] | None:
    return _normalize_turn_skill_activation(value)


def _normalize_dict_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    normalized: list[dict[str, Any]] = []
    for item in value:
        payload = _normalize_json_dict(item)
        if not payload:
            continue
        normalized.append(dict(payload))
    return normalized


def _pick_truthy(*values: Any) -> Any:
    for value in values:
        if value:
            return value
    return None


def _pick_first_list(*values: Any) -> list[Any] | None:
    for value in values:
        if isinstance(value, list):
            return value
    return None


def _pick_optional_bool(*sources: Any, key: str) -> bool | None:
    for source in sources:
        if isinstance(source, dict) and key in source:
            raw = source.get(key)
            return bool(raw) if raw is not None else None
    return None


def _pick_dict_payload(*values: Any) -> dict[str, Any] | None:
    return _normalize_json_dict(_pick_truthy(*values))


def _pick_string(*values: Any) -> str | None:
    return _to_non_empty_str(_pick_truthy(*values))


def _pick_string_list(*values: Any) -> list[str]:
    return _normalize_string_list(_pick_truthy(*values))


def _build_web_research_projection(
    *,
    metadata: dict[str, Any],
    turn_record: dict[str, Any] | None,
    turn_record_diagnostics: dict[str, Any],
    context_diagnostics: dict[str, Any],
    last_run_summary: dict[str, Any],
    intent_plan: list[dict[str, Any]],
) -> dict[str, Any]:
    projection = project_canonical_web_research_diagnostics(
        diagnostics_payload={
            **last_run_summary,
            **context_diagnostics,
            **turn_record_diagnostics,
            **metadata,
        },
        turn_record_payload=turn_record,
        intent_plan=intent_plan,
    )
    return sanitize_diagnostics_payload(projection) or {}


def resolve_live_selected_name_list(
    key: str,
    *sources: Any,
    turn_skill_activation: dict[str, Any] | None = None,
) -> tuple[list[str], bool]:
    if isinstance(turn_skill_activation, dict) and key in turn_skill_activation:
        return _normalize_string_list(turn_skill_activation.get(key)), True
    for source in sources:
        if not isinstance(source, dict) or key not in source:
            continue
        return _normalize_string_list(source.get(key)), True
    return [], False


def extract_turn_diagnostics_from_metadata(
    metadata: dict[str, Any],
) -> dict[str, Any]:
    _ensure_legacy_message_turn_flow(metadata)
    turn_record = _normalize_turn_record_payload(metadata.get("turn_record"))
    turn_record_metadata = (
        dict((turn_record or {}).get("metadata") or {})
        if isinstance((turn_record or {}).get("metadata"), dict)
        else {}
    )
    turn_record_diagnostics = (
        dict(turn_record_metadata.get("turn_diagnostics") or {})
        if isinstance(turn_record_metadata.get("turn_diagnostics"), dict)
        else {}
    )
    context_diagnostics = (
        dict(metadata.get("context_diagnostics") or {})
        if isinstance(metadata.get("context_diagnostics"), dict)
        else {}
    )
    last_run_summary = (
        dict(metadata.get("last_run_summary") or {})
        if isinstance(metadata.get("last_run_summary"), dict)
        else {}
    )

    turn_outcome = _pick_string(
        (turn_record or {}).get("turn_outcome"),
        metadata.get("turn_outcome"),
        turn_record_diagnostics.get("turn_outcome"),
        context_diagnostics.get("turn_outcome"),
        last_run_summary.get("turn_outcome"),
    )
    termination_reason = _pick_string(
        (turn_record or {}).get("termination_reason"),
        metadata.get("termination_reason"),
        metadata.get("completion_reason"),
        turn_record_diagnostics.get("termination_reason"),
        context_diagnostics.get("termination_reason"),
        last_run_summary.get("termination_reason"),
        last_run_summary.get("completion_reason"),
    )

    metadata_completion_reason = _to_non_empty_str(metadata.get("completion_reason"))
    metadata_marks_partial = bool(metadata.get("partial")) or bool(
        metadata.get("interrupted")
    )
    if metadata_marks_partial:
        turn_outcome = "partial"
        if bool(metadata.get("interrupted")) or (
            metadata_completion_reason == "interrupted"
        ):
            termination_reason = "interrupted"
        elif metadata_completion_reason:
            termination_reason = metadata_completion_reason
    elif not turn_outcome:
        if (
            bool(metadata.get("partial"))
            or bool(metadata.get("interrupted"))
            or termination_reason == "interrupted"
        ):
            turn_outcome = "partial"
        elif termination_reason in {
            "error",
            "failed",
            "tool_error",
            "tool_round_failed",
        }:
            turn_outcome = "failed"

    protocol_path = _pick_string(
        (turn_record or {}).get("protocol_path"),
        metadata.get("protocol_path"),
        turn_record_diagnostics.get("protocol_path"),
        context_diagnostics.get("protocol_path"),
        last_run_summary.get("protocol_path"),
    )
    turn_skill_activation = _normalize_turn_skill_activation(
        _pick_truthy(
            (turn_record or {}).get("turn_skill_activation"),
            metadata.get("turn_skill_activation"),
            turn_record_diagnostics.get("turn_skill_activation"),
            context_diagnostics.get("turn_skill_activation"),
            last_run_summary.get("turn_skill_activation"),
        )
    )
    selected_tool_names, _selected_tools_explicit = resolve_live_selected_name_list(
        "selected_tool_names",
        turn_record,
        metadata,
        turn_record_diagnostics,
        context_diagnostics,
        last_run_summary,
        turn_skill_activation=turn_skill_activation,
    )
    selected_skill_names, _selected_skills_explicit = resolve_live_selected_name_list(
        "selected_skill_names",
        turn_record,
        metadata,
        turn_record_diagnostics,
        context_diagnostics,
        last_run_summary,
        turn_skill_activation=turn_skill_activation,
    )
    context_sources = _normalize_context_sources(
        _pick_truthy(
            (turn_record or {}).get("context_sources"),
            metadata.get("context_sources"),
            turn_record_diagnostics.get("context_sources"),
            context_diagnostics.get("context_sources"),
            last_run_summary.get("context_sources"),
        )
    )
    contract_breach_type = _pick_string(
        turn_record_metadata.get("contract_breach_type"),
        metadata.get("contract_breach_type"),
        turn_record_diagnostics.get("contract_breach_type"),
        context_diagnostics.get("contract_breach_type"),
        last_run_summary.get("contract_breach_type"),
    )
    tool_planner = _sanitize_tool_planner(
        _pick_truthy(
            (turn_record or {}).get("tool_planner"),
            metadata.get("tool_planner"),
            turn_record_diagnostics.get("tool_planner"),
            context_diagnostics.get("tool_planner"),
            last_run_summary.get("tool_planner"),
        )
    )
    tool_leak_detected = bool(
        _pick_truthy(
            turn_record_metadata.get("tool_leak_detected"),
            metadata.get("tool_leak_detected"),
            turn_record_diagnostics.get("tool_leak_detected"),
            context_diagnostics.get("tool_leak_detected"),
            last_run_summary.get("tool_leak_detected"),
        )
    )
    assistant_claimed_tool_call_without_tool_event = bool(
        _pick_truthy(
            turn_record_metadata.get("assistant_claimed_tool_call_without_tool_event"),
            (turn_record or {}).get("assistant_claimed_tool_call_without_tool_event"),
            metadata.get("assistant_claimed_tool_call_without_tool_event"),
            turn_record_diagnostics.get(
                "assistant_claimed_tool_call_without_tool_event"
            ),
            context_diagnostics.get("assistant_claimed_tool_call_without_tool_event"),
            last_run_summary.get("assistant_claimed_tool_call_without_tool_event"),
        )
    )
    unfinished_intents = _pick_string_list(
        turn_record_metadata.get("unfinished_intents"),
        metadata.get("unfinished_intents"),
        turn_record_diagnostics.get("unfinished_intents"),
        context_diagnostics.get("unfinished_intents"),
        last_run_summary.get("unfinished_intents"),
    )
    leaked_tool_names = _pick_string_list(
        turn_record_metadata.get("leaked_tool_names"),
        metadata.get("leaked_tool_names"),
        turn_record_diagnostics.get("leaked_tool_names"),
        context_diagnostics.get("leaked_tool_names"),
        last_run_summary.get("leaked_tool_names"),
    )
    recovered_via_retry = _pick_optional_bool(
        turn_record_metadata,
        metadata,
        turn_record_diagnostics,
        context_diagnostics,
        last_run_summary,
        key="recovered_via_retry",
    )
    last_tool_name = normalize_live_diagnostics_reference(
        _pick_string(
            (turn_record or {}).get("last_tool_name"),
            metadata.get("last_tool_name"),
            turn_record_diagnostics.get("last_tool_name"),
            context_diagnostics.get("last_tool_name"),
            last_run_summary.get("last_tool_name"),
        )
    )
    interrupted_stage = _pick_string(
        (turn_record or {}).get("interrupted_stage"),
        metadata.get("interrupted_stage"),
        turn_record_diagnostics.get("interrupted_stage"),
        context_diagnostics.get("interrupted_stage"),
        last_run_summary.get("interrupted_stage"),
    )

    tool_loop_progress = (
        dict((turn_record or {}).get("tool_loop_progress") or {})
        if isinstance((turn_record or {}).get("tool_loop_progress"), dict)
        else (
            dict(turn_record_diagnostics.get("tool_loop_progress") or {})
            if isinstance(turn_record_diagnostics.get("tool_loop_progress"), dict)
            else {}
        )
    )
    if not tool_loop_progress and isinstance(metadata.get("tool_loop_progress"), dict):
        tool_loop_progress = dict(metadata.get("tool_loop_progress") or {})
    if not tool_loop_progress and isinstance(
        context_diagnostics.get("tool_loop_progress"), dict
    ):
        tool_loop_progress = dict(context_diagnostics.get("tool_loop_progress") or {})
    if not tool_loop_progress and isinstance(
        last_run_summary.get("tool_loop_progress"), dict
    ):
        tool_loop_progress = dict(last_run_summary.get("tool_loop_progress") or {})

    execution_path = _pick_string(
        (turn_record or {}).get("execution_path"),
        metadata.get("execution_path"),
        turn_record_diagnostics.get("execution_path"),
        context_diagnostics.get("execution_path"),
        last_run_summary.get("execution_path"),
    )
    active_intent_id = _pick_string(
        (turn_record or {}).get("active_intent_id"),
        metadata.get("active_intent_id"),
        turn_record_diagnostics.get("active_intent_id"),
        context_diagnostics.get("active_intent_id"),
        last_run_summary.get("active_intent_id"),
    )
    continuation_source = normalize_live_diagnostics_reference(
        _pick_string(
            (turn_record or {}).get("continuation_source"),
            metadata.get("continuation_source"),
            turn_record_diagnostics.get("continuation_source"),
            context_diagnostics.get("continuation_source"),
            last_run_summary.get("continuation_source"),
        )
    )
    conversation_outcome = _pick_string(
        (turn_record or {}).get("conversation_outcome"),
        metadata.get("conversation_outcome"),
        turn_record_diagnostics.get("conversation_outcome"),
        context_diagnostics.get("conversation_outcome"),
        last_run_summary.get("conversation_outcome"),
        turn_outcome,
    )
    intent_plan = _normalize_intent_plan(
        _pick_truthy(
            (turn_record or {}).get("intent_plan"),
            metadata.get("intent_plan"),
            turn_record_diagnostics.get("intent_plan"),
            context_diagnostics.get("intent_plan"),
            last_run_summary.get("intent_plan"),
        )
    )
    budget = _pick_dict_payload(
        (turn_record or {}).get("budget"),
        metadata.get("budget"),
        turn_record_diagnostics.get("budget"),
        context_diagnostics.get("budget"),
        last_run_summary.get("budget"),
    )
    routing = (
        _pick_dict_payload(
            metadata.get("routing"),
            turn_record_diagnostics.get("routing"),
            context_diagnostics.get("routing"),
            last_run_summary.get("routing"),
        )
        or {}
    )
    candidate_tool_names = _pick_string_list(
        routing.get("candidate_tool_names"),
        metadata.get("candidate_tool_names"),
        turn_record_diagnostics.get("candidate_tool_names"),
        context_diagnostics.get("candidate_tool_names"),
        last_run_summary.get("candidate_tool_names"),
    )
    recovery = (
        _pick_dict_payload(
            metadata.get("recovery"),
            turn_record_diagnostics.get("recovery"),
            context_diagnostics.get("recovery"),
            last_run_summary.get("recovery"),
        )
        or {}
    )
    path_decision = _pick_dict_payload(
        (turn_record or {}).get("path_decision"),
        metadata.get("path_decision"),
        turn_record_diagnostics.get("path_decision"),
        context_diagnostics.get("path_decision"),
        last_run_summary.get("path_decision"),
    )
    capability_injection = _pick_dict_payload(
        (turn_record or {}).get("capability_injection"),
        (turn_record or {}).get("capability_injection_decision"),
        metadata.get("capability_injection"),
        metadata.get("capability_injection_decision"),
        turn_record_diagnostics.get("capability_injection"),
        turn_record_diagnostics.get("capability_injection_decision"),
        context_diagnostics.get("capability_injection"),
        context_diagnostics.get("capability_injection_decision"),
        last_run_summary.get("capability_injection"),
        last_run_summary.get("capability_injection_decision"),
    )
    tool_filtering = _pick_dict_payload(
        (turn_record or {}).get("tool_filtering"),
        metadata.get("tool_filtering"),
        routing.get("tool_filtering"),
        turn_record_diagnostics.get("tool_filtering"),
        context_diagnostics.get("tool_filtering"),
        last_run_summary.get("tool_filtering"),
    )
    recovery_chain = _normalize_dict_list(
        _pick_first_list(
            (turn_record or {}).get("recovery_chain"),
            metadata.get("recovery_chain"),
            recovery.get("recovery_chain"),
            turn_record_diagnostics.get("recovery_chain"),
            (_normalize_json_dict(turn_record_diagnostics.get("recovery")) or {}).get(
                "recovery_chain"
            ),
            context_diagnostics.get("recovery_chain"),
            (_normalize_json_dict(context_diagnostics.get("recovery")) or {}).get(
                "recovery_chain"
            ),
            last_run_summary.get("recovery_chain"),
            (_normalize_json_dict(last_run_summary.get("recovery")) or {}).get(
                "recovery_chain"
            ),
        )
    )
    retry_events = _normalize_retry_events(
        _pick_truthy(
            recovery.get("retry_events"),
            metadata.get("retry_events"),
            turn_record_diagnostics.get("retry_events"),
            context_diagnostics.get("retry_events"),
            last_run_summary.get("retry_events"),
        )
    )
    partial_exit_reason = _pick_string(
        recovery.get("partial_exit_reason"),
        metadata.get("partial_exit_reason"),
        turn_record_diagnostics.get("partial_exit_reason"),
        context_diagnostics.get("partial_exit_reason"),
        last_run_summary.get("partial_exit_reason"),
    )
    failure_kind = _pick_string(
        metadata.get("failure_kind"),
        turn_record_diagnostics.get("failure_kind"),
        (_normalize_json_dict(metadata.get("failures")) or {}).get("failure_kind"),
        (_normalize_json_dict(turn_record_diagnostics.get("failures")) or {}).get(
            "failure_kind"
        ),
        context_diagnostics.get("failure_kind"),
        last_run_summary.get("failure_kind"),
    )
    provider_events = _normalize_provider_events(
        _pick_truthy(
            metadata.get("provider_events"),
            (_normalize_json_dict(metadata.get("failures")) or {}).get(
                "provider_events"
            ),
            turn_record_diagnostics.get("provider_events"),
            (_normalize_json_dict(turn_record_diagnostics.get("failures")) or {}).get(
                "provider_events"
            ),
            context_diagnostics.get("provider_events"),
            last_run_summary.get("provider_events"),
        )
    )
    sync_rescue = _pick_optional_bool(
        turn_record_metadata,
        metadata,
        turn_record_diagnostics,
        context_diagnostics,
        last_run_summary,
        key="sync_rescue",
    )
    should_record_call_log = _pick_optional_bool(
        turn_record_metadata,
        metadata,
        turn_record_diagnostics,
        context_diagnostics,
        last_run_summary,
        key="should_record_call_log",
    )
    budget_status = _pick_string(
        (budget or {}).get("status"),
        metadata.get("budget_status"),
        context_diagnostics.get("budget_status"),
        last_run_summary.get("budget_status"),
    )
    budget_exit_reason = _pick_string(
        (budget or {}).get("exit_reason"),
        metadata.get("budget_exit_reason"),
        context_diagnostics.get("budget_exit_reason"),
        last_run_summary.get("budget_exit_reason"),
    )
    budget_projection = derive_budget_projection(
        budget=budget,
        budget_status=budget_status,
        budget_exit_reason=budget_exit_reason,
        termination_reason=termination_reason,
    )
    budget = budget_projection.get("budget") or budget
    budget_status = budget_projection.get("budget_status") or budget_status
    budget_exit_reason = (
        budget_projection.get("budget_exit_reason") or budget_exit_reason
    )
    final_output_source = _pick_string(
        (turn_record or {}).get("final_output_source"),
        metadata.get("final_output_source"),
        turn_record_diagnostics.get("final_output_source"),
        context_diagnostics.get("final_output_source"),
        last_run_summary.get("final_output_source"),
    )
    web_research_projection = _build_web_research_projection(
        metadata=metadata,
        turn_record=turn_record,
        turn_record_diagnostics=turn_record_diagnostics,
        context_diagnostics=context_diagnostics,
        last_run_summary=last_run_summary,
        intent_plan=intent_plan,
    )

    diagnostics = {
        "turn_record": turn_record,
        "turn_outcome": turn_outcome,
        "termination_reason": termination_reason,
        "protocol_path": protocol_path,
        "selected_tool_names": selected_tool_names,
        "selected_skill_names": selected_skill_names,
        "turn_skill_activation": turn_skill_activation,
        "context_sources": context_sources,
        "tool_planner": tool_planner,
        "path_decision": path_decision,
        "capability_injection": capability_injection,
        "tool_filtering": tool_filtering,
        "recovery_chain": recovery_chain,
        "contract_breach_type": contract_breach_type,
        "tool_leak_detected": tool_leak_detected,
        "assistant_claimed_tool_call_without_tool_event": (
            assistant_claimed_tool_call_without_tool_event
        ),
        "unfinished_intents": unfinished_intents,
        "leaked_tool_names": leaked_tool_names,
        "recovered_via_retry": recovered_via_retry,
        "execution_path": execution_path,
        "active_intent_id": active_intent_id,
        "continuation_source": continuation_source,
        "conversation_outcome": conversation_outcome,
        "intent_plan": intent_plan,
        "budget": budget,
        "budget_status": budget_status,
        "budget_exit_reason": budget_exit_reason,
        "final_output_source": final_output_source,
        "candidate_tool_names": candidate_tool_names,
        "retry_events": retry_events,
        "partial_exit_reason": partial_exit_reason,
        "failure_kind": failure_kind,
        "provider_events": provider_events,
        "last_tool_name": last_tool_name,
        "interrupted_stage": interrupted_stage,
        "tool_loop_progress": tool_loop_progress,
        "sync_rescue": sync_rescue,
        "should_record_call_log": should_record_call_log,
    }
    diagnostics.update(web_research_projection)
    return diagnostics


__all__ = [
    "extract_turn_diagnostics_from_metadata",
    "is_invalid_runtime_diagnostics_reference",
    "normalize_live_diagnostics_reference",
    "normalize_turn_skill_activation_payload",
    "resolve_live_selected_name_list",
    "sanitize_diagnostics_payload",
]
