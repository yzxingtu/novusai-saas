"""Legacy protocol execution bridge for OpenAI-compatible adapters."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, Protocol

from app.ai.adapters.openai_compatible.compat.legacy_protocol_policy import (
    extract_status_code,
    should_fallback_from_responses_error,
    should_skip_sync_rescue_after_stream_error,
)
from app.ai.types import ChatChunk, ChatMessage, ChatResponse
from app.core.logging import LogManager

logger = LogManager.get_logger("ai")

_RESPONSES_TOOL_FALLBACK_DISABLED = {"0", "false", "no", "off"}


class LegacyCompatAdapterProtocol(Protocol):
    provider_config: dict[str, Any]
    protocol_capabilities: Any

    async def _chat_via_responses(self, **kwargs: Any) -> ChatResponse: ...

    async def _stream_chat_via_responses(
        self,
        **kwargs: Any,
    ) -> AsyncIterator[ChatChunk]: ...

    async def _chat_via_chat_completions(
        self,
        *,
        request_params: dict[str, Any],
        messages: list[ChatMessage],
        model: str,
        fallback_to_responses: bool = True,
        responses_kwargs: dict[str, Any] | None = None,
    ) -> ChatResponse: ...

    async def _stream_chat_via_chat_completions(
        self,
        *,
        request_params: dict[str, Any],
        model: str,
        fallback_to_responses: bool = True,
        responses_kwargs: dict[str, Any] | None = None,
    ) -> AsyncIterator[ChatChunk]: ...

    @staticmethod
    def _stream_chunk_blocks_fallback(chunk: ChatChunk) -> bool: ...

    def _chat_response_to_stream_chunk(self, response: ChatResponse) -> ChatChunk: ...


def responses_tool_call_fallback_enabled(
    provider_config: dict[str, Any] | None,
) -> bool:
    raw_value = (provider_config or {}).get("responses_tool_call_fallback_enabled")
    if raw_value is None:
        return True
    if isinstance(raw_value, bool):
        return raw_value
    return str(raw_value).strip().lower() not in _RESPONSES_TOOL_FALLBACK_DISABLED


def log_responses_tool_call_fallback(
    *,
    model: str,
    stream: bool,
    error: Exception,
) -> None:
    logger.warning(
        "Responses tool call failed, fallback to chat.completions: model={} stream={} error_type={} status_code={} error={}",
        model,
        stream,
        type(error).__name__,
        extract_status_code(error),
        str(error),
    )


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


async def execute_legacy_chat(
    *,
    adapter: LegacyCompatAdapterProtocol,
    execution_state: dict[str, str],
    messages: list[ChatMessage],
    model: str,
    tools: list[dict] | None,
    tool_choice: str | None,
    use_responses_api: bool,
    runtime_disable_cross_protocol_fallback: bool,
    request_params: dict[str, Any],
    responses_kwargs: dict[str, Any],
) -> ChatResponse:
    """Run the legacy smart chat path without keeping policy inside the adapter."""

    if use_responses_api:
        try:
            return await adapter._chat_via_responses(**responses_kwargs)
        except Exception as responses_error:
            if (
                not runtime_disable_cross_protocol_fallback
                and should_fallback_from_responses_error(
                    capabilities=adapter.protocol_capabilities,
                    error=responses_error,
                    tools=tools,
                    tool_choice=tool_choice,
                    use_responses_api=use_responses_api,
                    fallback_switch_enabled=responses_tool_call_fallback_enabled(
                        adapter.provider_config,
                    ),
                )
            ):
                log_responses_tool_call_fallback(
                    model=model,
                    stream=False,
                    error=responses_error,
                )
                execution_state["active_endpoint_path"] = "chat/completions"
                execution_state["active_wire_api"] = "chat_completions"
                return await adapter._chat_via_chat_completions(
                    request_params=request_params,
                    messages=messages,
                    model=model,
                    fallback_to_responses=False,
                )
            raise

    return await adapter._chat_via_chat_completions(
        request_params=request_params,
        messages=messages,
        model=model,
        fallback_to_responses=not runtime_disable_cross_protocol_fallback,
        responses_kwargs=(
            responses_kwargs if not runtime_disable_cross_protocol_fallback else None
        ),
    )


async def execute_legacy_stream(
    *,
    adapter: LegacyCompatAdapterProtocol,
    execution_state: dict[str, str],
    messages: list[ChatMessage],
    model: str,
    tools: list[dict] | None,
    tool_choice: str | None,
    use_responses_api: bool,
    runtime_disable_cross_protocol_fallback: bool,
    runtime_disable_sync_rescue: bool,
    request_params: dict[str, Any],
    sync_request_params: dict[str, Any],
    responses_kwargs: dict[str, Any],
) -> AsyncIterator[ChatChunk]:
    """Run the legacy smart stream path without keeping policy inside the adapter."""

    if use_responses_api:
        responses_stream_emitted_fallback_blocking_chunk = False
        try:
            async for chunk in adapter._stream_chat_via_responses(**responses_kwargs):
                if adapter._stream_chunk_blocks_fallback(chunk):
                    responses_stream_emitted_fallback_blocking_chunk = True
                yield chunk
            return
        except Exception as responses_error:
            if (
                not responses_stream_emitted_fallback_blocking_chunk
                and not runtime_disable_cross_protocol_fallback
                and should_fallback_from_responses_error(
                    capabilities=adapter.protocol_capabilities,
                    error=responses_error,
                    tools=tools,
                    tool_choice=tool_choice,
                    use_responses_api=use_responses_api,
                    fallback_switch_enabled=responses_tool_call_fallback_enabled(
                        adapter.provider_config,
                    ),
                )
            ):
                log_responses_tool_call_fallback(
                    model=model,
                    stream=True,
                    error=responses_error,
                )
                execution_state["active_endpoint_path"] = "chat/completions"
                execution_state["active_wire_api"] = "chat_completions"
                stream_iterator = (
                    adapter._stream_chat_via_chat_completions(
                        request_params=request_params,
                        model=model,
                        fallback_to_responses=False,
                    )
                    if runtime_disable_sync_rescue
                    else stream_chat_completions_with_sync_rescue(
                        adapter=adapter,
                        request_params=request_params,
                        sync_request_params=sync_request_params,
                        messages=messages,
                        model=model,
                        rescue_reason="responses_fallback",
                    )
                )
                async for chunk in stream_iterator:
                    yield chunk
                return
            if responses_stream_emitted_fallback_blocking_chunk:
                logger.warning(
                    "Responses stream failed after visible/tool chunk; skip cross-protocol fallback: model={} error_type={} error={}",
                    model,
                    type(responses_error).__name__,
                    str(responses_error),
                )
            raise

    stream_iterator = (
        adapter._stream_chat_via_chat_completions(
            request_params=request_params,
            model=model,
            fallback_to_responses=False,
        )
        if runtime_disable_sync_rescue
        else stream_chat_completions_with_sync_rescue(
            adapter=adapter,
            request_params=request_params,
            sync_request_params=sync_request_params,
            messages=messages,
            model=model,
            rescue_reason="chat_completions_primary",
        )
    )
    async for chunk in stream_iterator:
        yield chunk


__all__ = [
    "execute_legacy_chat",
    "execute_legacy_stream",
    "log_responses_tool_call_fallback",
    "responses_tool_call_fallback_enabled",
    "stream_chat_completions_with_sync_rescue",
]
