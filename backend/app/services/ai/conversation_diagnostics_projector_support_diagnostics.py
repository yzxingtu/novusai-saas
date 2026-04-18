"""Turn diagnostics extraction helpers for conversation diagnostics projector."""

from __future__ import annotations

from typing import Any

from app.ai.json_safe import normalize_json_safe_dict
from app.services.ai.turn_failure_normalizer import derive_budget_projection


def _normalize_turn_record_payload(turn_record: Any) -> dict[str, Any] | None:
    return normalize_json_safe_dict(turn_record)


def _to_non_empty_str(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    if text.lower() in {"none", "null", "undefined"}:
        return None
    return text


def _normalize_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


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
        normalized.append(
            {
                "kind": source_kind,
                "name": source_name,
                "active": bool(item.get("active", True)),
                "metadata": dict(item.get("metadata") or {}),
            }
        )
    return normalized


def _normalize_json_dict(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    return {
        str(key): value[key]
        for key in value
        if isinstance(key, str) or key is not None
    }


def _normalize_intent_plan(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    normalized: list[dict[str, Any]] = []
    for item in value:
        payload = _normalize_json_dict(item)
        if not payload:
            continue
        normalized.append(
            {
                "intent_id": _to_non_empty_str(payload.get("intent_id")),
                "kind": _to_non_empty_str(payload.get("kind")),
                "family": _to_non_empty_str(payload.get("family")),
                "order": int(payload.get("order") or 0) or None,
                "user_visible_label": _to_non_empty_str(
                    payload.get("user_visible_label")
                ),
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
        normalized.append(
            {
                "action": _to_non_empty_str(payload.get("action")),
                "target_intent_id": _to_non_empty_str(payload.get("target_intent_id")),
                "retry_family": _to_non_empty_str(payload.get("retry_family")),
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
                "metadata": dict(payload.get("metadata") or {}),
            }
        )
    return normalized


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


def extract_turn_diagnostics_from_metadata(
    metadata: dict[str, Any],
) -> dict[str, Any]:
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
    selected_tool_names = _pick_string_list(
        (turn_record or {}).get("selected_tool_names"),
        metadata.get("selected_tool_names"),
        turn_record_diagnostics.get("selected_tool_names"),
        context_diagnostics.get("selected_tool_names"),
        last_run_summary.get("selected_tool_names"),
    )
    selected_skill_names = _pick_string_list(
        (turn_record or {}).get("selected_skill_names"),
        metadata.get("selected_skill_names"),
        turn_record_diagnostics.get("selected_skill_names"),
        context_diagnostics.get("selected_skill_names"),
        last_run_summary.get("selected_skill_names"),
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
    tool_planner = _pick_dict_payload(
        (turn_record or {}).get("tool_planner"),
        metadata.get("tool_planner"),
        turn_record_diagnostics.get("tool_planner"),
        context_diagnostics.get("tool_planner"),
        last_run_summary.get("tool_planner"),
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
    last_tool_name = _pick_string(
        (turn_record or {}).get("last_tool_name"),
        metadata.get("last_tool_name"),
        turn_record_diagnostics.get("last_tool_name"),
        context_diagnostics.get("last_tool_name"),
        last_run_summary.get("last_tool_name"),
    )
    last_page_key = _pick_string(
        (turn_record or {}).get("last_page_key"),
        metadata.get("last_page_key"),
        turn_record_diagnostics.get("last_page_key"),
        context_diagnostics.get("last_page_key"),
        last_run_summary.get("last_page_key"),
    )
    last_page_op = _pick_string(
        (turn_record or {}).get("last_page_op"),
        metadata.get("last_page_op"),
        turn_record_diagnostics.get("last_page_op"),
        context_diagnostics.get("last_page_op"),
        last_run_summary.get("last_page_op"),
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
    continuation_source = _pick_string(
        (turn_record or {}).get("continuation_source"),
        metadata.get("continuation_source"),
        turn_record_diagnostics.get("continuation_source"),
        context_diagnostics.get("continuation_source"),
        last_run_summary.get("continuation_source"),
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

    return {
        "turn_record": turn_record,
        "turn_outcome": turn_outcome,
        "termination_reason": termination_reason,
        "protocol_path": protocol_path,
        "selected_tool_names": selected_tool_names,
        "selected_skill_names": selected_skill_names,
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
        "last_page_key": last_page_key,
        "last_page_op": last_page_op,
        "interrupted_stage": interrupted_stage,
        "tool_loop_progress": tool_loop_progress,
        "sync_rescue": sync_rescue,
        "should_record_call_log": should_record_call_log,
    }


__all__ = ["extract_turn_diagnostics_from_metadata"]
