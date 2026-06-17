"""AI CLI normalization and diagnostics extraction helpers."""

from __future__ import annotations

from app.cli_commands import state as S
from app.services.ai.conversation_diagnostics_projector_support import (
    is_invalid_runtime_diagnostics_reference,
    normalize_live_diagnostics_reference,
    sanitize_diagnostics_payload,
)
from app.services.ai.turn_failure_normalizer import (
    derive_budget_projection,
    resolve_failure_projection,
)

_json_default = S._json_default


def _truncate_cli_block(
    value: object,
    *,
    max_chars: int = 600,
    full_content: bool = False,
) -> str:
    text = str(value or "")
    if full_content or len(text) <= max_chars:
        return text
    return f"{text[: max_chars - 3]}..."


def _indent_cli_block(text: str, prefix: str = "    ") -> str:
    lines = (text or "").splitlines() or [""]
    return "\n".join(f"{prefix}{line}" for line in lines)


def _compact_json_text(value: object) -> str:
    import json

    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        default=_json_default,
    )


def _normalize_cli_string_list(raw_value: object) -> list[str]:
    if not isinstance(raw_value, list):
        return []
    out: list[str] = []
    for item in raw_value:
        text = normalize_live_diagnostics_reference(item) or ""
        if text and text not in out:
            out.append(text)
    return out


def _normalize_cli_context_sources(raw_value: object) -> list[dict]:
    if not isinstance(raw_value, list):
        return []
    normalized: list[dict] = []
    for item in raw_value:
        if not isinstance(item, dict):
            continue
        kind = _normalize_cli_optional_string(item.get("kind"))
        name = _normalize_cli_optional_string(item.get("name"))
        if not (kind or name):
            continue
        if is_invalid_runtime_diagnostics_reference(
            kind
        ) or is_invalid_runtime_diagnostics_reference(name):
            continue
        normalized.append(
            {
                "kind": kind,
                "name": name,
                "active": bool(item.get("active", True)),
                "metadata": sanitize_diagnostics_payload(item.get("metadata")) or {},
            }
        )
    return normalized


def _normalize_cli_fallback_history(raw_value: object) -> list[dict]:
    if not isinstance(raw_value, list):
        return []
    normalized: list[dict] = []
    for item in raw_value:
        if not isinstance(item, dict):
            continue
        from_protocol = _normalize_cli_optional_string(item.get("from_protocol"))
        to_protocol = _normalize_cli_optional_string(item.get("to_protocol"))
        reason = _normalize_cli_optional_string(item.get("reason"))
        if not (from_protocol or to_protocol or reason):
            continue
        normalized.append(
            {
                "from_protocol": from_protocol,
                "to_protocol": to_protocol,
                "reason": reason,
                "recovered": bool(item.get("recovered", False)),
                "metadata": _normalize_cli_dict(item.get("metadata")),
            }
        )
    return normalized


def _normalize_cli_bool(raw_value: object) -> bool | None:
    if isinstance(raw_value, bool):
        return raw_value
    if raw_value is None:
        return None
    normalized = str(raw_value).strip().lower()
    if normalized in {"true", "1", "yes", "y", "on"}:
        return True
    if normalized in {"false", "0", "no", "n", "off"}:
        return False
    return None


def _normalize_cli_optional_string(raw_value: object) -> str | None:
    if raw_value is None:
        return None
    text = str(raw_value).strip()
    if not text:
        return None
    if text.lower() in {"none", "null", "undefined"}:
        return None
    return text


def _normalize_cli_json_value(raw_value: object) -> object:
    if isinstance(raw_value, dict):
        return {
            str(key): _normalize_cli_json_value(raw_value[key])
            for key in raw_value
            if isinstance(key, str) or key is not None
        }
    if isinstance(raw_value, list):
        return [_normalize_cli_json_value(item) for item in raw_value]
    if isinstance(raw_value, tuple):
        return [_normalize_cli_json_value(item) for item in raw_value]
    if isinstance(raw_value, str):
        return _normalize_cli_optional_string(raw_value)
    return raw_value


def _normalize_cli_dict(raw_value: object) -> dict:
    if not isinstance(raw_value, dict):
        return {}
    normalized = _normalize_cli_json_value(raw_value)
    return normalized if isinstance(normalized, dict) else {}


