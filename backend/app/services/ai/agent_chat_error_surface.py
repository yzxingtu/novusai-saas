"""
Agent chat stream error-surface helpers.
"""

from __future__ import annotations

from typing import Any

from app.ai.exceptions import extract_provider_error_message
from app.core.i18n import _
from app.core.response import get_current_trace_id


def strip_stream_error_trace(error: Any) -> str:
    text = str(error or "").strip()
    trace_marker = " [trace_id="
    if trace_marker in text:
        return text.split(trace_marker, 1)[0].strip()
    return text


def friendly_stream_error_text(
    error: Any,
    *,
    failure_kind: str | None = None,
) -> str:
    sanitized_error = strip_stream_error_trace(error)
    lowered_error = sanitized_error.lower()
    if any(
        token in lowered_error
        for token in (
            "cancellederror",
            "cancelled via cancel scope",
            "cancel scope",
            "client disconnected",
            "disconnect",
            "connection reset",
            "broken pipe",
        )
    ):
        return _("ai.stream.error.interrupted")

    normalized_kind = str(failure_kind or "").strip().lower()
    if normalized_kind.startswith("provider_"):
        provider_message = strip_stream_error_trace(
            extract_provider_error_message(error) or sanitized_error
        )
        if provider_message:
            return provider_message

    if "fallback" in lowered_error:
        return _("ai.stream.error.fallback_failed")

    return _("common.server_error")


def friendly_stream_error_detail(
    error: Any,
    *,
    failure_kind: str | None = None,
) -> str | None:
    normalized_kind = str(failure_kind or "").strip().lower()
    provider_message = strip_stream_error_trace(
        extract_provider_error_message(error) or ""
    )
    if normalized_kind.startswith("provider_") and provider_message:
        return provider_message

    mapped_detail = {
        "provider_bad_response": _("ai.request_failed"),
        "provider_http_5xx": _("ai.error.provider_server_error"),
        "provider_rate_limit": _("ai.error.provider_rate_limit"),
        "provider_timeout": _("ai.error.provider_timeout"),
        "provider_unavailable": _("ai.error.provider_connection"),
    }.get(normalized_kind)
    if mapped_detail:
        return mapped_detail

    sanitized_error = strip_stream_error_trace(error)
    lowered_error = sanitized_error.lower()
    if any(
        token in lowered_error
        for token in (
            "cancellederror",
            "cancelled via cancel scope",
            "cancel scope",
            "client disconnected",
            "disconnect",
            "connection reset",
            "broken pipe",
        )
    ):
        return None
    if "fallback" in lowered_error:
        return _("ai.stream.error.fallback_failed")
    if sanitized_error and sanitized_error != _("common.server_error"):
        return sanitized_error
    return None


def build_stream_error_display(
    error: Any,
    *,
    failure_kind: str | None = None,
) -> dict[str, Any]:
    lowered_error = strip_stream_error_trace(error).lower()
    error_type = str(failure_kind or "").strip()
    if error_type == "none":
        error_type = ""
    if not error_type:
        if any(
            token in lowered_error
            for token in (
                "cancellederror",
                "cancelled via cancel scope",
                "cancel scope",
                "client disconnected",
                "disconnect",
                "connection reset",
                "broken pipe",
            )
        ):
            error_type = "stream_interrupted"
        elif "fallback" in lowered_error:
            error_type = "stream_fallback_error"
        else:
            error_type = "stream_execution_error"

    return {
        "debug_message": friendly_stream_error_detail(
            error,
            failure_kind=failure_kind,
        ),
        "error_only": True,
        "error_type": error_type,
        "message": friendly_stream_error_text(
            error,
            failure_kind=failure_kind,
        ),
        "trace_id": get_current_trace_id(),
    }

