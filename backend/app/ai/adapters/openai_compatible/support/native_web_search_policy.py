"""Policy helpers for native Responses web search support."""

from __future__ import annotations

from collections.abc import Callable

from openai import APITimeoutError

from app.ai.exceptions import (
    ContentFilterError,
    ModelNotFoundError,
    ProviderConnectionError,
    ProviderTimeoutError,
)
from app.ai.web_search.types import (
    STATUS_POLICY_FILTERED,
    STATUS_TIMEOUT,
    STATUS_UNSUPPORTED,
    STATUS_UPSTREAM_ERROR,
)

NATIVE_WEB_SEARCH_MODEL_PREFIXES: tuple[str, ...] = (
    "gpt-4.1",
    "gpt-4o",
    "gpt-5",
    "o3",
    "o4",
)


def supports_native_web_search_model(model: str) -> bool:
    normalized = str(model or "").strip().lower()
    if not normalized:
        return False
    return any(normalized.startswith(prefix) for prefix in NATIVE_WEB_SEARCH_MODEL_PREFIXES)


def map_native_web_search_error(
    error: Exception,
    *,
    extract_status_code: Callable[[Exception], int | None],
) -> str:
    if isinstance(error, (APITimeoutError, ProviderTimeoutError)):
        return STATUS_TIMEOUT
    if isinstance(error, ContentFilterError):
        return STATUS_POLICY_FILTERED
    if isinstance(error, ModelNotFoundError):
        return STATUS_UNSUPPORTED
    if isinstance(error, ProviderConnectionError):
        return STATUS_UPSTREAM_ERROR

    status_code = extract_status_code(error)
    message = str(error).lower()
    if (
        "unsupported" in message
        or "not support" in message
        or "unknown parameter" in message
        or "invalid tool" in message
        or ("web_search" in message and "available" in message)
    ):
        return STATUS_UNSUPPORTED
    if (
        "content_filter" in message
        or "content policy" in message
        or "safety" in message
        or "policy" in message
    ):
        return STATUS_POLICY_FILTERED
    if status_code in {400, 404}:
        return STATUS_UNSUPPORTED
    if status_code == 408:
        return STATUS_TIMEOUT
    return STATUS_UPSTREAM_ERROR


__all__ = [
    "NATIVE_WEB_SEARCH_MODEL_PREFIXES",
    "map_native_web_search_error",
    "supports_native_web_search_model",
]
