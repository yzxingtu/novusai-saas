"""Sanitizers for user-visible conversation payloads."""

from __future__ import annotations

from typing import Any

from app.ai.exceptions import looks_like_html_document_text
from app.core.i18n import _

_ASSISTANT_LEGACY_MESSAGE_KEYS = {
    "tool_calls",
}

_ASSISTANT_LEGACY_METADATA_KEYS = {
    "rag_sources",
    "thinking_content",
}


def _strip_trace_suffix(text: str) -> str:
    trace_marker = " [trace_id="
    if trace_marker in text:
        return text.split(trace_marker, 1)[0].strip()
    return text.strip()


def _normalize_public_error_text(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text or looks_like_html_document_text(text):
        return None
    cleaned = _strip_trace_suffix(text)
    return cleaned or None


def _mapped_public_error_message(error_type: str | None) -> str | None:
    normalized = str(error_type or "").strip().lower()
    return {
        "provider_bad_response": _("ai.request_failed"),
        "provider_http_5xx": _("ai.error.provider_server_error"),
        "provider_rate_limit": _("ai.error.provider_rate_limit"),
        "provider_timeout": _("ai.error.provider_timeout"),
        "provider_unavailable": _("ai.error.provider_connection"),
        "stream_fallback_error": _("ai.stream.error.fallback_failed"),
        "stream_interrupted": _("ai.stream.error.interrupted"),
    }.get(normalized)


def sanitize_conversation_last_error_payload(
    payload: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if not isinstance(payload, dict) or not payload:
        return payload

    last_error = dict(payload)
    error_type = str(last_error.get("error_type") or "").strip().lower()
    fallback_message = _mapped_public_error_message(error_type) or _(
        "common.server_error"
    )
    safe_friendly_message = (
        _normalize_public_error_text(last_error.get("friendly_message"))
        or _normalize_public_error_text(last_error.get("error_message"))
        or fallback_message
    )
    safe_debug_message = _normalize_public_error_text(
        last_error.get("debug_message")
    ) or _mapped_public_error_message(error_type)

    last_error["friendly_message"] = safe_friendly_message
    last_error["error_message"] = safe_debug_message or safe_friendly_message
    if safe_debug_message:
        last_error["debug_message"] = safe_debug_message
    else:
        last_error.pop("debug_message", None)
    return last_error


def sanitize_assistant_error_payload(
    payload: dict[str, Any] | None,
) -> dict[str, Any]:
    message_payload = dict(payload or {})
    if str(message_payload.get("role") or "") != "assistant":
        return message_payload

    raw_metadata = message_payload.get("metadata")
    if not isinstance(raw_metadata, dict):
        return message_payload

    metadata_payload = dict(raw_metadata)
    if metadata_payload.get("error") is True:
        error_type = str(metadata_payload.get("error_type") or "").strip().lower()
        fallback_message = _mapped_public_error_message(error_type) or _(
            "common.server_error"
        )
        safe_message = (
            _normalize_public_error_text(metadata_payload.get("error_message"))
            or _normalize_public_error_text(message_payload.get("content"))
            or fallback_message
        )
        safe_debug_message = _normalize_public_error_text(
            metadata_payload.get("error_debug_message")
        ) or _mapped_public_error_message(error_type)
        safe_raw_message = (
            _normalize_public_error_text(metadata_payload.get("raw_error_message"))
            or safe_debug_message
            or safe_message
        )
        metadata_payload["error_message"] = safe_message
        metadata_payload["raw_error_message"] = safe_raw_message
        if safe_debug_message:
            metadata_payload["error_debug_message"] = safe_debug_message
        else:
            metadata_payload.pop("error_debug_message", None)
        if looks_like_html_document_text(message_payload.get("content")):
            message_payload["content"] = safe_message

    if metadata_payload:
        message_payload["metadata"] = metadata_payload
    else:
        message_payload.pop("metadata", None)
    return message_payload


def strip_assistant_legacy_turn_projection_fields(
    payload: dict[str, Any] | None,
) -> dict[str, Any]:
    message_payload = sanitize_assistant_error_payload(payload)
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
