"""Lower-level usage and timeout helpers for OpenAI-compatible adapters."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

from app.ai.types import ChatChunk, ChatResponse
from app.core.logging import LogManager

logger = LogManager.get_logger("ai")

RESPONSES_USAGE_RETRIEVE_TIMEOUT_SECONDS = 2.0


def _build_usage_retrieve_client(client: Any) -> Any:
    """Prefer a no-retry, short-timeout client for post-stream usage backfill."""
    with_options = getattr(client, "with_options", None)
    if not callable(with_options):
        return client
    try:
        return with_options(
            timeout=RESPONSES_USAGE_RETRIEVE_TIMEOUT_SECONDS,
            max_retries=0,
        )
    except TypeError:
        return client


async def retrieve_responses_usage(
    *,
    client: Any,
    response_id: str | None,
    extract_usage_tokens: Callable[[Any], tuple[int | None, int | None, int | None]],
) -> tuple[int | None, int | None, int | None]:
    """Fallback when a terminal Responses stream event omitted usage."""
    if not response_id:
        return (None, None, None)
    usage_client = _build_usage_retrieve_client(client)
    retrieve = getattr(getattr(usage_client, "responses", None), "retrieve", None)
    if not callable(retrieve):
        return (None, None, None)
    try:
        response = await retrieve(response_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Responses usage retrieve failed: response_id={} timeout_seconds={} error={}",
            response_id,
            RESPONSES_USAGE_RETRIEVE_TIMEOUT_SECONDS,
            str(exc),
        )
        return (None, None, None)

    return extract_usage_tokens(getattr(response, "usage", None))


async def next_stream_event_with_timeout(
    stream: Any,
    *,
    timeout_seconds: float | None,
    model: str,
    wire_api: str,
    timeout_error_factory: Callable[[], Exception],
) -> Any:
    """Read the next stream event while normalizing timeout behavior."""
    if timeout_seconds is None:
        return await anext(stream)
    try:
        return await asyncio.wait_for(
            anext(stream),
            timeout=timeout_seconds,
        )
    except asyncio.TimeoutError as exc:
        logger.warning(
            "Provider stream timeout: model={} wire_api={} timeout_seconds={}",
            model,
            wire_api,
            timeout_seconds,
        )
        raise timeout_error_factory() from exc


def build_terminal_stream_chunk(response: ChatResponse) -> ChatChunk:
    """Convert a sync response into one terminal stream chunk."""
    finish_reason = response.finish_reason
    if not finish_reason:
        finish_reason = (
            "tool_calls"
            if (response.tool_calls or response.message.tool_calls)
            else "stop"
        )
    return ChatChunk(
        delta=response.message.content or "",
        reasoning_delta=response.message.reasoning_content or "",
        role=response.message.role,
        finish_reason=finish_reason,
        input_tokens=response.input_tokens,
        output_tokens=response.output_tokens,
        total_tokens=response.total_tokens,
        tool_calls=response.tool_calls or response.message.tool_calls,
        metadata=dict(response.metadata or {}),
    )


__all__ = [
    "build_terminal_stream_chunk",
    "next_stream_event_with_timeout",
    "retrieve_responses_usage",
]
