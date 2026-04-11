"""Legacy protocol fallback policy for OpenAI-compatible adapters."""

from __future__ import annotations

from typing import Protocol

import httpx
from openai import APIConnectionError, APITimeoutError, RateLimitError

from app.ai.exceptions import (
    AIGatewayError,
    ProviderConnectionError,
    ProviderRateLimitError,
    ProviderTimeoutError,
)


class CrossProtocolCapabilities(Protocol):
    def is_cross_protocol_fallback_allowed(
        self,
        *,
        from_wire_api: str,
        to_wire_api: str,
    ) -> bool: ...


def extract_status_code(error: Exception) -> int | None:
    raw_status = getattr(error, "status_code", None)
    if raw_status is None:
        response = getattr(error, "response", None)
        raw_status = getattr(response, "status_code", None)
    try:
        return int(raw_status) if raw_status is not None else None
    except (TypeError, ValueError):
        return None


def should_fallback_from_responses_error(
    *,
    capabilities: CrossProtocolCapabilities,
    error: Exception,
    tools: list[dict] | None,
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

    status_code = extract_status_code(error)
    if isinstance(error, (RateLimitError, ProviderRateLimitError)) or status_code == 429:
        return False

    if isinstance(
        error,
        (
            APIConnectionError,
            ProviderConnectionError,
            httpx.ConnectError,
        ),
    ):
        return False

    if isinstance(
        error,
        (
            APITimeoutError,
            ProviderTimeoutError,
            httpx.TimeoutException,
        ),
    ):
        return False

    if status_code in {408, 504}:
        return False

    if isinstance(error, AIGatewayError):
        return bool(status_code is not None and 500 <= status_code < 600)
    return bool(status_code is not None and 500 <= status_code < 600)


def should_skip_sync_rescue_after_stream_error(error: Exception | None) -> bool:
    if error is None:
        return False
    status_code = extract_status_code(error)
    if isinstance(error, (RateLimitError, ProviderRateLimitError)) or status_code == 429:
        return True
    if status_code in {408, 504}:
        return True
    return isinstance(
        error,
        (
            APIConnectionError,
            APITimeoutError,
            ProviderConnectionError,
            ProviderTimeoutError,
            httpx.ConnectError,
            httpx.TimeoutException,
        ),
    )


__all__ = [
    "extract_status_code",
    "should_fallback_from_responses_error",
    "should_skip_sync_rescue_after_stream_error",
]
