"""Error/payload helpers extracted from stream handler."""

from __future__ import annotations

from typing import Any

from app.ai.exceptions import (
    AIGatewayError,
    ProviderAuthError,
    ProviderConnectionError,
    ProviderError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    extract_provider_error_message,
    looks_like_html_document_text,
)
from app.core.i18n import _
from app.middleware.trace import trace_id_var

STREAM_INTERRUPTION_TOKENS = (
    "cancellederror",
    "cancelled via cancel scope",
    "cancel scope",
    "client disconnected",
    "disconnect",
    "connection reset",
    "broken pipe",
)


def trace_payload(data: dict[str, Any]) -> dict[str, Any]:
    trace_id = trace_id_var.get()
    if trace_id and "trace_id" not in data:
        return {**data, "trace_id": trace_id}
    return data


def strip_error_trace_suffix(text: str) -> str:
    trace_marker = " [trace_id="
    if trace_marker in text:
        return text.split(trace_marker, 1)[0].strip()
    return text.strip()


def is_stream_interruption_error(error: BaseException) -> bool:
    lowered_error = strip_error_trace_suffix(str(error or "")).lower()
    return any(token in lowered_error for token in STREAM_INTERRUPTION_TOKENS)


def resolve_provider_public_error_message(error: BaseException) -> str:
    provider_message = strip_error_trace_suffix(extract_provider_error_message(error) or "")
    if provider_message and not looks_like_html_document_text(provider_message):
        return provider_message

    if isinstance(error, ProviderRateLimitError):
        return _("ai.error.provider_rate_limit")
    if isinstance(error, ProviderTimeoutError):
        return _("ai.error.provider_timeout")
    if isinstance(error, ProviderConnectionError):
        return _("ai.error.provider_connection")
    if isinstance(error, ProviderAuthError):
        return _("ai.error.provider_auth")
    if isinstance(error, ProviderError):
        status_code = int(getattr(error, "status_code", 0) or 0)
        if 500 <= status_code < 600:
            return _("ai.error.provider_server_error")
        return _("ai.request_failed")
    if isinstance(error, AIGatewayError):
        gateway_message = strip_error_trace_suffix(str(error or ""))
        if gateway_message and not looks_like_html_document_text(gateway_message):
            return gateway_message
    return ""


def resolve_stream_public_error_message(error: BaseException) -> str:
    if is_stream_interruption_error(error):
        return _("ai.stream.error.interrupted")

    provider_message = resolve_provider_public_error_message(error)
    if provider_message:
        return provider_message

    return _("common.server_error")
