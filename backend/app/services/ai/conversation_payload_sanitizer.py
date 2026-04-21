"""Sanitizers for user-visible conversation payloads."""

from __future__ import annotations

from typing import Any

_ASSISTANT_LEGACY_MESSAGE_KEYS = {
    "tool_calls",
}

_ASSISTANT_LEGACY_METADATA_KEYS = {
    "rag_sources",
    "thinking_content",
}


def strip_assistant_legacy_turn_projection_fields(
    payload: dict[str, Any] | None,
) -> dict[str, Any]:
    message_payload = dict(payload or {})
    if str(message_payload.get("role") or "") != "assistant":
        return message_payload

    for key in _ASSISTANT_LEGACY_MESSAGE_KEYS:
        message_payload.pop(key, None)

    raw_metadata = message_payload.get("metadata")
    if not isinstance(raw_metadata, dict):
        return message_payload

    metadata_payload = dict(raw_metadata)
    for key in _ASSISTANT_LEGACY_METADATA_KEYS:
        metadata_payload.pop(key, None)

    if metadata_payload:
        message_payload["metadata"] = metadata_payload
    else:
        message_payload.pop("metadata", None)
    return message_payload
