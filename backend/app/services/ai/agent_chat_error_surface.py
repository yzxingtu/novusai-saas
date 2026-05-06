"""
Agent chat stream error-surface helpers.
"""

from __future__ import annotations

from typing import Any

from app.ai.exceptions import (
    ProviderAuthError,
    extract_provider_error_message,
    looks_like_html_document_text,
)
from app.core.i18n import _
from app.core.response import get_current_trace_id

STREAM_INTERRUPTION_TOKENS = (
    "cancellederror",
    "cancelled via cancel scope",
    "cancel scope",
    "client disconnected",
    "disconnect",
    "connection reset",
    "broken pipe",
)


def strip_stream_error_trace(error: Any) -> str:
    text = str(error or "").strip()
    trace_marker = " [trace_id="
    if trace_marker in text:
        return text.split(trace_marker, 1)[0].strip()
    return text


def _resolve_safe_provider_message(error: Any) -> str:
    provider_message = strip_stream_error_trace(
        extract_provider_error_message(error) or ""
    )
    if not provider_message or looks_like_html_document_text(provider_message):
        return ""
    return provider_message


def _mapped_provider_failure_public_detail(failure_kind: str) -> str | None:
    return {
        "provider_auth": _("ai.error.provider_auth"),
        "provider_auth_error": _("ai.error.provider_auth"),
        "provider_bad_response": _("ai.request_failed"),
        "provider_http_5xx": _("ai.error.provider_server_error"),
        "provider_rate_limit": _("ai.error.provider_rate_limit"),
        "provider_timeout": _("ai.error.provider_timeout"),
        "provider_unavailable": _("ai.error.provider_connection"),
    }.get(failure_kind)


def _should_prefer_mapped_provider_message(failure_kind: str) -> bool:
    return failure_kind in {"provider_timeout", "provider_unavailable"}


def friendly_stream_error_text(
    error: Any,
    *,
    failure_kind: str | None = None,
) -> str:
    sanitized_error = strip_stream_error_trace(error)
    lowered_error = sanitized_error.lower()
    if any(token in lowered_error for token in STREAM_INTERRUPTION_TOKENS):
        return _("ai.stream.error.interrupted")

    normalized_kind = str(failure_kind or "").strip().lower()
    if isinstance(error, ProviderAuthError):
        return _("ai.error.provider_auth")
    if normalized_kind.startswith("provider_"):
        mapped_detail = _mapped_provider_failure_public_detail(normalized_kind)
        if normalized_kind in {"provider_auth", "provider_auth_error"}:
            return mapped_detail or _("ai.error.provider_auth")
        if mapped_detail and _should_prefer_mapped_provider_message(normalized_kind):
            return mapped_detail
        provider_message = _resolve_safe_provider_message(error)
        if provider_message:
            return provider_message
        if (
            sanitized_error
            and sanitized_error != _("common.server_error")
            and not looks_like_html_document_text(sanitized_error)
        ):
            return sanitized_error
        if mapped_detail:
            return mapped_detail
        return _("ai.request_failed")

    if "fallback" in lowered_error:
        return _("ai.stream.error.fallback_failed")

    return _("common.server_error")


def friendly_stream_error_detail(
    error: Any,
    *,
    failure_kind: str | None = None,
) -> str | None:
    normalized_kind = str(failure_kind or "").strip().lower()
    if isinstance(error, ProviderAuthError):
        return _("ai.error.provider_auth")
    if normalized_kind in {"provider_auth", "provider_auth_error"}:
        return _("ai.error.provider_auth")
    sanitized_error = strip_stream_error_trace(error)
    provider_message = _resolve_safe_provider_message(error)
    if normalized_kind.startswith("provider_") and provider_message:
        return provider_message

    mapped_detail = _mapped_provider_failure_public_detail(normalized_kind)
    if mapped_detail:
        return mapped_detail

    lowered_error = sanitized_error.lower()
    if any(token in lowered_error for token in STREAM_INTERRUPTION_TOKENS):
        return None
    if "fallback" in lowered_error:
        return _("ai.stream.error.fallback_failed")
    if (
        sanitized_error
        and sanitized_error != _("common.server_error")
        and not looks_like_html_document_text(sanitized_error)
    ):
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
        if any(token in lowered_error for token in STREAM_INTERRUPTION_TOKENS):
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
