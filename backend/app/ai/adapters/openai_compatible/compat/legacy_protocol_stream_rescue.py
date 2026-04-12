"""Legacy stream rescue helpers for chat.completions execution."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any

from app.ai.types import ChatChunk, ChatMessage
from app.core.logging import LogManager

from .legacy_protocol_policy import should_skip_sync_rescue_after_stream_error

if TYPE_CHECKING:
    from .legacy_context_builder import LegacyEntrypointGuardSnapshot
    from .legacy_protocol_execution_helpers import LegacyCompatAdapterProtocol

logger = LogManager.get_logger("ai")


async def stream_chat_completions_with_sync_rescue(
    *,
    adapter: LegacyCompatAdapterProtocol,
    request_params: dict[str, Any],
    sync_request_params: dict[str, Any],
    messages: list[ChatMessage],
    model: str,
    rescue_reason: str,
) -> AsyncIterator[ChatChunk]:
    """Rescue empty or broken chat.completions streams with a sync request."""

    emitted_fallback_blocking_chunk = False
    stream_error: Exception | None = None

    try:
        async for chunk in adapter._stream_chat_via_chat_completions(
            request_params=request_params,
            model=model,
            fallback_to_responses=False,
        ):
            if adapter._stream_chunk_blocks_fallback(chunk):
                emitted_fallback_blocking_chunk = True
            yield chunk
    except Exception as exc:  # noqa: BLE001
        if emitted_fallback_blocking_chunk:
            raise
        stream_error = exc

    if emitted_fallback_blocking_chunk:
        return

    if should_skip_sync_rescue_after_stream_error(stream_error):
        logger.warning(
            "Skip sync rescue after chat.completions stream failure: model={} reason={} stream_error_type={} stream_error={}",
            model,
            rescue_reason,
            type(stream_error).__name__ if stream_error is not None else "",
            str(stream_error) if stream_error is not None else "",
        )
        raise stream_error

    logger.warning(
        "chat.completions stream had no meaningful chunk, rescue with sync chat: model={} reason={} stream_error_type={} stream_error={}",
        model,
        rescue_reason,
        type(stream_error).__name__ if stream_error is not None else "",
        str(stream_error) if stream_error is not None else "",
    )
    try:
        response = await adapter._chat_via_chat_completions(
            request_params=sync_request_params,
            messages=messages,
            model=model,
            fallback_to_responses=False,
        )
        yield adapter._chat_response_to_stream_chunk(response)
    except Exception as rescue_error:
        logger.error(
            "Sync rescue failed after stream failure: model={} stream_error={} rescue_error={}",
            model,
            str(stream_error) if stream_error is not None else "None",
            str(rescue_error),
        )
        raise stream_error if stream_error is not None else rescue_error


def build_chat_completions_stream_iterator(
    *,
    adapter: LegacyCompatAdapterProtocol,
    request_params: dict[str, Any],
    sync_request_params: dict[str, Any],
    messages: list[ChatMessage],
    model: str,
    guard_snapshot: LegacyEntrypointGuardSnapshot,
    rescue_reason: str,
) -> AsyncIterator[ChatChunk]:
    if guard_snapshot.runtime_disable_sync_rescue:
        return adapter._stream_chat_via_chat_completions(
            request_params=request_params,
            model=model,
            fallback_to_responses=False,
        )
    return stream_chat_completions_with_sync_rescue(
        adapter=adapter,
        request_params=request_params,
        sync_request_params=sync_request_params,
        messages=messages,
        model=model,
        rescue_reason=rescue_reason,
    )


__all__ = [
    "build_chat_completions_stream_iterator",
    "stream_chat_completions_with_sync_rescue",
]
