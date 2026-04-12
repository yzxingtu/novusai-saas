"""Runtime semantics for protocol fallback and rescue decisions."""

from __future__ import annotations

from typing import Any

from app.ai.exceptions import (
    ProviderConnectionError,
    ProviderRateLimitError,
    ProviderTimeoutError,
)

RATE_LIMIT_ERROR_CLASS_NAMES = frozenset({"RateLimitError"})
TIMEOUT_ERROR_CLASS_NAMES = frozenset(
    {
        "APITimeoutError",
        "TimeoutException",
        "ReadTimeout",
        "WriteTimeout",
        "ConnectTimeout",
        "PoolTimeout",
    }
)
CONNECTION_ERROR_CLASS_NAMES = frozenset(
    {
        "APIConnectionError",
        "ConnectError",
    }
)


def extract_status_code(exc: BaseException) -> int | None:
    raw_status = getattr(exc, "status_code", None)
    if raw_status is None:
        response = getattr(exc, "response", None)
        raw_status = getattr(response, "status_code", None)
    try:
        return int(raw_status) if raw_status is not None else None
    except (TypeError, ValueError):
        return None


def fallback_block_reason(exc: BaseException) -> str | None:
    error_class_name = exc.__class__.__name__
    if error_class_name in RATE_LIMIT_ERROR_CLASS_NAMES:
        return "provider_rate_limit"
    if error_class_name in TIMEOUT_ERROR_CLASS_NAMES:
        return "provider_timeout"
    if error_class_name in CONNECTION_ERROR_CLASS_NAMES:
        return "provider_connection_error"
    if isinstance(exc, ProviderRateLimitError):
        return "provider_rate_limit"
    if isinstance(exc, ProviderTimeoutError):
        return "provider_timeout"
    if isinstance(exc, ProviderConnectionError):
        return "provider_connection_error"
    normalized_status = extract_status_code(exc)
    if normalized_status is None:
        return None
    if normalized_status == 429:
        return "provider_rate_limit"
    if normalized_status in {408, 504}:
        return "provider_timeout"
    return None


def should_skip_sync_rescue_after_stream_error(error: BaseException | None) -> bool:
    if error is None:
        return False
    return fallback_block_reason(error) in {
        "provider_rate_limit",
        "provider_timeout",
        "provider_connection_error",
    }


def should_cross_protocol_fallback_from_responses_error(
    *,
    capabilities: Any,
    error: BaseException,
    tools: list[dict[str, Any]] | None,
    tool_choice: str | None,
    use_responses_api: bool,
    fallback_switch_enabled: bool,
) -> bool:
    if not use_responses_api:
        return False
    if not fallback_switch_enabled:
        return False
    if not capabilities.is_cross_protocol_fallback_allowed(
        from_wire_api="responses",
        to_wire_api="chat_completions",
    ):
        return False
    if not tools and not tool_choice:
        return False
    if fallback_block_reason(error) is not None:
        return False
    status_code = extract_status_code(error)
    return bool(status_code is not None and 500 <= status_code < 600)


__all__ = [
    "CONNECTION_ERROR_CLASS_NAMES",
    "RATE_LIMIT_ERROR_CLASS_NAMES",
    "TIMEOUT_ERROR_CLASS_NAMES",
    "extract_status_code",
    "fallback_block_reason",
    "should_cross_protocol_fallback_from_responses_error",
    "should_skip_sync_rescue_after_stream_error",
]
