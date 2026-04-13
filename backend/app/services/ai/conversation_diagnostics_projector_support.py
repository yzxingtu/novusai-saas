"""
Conversation diagnostics projector helpers.
"""

from __future__ import annotations

from typing import Any

from app.ai.json_safe import normalize_json_safe as _normalize_json_safe
from app.ai.json_safe import normalize_json_safe_dict as _normalize_json_safe_dict
from app.ai.tools.types import ToolResult
from app.ai.types import ChatMessage


def copy_metadata(raw: Any) -> dict[str, Any] | None:
    return normalize_json_safe_dict(raw)


def normalize_json_safe(value: Any) -> Any:
    return _normalize_json_safe(value)


def normalize_json_safe_dict(raw: Any) -> dict[str, Any] | None:
    return _normalize_json_safe_dict(raw)


def normalize_turn_record_payload(turn_record: Any) -> dict[str, Any] | None:
    return normalize_json_safe_dict(turn_record)


def to_non_empty_str(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    if text.lower() in {"none", "null", "undefined"}:
        return None
    return text


def normalize_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def normalize_context_sources(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    normalized: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        source_name = to_non_empty_str(item.get("name"))
        source_kind = to_non_empty_str(item.get("kind"))
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


def normalize_json_dict(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    return {
        str(key): value[key]
        for key in value
        if isinstance(key, str) or key is not None
    }


def normalize_intent_plan(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    normalized: list[dict[str, Any]] = []
    for item in value:
        payload = normalize_json_dict(item)
        if not payload:
            continue
        normalized.append(
            {
                "intent_id": to_non_empty_str(payload.get("intent_id")),
                "kind": to_non_empty_str(payload.get("kind")),
                "family": to_non_empty_str(payload.get("family")),
                "order": int(payload.get("order") or 0) or None,
                "user_visible_label": to_non_empty_str(
                    payload.get("user_visible_label")
                ),
                "status": to_non_empty_str(payload.get("status")),
                "allowed_tool_names": normalize_string_list(
                    payload.get("allowed_tool_names")
                ),
                "completed_by_tool_names": normalize_string_list(
                    payload.get("completed_by_tool_names")
                ),
                "failure_reason": to_non_empty_str(payload.get("failure_reason")),
            }
        )
    return normalized


def normalize_retry_events(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    normalized: list[dict[str, Any]] = []
    for item in value:
        payload = normalize_json_dict(item)
        if not payload:
            continue
        normalized.append(
            {
                "action": to_non_empty_str(payload.get("action")),
                "target_intent_id": to_non_empty_str(payload.get("target_intent_id")),
                "retry_family": to_non_empty_str(payload.get("retry_family")),
                "allowed_tool_names": normalize_string_list(
                    payload.get("allowed_tool_names")
                ),
                "completed_intent_ids": normalize_string_list(
                    payload.get("completed_intent_ids")
                ),
                "unfinished_intent_ids": normalize_string_list(
                    payload.get("unfinished_intent_ids")
                ),
                "reason": to_non_empty_str(payload.get("reason")),
                "provider_failure_kind": to_non_empty_str(
                    payload.get("provider_failure_kind")
                ),
                "metadata": dict(payload.get("metadata") or {}),
            }
        )
    return normalized


def normalize_provider_events(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    normalized: list[dict[str, Any]] = []
    for item in value:
        payload = normalize_json_dict(item)
        if not payload:
            continue
        normalized.append(dict(payload))
    return normalized


def extract_turn_diagnostics_from_metadata(
    metadata: dict[str, Any],
) -> dict[str, Any]:
    turn_record = normalize_turn_record_payload(metadata.get("turn_record"))
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
    turn_outcome = to_non_empty_str(
        (turn_record or {}).get("turn_outcome")
        or metadata.get("turn_outcome")
        or turn_record_diagnostics.get("turn_outcome")
        or context_diagnostics.get("turn_outcome")
        or last_run_summary.get("turn_outcome")
    )
    termination_reason = to_non_empty_str(
        (turn_record or {}).get("termination_reason")
        or metadata.get("termination_reason")
        or metadata.get("completion_reason")
        or turn_record_diagnostics.get("termination_reason")
        or context_diagnostics.get("termination_reason")
        or last_run_summary.get("termination_reason")
        or last_run_summary.get("completion_reason")
    )
    metadata_completion_reason = to_non_empty_str(metadata.get("completion_reason"))
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
    protocol_path = to_non_empty_str(
        (turn_record or {}).get("protocol_path")
        or metadata.get("protocol_path")
        or turn_record_diagnostics.get("protocol_path")
        or context_diagnostics.get("protocol_path")
        or last_run_summary.get("protocol_path")
    )
    selected_tool_names = normalize_string_list(
        (turn_record or {}).get("selected_tool_names")
        or metadata.get("selected_tool_names")
        or turn_record_diagnostics.get("selected_tool_names")
        or context_diagnostics.get("selected_tool_names")
        or last_run_summary.get("selected_tool_names")
    )
    selected_skill_names = normalize_string_list(
        (turn_record or {}).get("selected_skill_names")
        or metadata.get("selected_skill_names")
        or turn_record_diagnostics.get("selected_skill_names")
        or context_diagnostics.get("selected_skill_names")
        or last_run_summary.get("selected_skill_names")
    )
    context_sources = normalize_context_sources(
        (turn_record or {}).get("context_sources")
        or metadata.get("context_sources")
        or turn_record_diagnostics.get("context_sources")
        or context_diagnostics.get("context_sources")
        or last_run_summary.get("context_sources")
    )
    contract_breach_type = to_non_empty_str(
        turn_record_metadata.get("contract_breach_type")
        or metadata.get("contract_breach_type")
        or turn_record_diagnostics.get("contract_breach_type")
        or context_diagnostics.get("contract_breach_type")
        or last_run_summary.get("contract_breach_type")
    )
    tool_planner = normalize_json_dict(
        (turn_record or {}).get("tool_planner")
        or metadata.get("tool_planner")
        or turn_record_diagnostics.get("tool_planner")
        or context_diagnostics.get("tool_planner")
        or last_run_summary.get("tool_planner")
    )
    tool_leak_detected = bool(
        turn_record_metadata.get("tool_leak_detected")
        or metadata.get("tool_leak_detected")
        or turn_record_diagnostics.get("tool_leak_detected")
        or context_diagnostics.get("tool_leak_detected")
        or last_run_summary.get("tool_leak_detected")
    )
    assistant_claimed_tool_call_without_tool_event = bool(
        turn_record_metadata.get("assistant_claimed_tool_call_without_tool_event")
        or (turn_record or {}).get("assistant_claimed_tool_call_without_tool_event")
        or metadata.get("assistant_claimed_tool_call_without_tool_event")
        or turn_record_diagnostics.get(
            "assistant_claimed_tool_call_without_tool_event"
        )
        or context_diagnostics.get("assistant_claimed_tool_call_without_tool_event")
        or last_run_summary.get("assistant_claimed_tool_call_without_tool_event")
    )
    unfinished_intents = normalize_string_list(
        turn_record_metadata.get("unfinished_intents")
        or metadata.get("unfinished_intents")
        or turn_record_diagnostics.get("unfinished_intents")
        or context_diagnostics.get("unfinished_intents")
        or last_run_summary.get("unfinished_intents")
    )
    leaked_tool_names = normalize_string_list(
        turn_record_metadata.get("leaked_tool_names")
        or metadata.get("leaked_tool_names")
        or turn_record_diagnostics.get("leaked_tool_names")
        or context_diagnostics.get("leaked_tool_names")
        or last_run_summary.get("leaked_tool_names")
    )
    recovered_via_retry_raw = (
        turn_record_metadata.get("recovered_via_retry")
        if "recovered_via_retry" in turn_record_metadata
        else (
            metadata.get("recovered_via_retry")
            if "recovered_via_retry" in metadata
            else (
                turn_record_diagnostics.get("recovered_via_retry")
                if "recovered_via_retry" in turn_record_diagnostics
                else (
                    context_diagnostics.get("recovered_via_retry")
                    if "recovered_via_retry" in context_diagnostics
                    else last_run_summary.get("recovered_via_retry")
                )
            )
        )
    )
    recovered_via_retry = (
        bool(recovered_via_retry_raw) if recovered_via_retry_raw is not None else None
    )
    last_tool_name = to_non_empty_str(
        (turn_record or {}).get("last_tool_name")
        or metadata.get("last_tool_name")
        or turn_record_diagnostics.get("last_tool_name")
        or context_diagnostics.get("last_tool_name")
        or last_run_summary.get("last_tool_name")
    )
    last_page_key = to_non_empty_str(
        (turn_record or {}).get("last_page_key")
        or metadata.get("last_page_key")
        or turn_record_diagnostics.get("last_page_key")
        or context_diagnostics.get("last_page_key")
        or last_run_summary.get("last_page_key")
    )
    last_page_op = to_non_empty_str(
        (turn_record or {}).get("last_page_op")
        or metadata.get("last_page_op")
        or turn_record_diagnostics.get("last_page_op")
        or context_diagnostics.get("last_page_op")
        or last_run_summary.get("last_page_op")
    )
    interrupted_stage = to_non_empty_str(
        (turn_record or {}).get("interrupted_stage")
        or metadata.get("interrupted_stage")
        or turn_record_diagnostics.get("interrupted_stage")
        or context_diagnostics.get("interrupted_stage")
        or last_run_summary.get("interrupted_stage")
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

    execution_path = to_non_empty_str(
        (turn_record or {}).get("execution_path")
        or metadata.get("execution_path")
        or turn_record_diagnostics.get("execution_path")
        or context_diagnostics.get("execution_path")
        or last_run_summary.get("execution_path")
    )
    active_intent_id = to_non_empty_str(
        (turn_record or {}).get("active_intent_id")
        or metadata.get("active_intent_id")
        or turn_record_diagnostics.get("active_intent_id")
        or context_diagnostics.get("active_intent_id")
        or last_run_summary.get("active_intent_id")
    )
    continuation_source = to_non_empty_str(
        (turn_record or {}).get("continuation_source")
        or metadata.get("continuation_source")
        or turn_record_diagnostics.get("continuation_source")
        or context_diagnostics.get("continuation_source")
        or last_run_summary.get("continuation_source")
    )
    conversation_outcome = to_non_empty_str(
        (turn_record or {}).get("conversation_outcome")
        or metadata.get("conversation_outcome")
        or turn_record_diagnostics.get("conversation_outcome")
        or context_diagnostics.get("conversation_outcome")
        or last_run_summary.get("conversation_outcome")
        or turn_outcome
    )
    intent_plan = normalize_intent_plan(
        (turn_record or {}).get("intent_plan")
        or metadata.get("intent_plan")
        or turn_record_diagnostics.get("intent_plan")
        or context_diagnostics.get("intent_plan")
        or last_run_summary.get("intent_plan")
    )
    budget = normalize_json_dict(
        (turn_record or {}).get("budget")
        or metadata.get("budget")
        or turn_record_diagnostics.get("budget")
        or context_diagnostics.get("budget")
        or last_run_summary.get("budget")
    )
    routing = (
        normalize_json_dict(
            metadata.get("routing")
            or turn_record_diagnostics.get("routing")
            or context_diagnostics.get("routing")
            or last_run_summary.get("routing")
        )
        or {}
    )
    candidate_tool_names = normalize_string_list(
        routing.get("candidate_tool_names")
        or metadata.get("candidate_tool_names")
        or turn_record_diagnostics.get("candidate_tool_names")
        or context_diagnostics.get("candidate_tool_names")
        or last_run_summary.get("candidate_tool_names")
    )
    recovery = (
        normalize_json_dict(
            metadata.get("recovery")
            or turn_record_diagnostics.get("recovery")
            or context_diagnostics.get("recovery")
            or last_run_summary.get("recovery")
        )
        or {}
    )
    retry_events = normalize_retry_events(
        recovery.get("retry_events")
        or metadata.get("retry_events")
        or turn_record_diagnostics.get("retry_events")
        or context_diagnostics.get("retry_events")
        or last_run_summary.get("retry_events")
    )
    partial_exit_reason = to_non_empty_str(
        recovery.get("partial_exit_reason")
        or metadata.get("partial_exit_reason")
        or turn_record_diagnostics.get("partial_exit_reason")
        or context_diagnostics.get("partial_exit_reason")
        or last_run_summary.get("partial_exit_reason")
    )
    failure_kind = to_non_empty_str(
        metadata.get("failure_kind")
        or turn_record_diagnostics.get("failure_kind")
        or (normalize_json_dict(metadata.get("failures")) or {}).get("failure_kind")
        or (normalize_json_dict(turn_record_diagnostics.get("failures")) or {}).get(
            "failure_kind"
        )
        or context_diagnostics.get("failure_kind")
        or last_run_summary.get("failure_kind")
    )
    provider_events = normalize_provider_events(
        metadata.get("provider_events")
        or (normalize_json_dict(metadata.get("failures")) or {}).get("provider_events")
        or turn_record_diagnostics.get("provider_events")
        or (normalize_json_dict(turn_record_diagnostics.get("failures")) or {}).get(
            "provider_events"
        )
        or context_diagnostics.get("provider_events")
        or last_run_summary.get("provider_events")
    )
    sync_rescue_raw = (
        turn_record_metadata.get("sync_rescue")
        if "sync_rescue" in turn_record_metadata
        else (
            metadata.get("sync_rescue")
            if "sync_rescue" in metadata
            else (
                turn_record_diagnostics.get("sync_rescue")
                if "sync_rescue" in turn_record_diagnostics
                else (
                    context_diagnostics.get("sync_rescue")
                    if "sync_rescue" in context_diagnostics
                    else last_run_summary.get("sync_rescue")
                )
            )
        )
    )
    sync_rescue = bool(sync_rescue_raw) if sync_rescue_raw is not None else None
    should_record_call_log_raw = (
        turn_record_metadata.get("should_record_call_log")
        if "should_record_call_log" in turn_record_metadata
        else (
            metadata.get("should_record_call_log")
            if "should_record_call_log" in metadata
            else (
                turn_record_diagnostics.get("should_record_call_log")
                if "should_record_call_log" in turn_record_diagnostics
                else (
                    context_diagnostics.get("should_record_call_log")
                    if "should_record_call_log" in context_diagnostics
                    else last_run_summary.get("should_record_call_log")
                )
            )
        )
    )
    should_record_call_log = (
        bool(should_record_call_log_raw) if should_record_call_log_raw is not None else None
    )
    budget_status = to_non_empty_str(
        (budget or {}).get("status")
        or metadata.get("budget_status")
        or context_diagnostics.get("budget_status")
        or last_run_summary.get("budget_status")
    )
    budget_exit_reason = to_non_empty_str(
        (budget or {}).get("exit_reason")
        or metadata.get("budget_exit_reason")
        or context_diagnostics.get("budget_exit_reason")
        or last_run_summary.get("budget_exit_reason")
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


def has_pending_state(
    *,
    tool_calls: list[dict[str, Any]] | None,
    metadata: dict[str, Any] | None,
) -> bool:
    if isinstance(metadata, dict) and (
        isinstance(metadata.get("pending_confirmation"), dict)
        or isinstance(metadata.get("pending_consent"), dict)
    ):
        return True

    for tc in tool_calls or []:
        if not isinstance(tc, dict):
            continue
        if isinstance(tc.get("pending_confirmation"), dict) or isinstance(
            tc.get("pending_consent"),
            dict,
        ):
            return True
    return False


def assistant_has_content_or_signal(
    message: dict[str, Any],
) -> bool:
    content = str(message.get("content") or "").strip()
    tool_calls = message.get("tool_calls")
    metadata = (
        dict(message.get("metadata") or {})
        if isinstance(message.get("metadata"), dict)
        else None
    )
    if content:
        return True
    if isinstance(tool_calls, list) and tool_calls:
        return True
    if has_pending_state(tool_calls=tool_calls, metadata=metadata):
        return True
    if isinstance(metadata, dict) and isinstance(metadata.get("action_buttons"), list):
        return len(metadata.get("action_buttons") or []) > 0
    return False


def sanitize_tool_messages(messages: list[ChatMessage]) -> list[ChatMessage]:
    if not messages:
        return messages

    result: list[ChatMessage] = []
    i = 0
    while i < len(messages):
        msg = messages[i]
        if msg.role == "tool":
            i += 1
            continue
        if msg.role != "assistant" or not msg.tool_calls:
            result.append(msg)
            i += 1
            continue

        tc_ids_expected = {tc.get("id", "") for tc in msg.tool_calls if tc.get("id")}
        if not tc_ids_expected:
            result.append(msg)
            i += 1
            continue

        collected_tool_ids: set[str] = set()
        round_msgs: list[ChatMessage] = [msg]
        j = i + 1
        while j < len(messages):
            next_msg = messages[j]
            if next_msg.role == "tool" and next_msg.tool_call_id:
                if next_msg.tool_call_id in tc_ids_expected:
                    collected_tool_ids.add(next_msg.tool_call_id)
                    round_msgs.append(next_msg)
                j += 1
                continue
            if next_msg.role in ("assistant", "user", "system"):
                break
            j += 1

        if collected_tool_ids == tc_ids_expected:
            result.extend(round_msgs)
        i = j

    return result


def enrich_tool_calls_for_persistence(
    tool_calls: list[dict[str, Any]] | None,
    tool_result_map: dict[str, ToolResult],
) -> list[dict[str, Any]] | None:
    if not tool_calls:
        return tool_calls

    enriched: list[dict[str, Any]] = []
    for tc in tool_calls:
        if not isinstance(tc, dict):
            continue
        next_tc = dict(tc)
        tc_id = str(next_tc.get("id") or "")
        tr = tool_result_map.get(tc_id) if tc_id else None
        if tr:
            if tr.display_name and not next_tc.get("display_name"):
                next_tc["display_name"] = tr.display_name
            if tr.summary and not next_tc.get("summary"):
                next_tc["summary"] = tr.summary
            if tr.summary_payload:
                existing_payload = (
                    next_tc.get("summary_payload")
                    if isinstance(next_tc.get("summary_payload"), dict)
                    else {}
                )
                next_tc["summary_payload"] = {
                    **existing_payload,
                    **tr.summary_payload,
                }
            if tr.result_link and not next_tc.get("result_link"):
                next_tc["result_link"] = tr.result_link
            if tr.error_type and not next_tc.get("error_type"):
                next_tc["error_type"] = tr.error_type
            if tr.duration_ms and not next_tc.get("duration_ms"):
                next_tc["duration_ms"] = tr.duration_ms
            next_tc["success"] = tr.success
        enriched.append(next_tc)

    return enriched


__all__ = [
    "assistant_has_content_or_signal",
    "copy_metadata",
    "enrich_tool_calls_for_persistence",
    "extract_turn_diagnostics_from_metadata",
    "has_pending_state",
    "normalize_context_sources",
    "normalize_intent_plan",
    "normalize_json_dict",
    "normalize_json_safe",
    "normalize_json_safe_dict",
    "normalize_provider_events",
    "normalize_retry_events",
    "normalize_string_list",
    "normalize_turn_record_payload",
    "sanitize_tool_messages",
    "to_non_empty_str",
]