def _normalize_cli_dict_list(raw_value: object) -> list[dict]:
    if not isinstance(raw_value, list):
        return []
    normalized: list[dict] = []
    for item in raw_value:
        payload = _normalize_cli_dict(item)
        if not payload:
            continue
        normalized.append(payload)
    return normalized


def _contains_invalid_runtime_diagnostics_reference(value: object) -> bool:
    if isinstance(value, dict):
        for key, nested in value.items():
            if is_invalid_runtime_diagnostics_reference(key):
                return True
            if _contains_invalid_runtime_diagnostics_reference(nested):
                return True
        return False
    if isinstance(value, list | tuple):
        return any(
            _contains_invalid_runtime_diagnostics_reference(item) for item in value
        )
    if isinstance(value, str):
        return is_invalid_runtime_diagnostics_reference(value)
    return False


def _normalize_cli_tool_calls(raw_value: object) -> list[dict]:
    if not isinstance(raw_value, list):
        return []
    normalized: list[dict] = []
    for item in raw_value:
        payload = _normalize_cli_dict(item)
        if not payload:
            continue
        function_payload = (
            payload.get("function") if isinstance(payload.get("function"), dict) else {}
        )
        tool_name = (
            payload.get("name")
            or payload.get("tool_name")
            or (
                function_payload.get("name")
                if isinstance(function_payload, dict)
                else None
            )
        )
        if tool_name and not normalize_live_diagnostics_reference(tool_name):
            continue
        if _contains_invalid_runtime_diagnostics_reference(payload):
            continue
        sanitized = sanitize_diagnostics_payload(payload)
        if sanitized:
            normalized.append(sanitized)
    return normalized


def _pick_first_cli_dict_list(*values: object) -> list[dict] | None:
    for value in values:
        if isinstance(value, list):
            return _normalize_cli_dict_list(value)
    return None




def _normalize_cli_retry_events(raw_value: object) -> list[dict]:
    if not isinstance(raw_value, list):
        return []
    normalized: list[dict] = []
    for item in raw_value:
        payload = _normalize_cli_dict(item)
        if not payload:
            continue
        retry_family = normalize_live_diagnostics_reference(payload.get("retry_family"))
        if payload.get("retry_family") and not retry_family:
            continue
        normalized.append(
            {
                "action": _normalize_cli_optional_string(payload.get("action")),
                "target_intent_id": _normalize_cli_optional_string(
                    payload.get("target_intent_id")
                ),
                "retry_family": retry_family,
                "allowed_tool_names": _normalize_cli_string_list(
                    payload.get("allowed_tool_names")
                ),
                "completed_intent_ids": _normalize_cli_string_list(
                    payload.get("completed_intent_ids")
                ),
                "unfinished_intent_ids": _normalize_cli_string_list(
                    payload.get("unfinished_intent_ids")
                ),
                "reason": _normalize_cli_optional_string(payload.get("reason")),
                "provider_failure_kind": _normalize_cli_optional_string(
                    payload.get("provider_failure_kind")
                ),
                "metadata": _normalize_cli_dict(payload.get("metadata")),
            }
        )
    return normalized


def _normalize_cli_provider_events(raw_value: object) -> list[dict]:
    if not isinstance(raw_value, list):
        return []
    normalized: list[dict] = []
    for item in raw_value:
        payload = _normalize_cli_dict(item)
        if not payload:
            continue
        if _contains_invalid_runtime_diagnostics_reference(payload):
            continue
        sanitized = sanitize_diagnostics_payload(payload)
        if sanitized:
            normalized.append(sanitized)
    return normalized


