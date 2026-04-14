"""
Conversation diagnostics projector helpers.
"""

from __future__ import annotations

from typing import Any

from app.ai.json_safe import normalize_json_safe as _normalize_json_safe
from app.ai.json_safe import normalize_json_safe_dict as _normalize_json_safe_dict
from app.ai.tools.types import ToolResult
from app.ai.types import ChatMessage
from app.services.ai.conversation_diagnostics_projector_support_diagnostics import (
    extract_turn_diagnostics_from_metadata,
)


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