def _normalize_cli_call_log_row(raw_value: object) -> dict:
    payload = _normalize_cli_dict(raw_value)
    if not payload:
        return {}
    payload["turn_outcome"] = _normalize_cli_optional_string(
        payload.get("turn_outcome")
    )
    payload["termination_reason"] = _normalize_cli_optional_string(
        payload.get("termination_reason")
    )
    payload["protocol_path"] = _normalize_cli_optional_string(
        payload.get("protocol_path")
    )
    payload["selected_tool_names"] = _normalize_cli_string_list(
        payload.get("selected_tool_names")
    )
    payload["selected_skill_names"] = _normalize_cli_string_list(
        payload.get("selected_skill_names")
    )
    payload["execution_path"] = _normalize_cli_optional_string(
        payload.get("execution_path")
    )
    payload["failure_kind"] = _normalize_cli_optional_string(
        payload.get("failure_kind")
    )
    payload["fallback_history"] = _normalize_cli_fallback_history(
        payload.get("fallback_history")
    )
    payload["provider_events"] = _normalize_cli_provider_events(
        payload.get("provider_events")
    )
    payload["budget"] = _normalize_cli_dict(payload.get("budget"))
    budget_projection = derive_budget_projection(
        budget=payload.get("budget"),
        budget_status=payload.get("budget_status"),
        budget_exit_reason=payload.get("budget_exit_reason"),
        termination_reason=payload.get("termination_reason"),
    )
    payload["budget"] = _normalize_cli_dict(budget_projection.get("budget"))
    payload["budget_status"] = _normalize_cli_optional_string(
        budget_projection.get("budget_status")
    )
    payload["budget_exit_reason"] = _normalize_cli_optional_string(
        budget_projection.get("budget_exit_reason")
    )
    payload["final_output_source"] = _normalize_cli_optional_string(
        payload.get("final_output_source")
    )
    payload["retry_events"] = _normalize_cli_retry_events(payload.get("retry_events"))
    payload["partial_exit_reason"] = _normalize_cli_optional_string(
        payload.get("partial_exit_reason")
    )
    payload["sync_rescue"] = _normalize_cli_bool(payload.get("sync_rescue"))
    payload["contract_breach_type"] = _normalize_cli_optional_string(
        payload.get("contract_breach_type")
    )
    payload["tool_leak_detected"] = bool(payload.get("tool_leak_detected"))
    payload["unfinished_intents"] = _normalize_cli_string_list(
        payload.get("unfinished_intents")
    )
    payload["leaked_tool_names"] = _normalize_cli_string_list(
        payload.get("leaked_tool_names")
    )
    payload["recovered_via_retry"] = _normalize_cli_bool(
        payload.get("recovered_via_retry")
    )
    payload["last_tool_name"] = normalize_live_diagnostics_reference(
        payload.get("last_tool_name")
    )
    payload["interrupted_stage"] = _normalize_cli_optional_string(
        payload.get("interrupted_stage")
    )
    payload["tool_loop_progress"] = (
        _normalize_cli_dict(payload.get("tool_loop_progress"))
        if isinstance(payload.get("tool_loop_progress"), dict)
        else {}
    )
    payload["turn_record"] = (
        _normalize_cli_dict(payload.get("turn_record"))
        if isinstance(payload.get("turn_record"), dict)
        else None
    )
    normalized_failure = resolve_failure_projection(
        diagnostics={
            "turn_record": payload.get("turn_record"),
            "turn_outcome": payload.get("turn_outcome"),
            "termination_reason": payload.get("termination_reason"),
            "failure_kind": payload.get("failure_kind"),
            "provider_events": payload.get("provider_events"),
            "budget": payload.get("budget"),
            "budget_exit_reason": payload.get("budget_exit_reason"),
            "final_output_source": payload.get("final_output_source"),
            "error_message": payload.get("error_message"),
        }
    )
    payload["turn_outcome"] = _normalize_cli_optional_string(
        normalized_failure.get("turn_outcome")
    ) or payload.get("turn_outcome")
    payload["termination_reason"] = _normalize_cli_optional_string(
        normalized_failure.get("termination_reason")
    ) or payload.get("termination_reason")
    normalized_failure_kind = _normalize_cli_optional_string(
        normalized_failure.get("failure_kind")
    )
    payload["failure_kind"] = (
        normalized_failure_kind
        if normalized_failure.get("authoritative_completed_success")
        else normalized_failure_kind or payload.get("failure_kind")
    )
    return sanitize_diagnostics_payload(payload) or {}


def _extract_turn_diagnostics_from_call_log_metadata(metadata: object) -> dict:
    if not isinstance(metadata, dict):
        return {}
    diagnostics = metadata.get("turn_diagnostics")
    if not isinstance(diagnostics, dict):
        diagnostics = {}
    turn_record = diagnostics.get("turn_record")
    if not isinstance(turn_record, dict):
        turn_record = metadata.get("request", {}).get("turn_record")
        if not isinstance(turn_record, dict):
            turn_record = {}
    turn_record_metadata = (
        dict(turn_record.get("metadata") or {})
        if isinstance(turn_record.get("metadata"), dict)
        else {}
    )
    turn_record_diagnostics = _normalize_cli_dict(
        turn_record_metadata.get("turn_diagnostics")
    )
    routing = _normalize_cli_dict(
        diagnostics.get("routing") or turn_record_diagnostics.get("routing")
    )
    recovery = _normalize_cli_dict(
        diagnostics.get("recovery") or turn_record_diagnostics.get("recovery")
    )
    failures = _normalize_cli_dict(
        diagnostics.get("failures") or turn_record_diagnostics.get("failures")
    )
    path_decision = _normalize_cli_dict(
        diagnostics.get("path_decision")
        or turn_record.get("path_decision")
        or turn_record_diagnostics.get("path_decision")
    )
    capability_injection = _normalize_cli_dict(
        diagnostics.get("capability_injection")
        or diagnostics.get("capability_injection_decision")
        or turn_record.get("capability_injection")
        or turn_record.get("capability_injection_decision")
        or turn_record_diagnostics.get("capability_injection")
        or turn_record_diagnostics.get("capability_injection_decision")
    )
    tool_filtering = _normalize_cli_dict(
        diagnostics.get("tool_filtering")
        or turn_record.get("tool_filtering")
        or routing.get("tool_filtering")
        or turn_record_diagnostics.get("tool_filtering")
    )
    recovery_chain = _pick_first_cli_dict_list(
        diagnostics.get("recovery_chain"),
        turn_record.get("recovery_chain"),
        recovery.get("recovery_chain"),
        turn_record_diagnostics.get("recovery_chain"),
    )
    raw_turn_outcome = _normalize_cli_optional_string(
        turn_record.get("turn_outcome") or diagnostics.get("turn_outcome")
    )
    raw_termination_reason = _normalize_cli_optional_string(
        turn_record.get("termination_reason") or diagnostics.get("termination_reason")
    )
    budget = _normalize_cli_dict(diagnostics.get("budget"))
    budget_projection = derive_budget_projection(
        budget=budget,
        budget_status=budget.get("status") or diagnostics.get("budget_status"),
        budget_exit_reason=budget.get("exit_reason")
        or diagnostics.get("budget_exit_reason"),
        termination_reason=raw_termination_reason,
    )
    budget = _normalize_cli_dict(budget_projection.get("budget"))
    final_output_source = _normalize_cli_optional_string(
        turn_record.get("final_output_source")
        or diagnostics.get("final_output_source")
        or turn_record_diagnostics.get("final_output_source")
    )
    raw_failure_kind = _normalize_cli_optional_string(
        failures.get("failure_kind") or diagnostics.get("failure_kind")
    )
    provider_events = _normalize_cli_provider_events(
        failures.get("provider_events") or diagnostics.get("provider_events")
    )
    normalized_failure = resolve_failure_projection(
        diagnostics={
            "turn_record": turn_record,
            "turn_outcome": raw_turn_outcome,
            "termination_reason": raw_termination_reason,
            "failure_kind": raw_failure_kind,
            "provider_events": provider_events,
            "budget": budget,
            "budget_exit_reason": budget_projection.get("budget_exit_reason"),
            "final_output_source": final_output_source,
            "error_message": diagnostics.get("error_message")
            or metadata.get("error_message"),
        }
    )
    turn_outcome = (
        _normalize_cli_optional_string(normalized_failure.get("turn_outcome"))
        or raw_turn_outcome
    )
    termination_reason = (
        _normalize_cli_optional_string(normalized_failure.get("termination_reason"))
        or raw_termination_reason
    )
    normalized_failure_kind = _normalize_cli_optional_string(
        normalized_failure.get("failure_kind")
    )
    failure_kind = (
        normalized_failure_kind
        if normalized_failure.get("authoritative_completed_success")
        else normalized_failure_kind or raw_failure_kind
    )

    payload = {
        "turn_outcome": turn_outcome,
        "termination_reason": termination_reason,
        "protocol_path": _normalize_cli_optional_string(
            turn_record.get("protocol_path") or diagnostics.get("protocol_path")
        ),
        "selected_tool_names": _normalize_cli_string_list(
            turn_record.get("selected_tool_names")
            or diagnostics.get("selected_tool_names")
        ),
        "selected_skill_names": _normalize_cli_string_list(
            turn_record.get("selected_skill_names")
            or diagnostics.get("selected_skill_names")
        ),
        "execution_path": _normalize_cli_optional_string(
            diagnostics.get("execution_path")
            or turn_record_diagnostics.get("execution_path")
        ),
        "path_decision": path_decision,
        "capability_injection": capability_injection,
        "tool_filtering": tool_filtering,
        "recovery_chain": recovery_chain,
        "budget": budget,
        "budget_status": _normalize_cli_optional_string(
            budget_projection.get("budget_status")
        ),
        "budget_exit_reason": _normalize_cli_optional_string(
            budget_projection.get("budget_exit_reason")
        ),
        "final_output_source": final_output_source,
        "candidate_tool_names": _normalize_cli_string_list(
            routing.get("candidate_tool_names")
            or diagnostics.get("candidate_tool_names")
        ),
        "context_sources": _normalize_cli_context_sources(
            turn_record.get("context_sources") or diagnostics.get("context_sources")
        ),
        "fallback_history": _normalize_cli_fallback_history(
            turn_record.get("fallback_history") or diagnostics.get("fallback_history")
        ),
        "retry_events": _normalize_cli_retry_events(
            recovery.get("retry_events") or diagnostics.get("retry_events")
        ),
        "partial_exit_reason": _normalize_cli_optional_string(
            recovery.get("partial_exit_reason")
            or diagnostics.get("partial_exit_reason")
        ),
        "failure_kind": failure_kind,
        "provider_events": provider_events,
        "sync_rescue": next(
            (
                parsed
                for parsed in (
                    _normalize_cli_bool(turn_record_metadata.get("sync_rescue")),
                    _normalize_cli_bool(turn_record.get("sync_rescue")),
                    _normalize_cli_bool(diagnostics.get("sync_rescue")),
                )
                if parsed is not None
            ),
            None,
        ),
        "should_record_call_log": next(
            (
                parsed
                for parsed in (
                    _normalize_cli_bool(
                        turn_record_metadata.get("should_record_call_log")
                    ),
                    _normalize_cli_bool(turn_record.get("should_record_call_log")),
                    _normalize_cli_bool(diagnostics.get("should_record_call_log")),
                )
                if parsed is not None
            ),
            None,
        ),
        "contract_breach_type": _normalize_cli_optional_string(
            turn_record_metadata.get("contract_breach_type")
            or diagnostics.get("contract_breach_type")
        ),
        "tool_leak_detected": bool(
            turn_record_metadata.get("tool_leak_detected")
            or diagnostics.get("tool_leak_detected")
        ),
        "unfinished_intents": _normalize_cli_string_list(
            turn_record_metadata.get("unfinished_intents")
            or recovery.get("unfinished_intents")
            or diagnostics.get("unfinished_intents")
        ),
        "leaked_tool_names": _normalize_cli_string_list(
            turn_record_metadata.get("leaked_tool_names")
            or diagnostics.get("leaked_tool_names")
        ),
        "recovered_via_retry": next(
            (
                parsed
                for parsed in (
                    _normalize_cli_bool(
                        turn_record_metadata.get("recovered_via_retry")
                    ),
                    _normalize_cli_bool(diagnostics.get("recovered_via_retry")),
                )
                if parsed is not None
            ),
            None,
        ),
        "last_tool_name": normalize_live_diagnostics_reference(
            turn_record.get("last_tool_name") or diagnostics.get("last_tool_name")
        ),
        "interrupted_stage": _normalize_cli_optional_string(
            turn_record.get("interrupted_stage") or diagnostics.get("interrupted_stage")
        ),
        "tool_loop_progress": (
            _normalize_cli_dict(turn_record.get("tool_loop_progress"))
            if isinstance(turn_record.get("tool_loop_progress"), dict)
            else (
                _normalize_cli_dict(diagnostics.get("tool_loop_progress"))
                if isinstance(diagnostics.get("tool_loop_progress"), dict)
                else {}
            )
        ),
        "turn_record": _normalize_cli_dict(turn_record) or None,
    }
    return sanitize_diagnostics_payload(payload) or {}
