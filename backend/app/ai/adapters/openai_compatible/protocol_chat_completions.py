"""chat.completions protocol helpers for OpenAI-compatible adapters."""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any, Protocol

from app.ai.adapters.openai_compatible.support.client_options import (
    with_client_retry_override,
)
from app.ai.adapters.openai_compatible.support.protocol_chat_completions_helpers import (
    convert_chat_chunk,
    convert_chat_response,
    is_salvageable_raw_text_chat_response,
    responses_fallback_context_ok,
    should_fallback_to_responses,
)
from app.ai.types import ChatChunk, ChatMessage, ChatResponse
from app.core.logging import LogManager

logger = LogManager.get_logger("ai")


class ChatCompletionsAdapterProtocol(Protocol):
    client: Any
    protocol_capabilities: Any
    _chat_completions_v1_retry_base_url: str | None

    def _use_responses_api(self) -> bool: ...

    def _get_chat_completions_v1_retry_client(self) -> Any: ...

    def _log_upstream_request(
        self,
        *,
        endpoint_path: str,
        model: str,
        stream: bool,
        wire_api: str | None = None,
    ) -> None: ...

    def _extract_usage_tokens(
        self,
        usage: Any,
    ) -> tuple[int | None, int | None, int | None]: ...

    async def _chat_via_responses(self, **kwargs: Any) -> ChatResponse: ...

    async def _stream_chat_via_responses(
        self,
        **kwargs: Any,
    ) -> AsyncIterator[ChatChunk]: ...

    async def _next_stream_event_with_timeout(
        self,
        stream: Any,
        *,
        timeout_seconds: float | None,
        model: str,
        wire_api: str,
    ) -> Any: ...


def _looks_like_html_document(payload: str) -> bool:
    preview = str(payload or "").lstrip().lower()
    return (
        preview.startswith("<!doctype")
        or preview.startswith("<html")
        or preview.startswith("<head")
        or preview.startswith("<body")
    )


async def retry_chat_completions_with_v1_if_needed(
    *,
    adapter: ChatCompletionsAdapterProtocol,
    payload: Any,
    request_params: dict[str, Any],
    model: str,
    stream: bool,
) -> Any:
    if not (isinstance(payload, str) and _looks_like_html_document(payload)):
        return payload

    retry_client = adapter._get_chat_completions_v1_retry_client()
    retry_base_url = adapter._chat_completions_v1_retry_base_url
    if retry_client is None or not retry_base_url:
        return payload

    logger.warning(
        "chat.completions root endpoint returned HTML; retry with /v1 endpoint: model={} retry_base_url={} stream={}",
        model,
        retry_base_url,
        stream,
    )
    return await retry_client.chat.completions.create(**request_params)


async def execute_chat_via_chat_completions(
    *,
    adapter: ChatCompletionsAdapterProtocol,
    request_params: dict[str, Any],
    messages: list[ChatMessage],
    model: str,
    fallback_to_responses: bool = True,
    responses_kwargs: dict[str, Any] | None = None,
) -> ChatResponse:
    request_params = dict(request_params)
    client_max_retries = request_params.pop("_client_max_retries", None)
    effective_model = str(request_params.get("model") or model)
    adapter._log_upstream_request(
        endpoint_path="chat/completions",
        model=effective_model,
        stream=False,
        wire_api="chat_completions",
    )
    logger.info("Chat request: model={} messages={}", effective_model, len(messages))

    client = with_client_retry_override(
        adapter.client,
        max_retries=client_max_retries,
    )
    response = await client.chat.completions.create(**request_params)
    response = await retry_chat_completions_with_v1_if_needed(
        adapter=adapter,
        payload=response,
        request_params=request_params,
        model=effective_model,
        stream=False,
    )

    fallback_candidate = False
    if fallback_to_responses:
        fallback_candidate = should_fallback_to_responses(
            use_responses_api=adapter._use_responses_api(),
            cross_protocol_fallback_allowed=adapter.protocol_capabilities.is_cross_protocol_fallback_allowed(
                from_wire_api="chat_completions",
                to_wire_api="responses",
            ),
            payload=response,
        )

    if fallback_candidate:
        if responses_fallback_context_ok(responses_kwargs):
            logger.warning(
                "Chat response missing choices; fallback to responses API: model={} response_type={}",
                model,
                type(response).__name__,
            )
            return await adapter._chat_via_responses(**(responses_kwargs or {}))
        logger.warning(
            "Chat response looked like responses payload but fallback context missing; skip fallback: model={} response_type={}",
            model,
            type(response).__name__,
        )

    if is_salvageable_raw_text_chat_response(response):
        logger.warning(
            "Chat response returned raw text; coerce to assistant message: model={} response_type={}",
            model,
            type(response).__name__,
        )
        return ChatResponse(
            message=ChatMessage(role="assistant", content=response.strip()),
            model=model,
            finish_reason="stop",
            metadata={
                "protocol_path": "chat_completions",
                "response_shape": "raw_text",
            },
        )

    if isinstance(response, str):
        logger.error(
            "Chat response returned unsalvageable string payload: model={} preview={}",
            model,
            response[:200],
        )
        raise ValueError(f"Upstream returned invalid string response: {response[:100]}")

    return convert_chat_response(adapter=adapter, response=response, model=model)


async def execute_stream_chat_via_chat_completions(
    *,
    adapter: ChatCompletionsAdapterProtocol,
    request_params: dict[str, Any],
    model: str,
    fallback_to_responses: bool = True,
    responses_kwargs: dict[str, Any] | None = None,
    aclose_stream: Callable[[Any], Awaitable[None]],
    normalize_timeout: Callable[[Any], float | None],
) -> AsyncIterator[ChatChunk]:
    request_params = dict(request_params)
    client_max_retries = request_params.pop("_client_max_retries", None)
    effective_model = str(request_params.get("model") or model)
    adapter._log_upstream_request(
        endpoint_path="chat/completions",
        model=effective_model,
        stream=True,
        wire_api="chat_completions",
    )
    logger.info("Stream chat request: model={}", effective_model)

    client = with_client_retry_override(
        adapter.client,
        max_retries=client_max_retries,
    )
    stream = await client.chat.completions.create(**request_params)
    stream = await retry_chat_completions_with_v1_if_needed(
        adapter=adapter,
        payload=stream,
        request_params=request_params,
        model=effective_model,
        stream=True,
    )
    stream_closed = False
    stream_iter = aiter(stream)
    stream_timeout_seconds = normalize_timeout(request_params.get("timeout"))

    try:
        try:
            first_chunk = await adapter._next_stream_event_with_timeout(
                stream_iter,
                timeout_seconds=stream_timeout_seconds,
                model=effective_model,
                wire_api="chat_completions",
            )
        except StopAsyncIteration:
            return

        fallback_candidate = False
        if fallback_to_responses:
            fallback_candidate = should_fallback_to_responses(
                use_responses_api=adapter._use_responses_api(),
                cross_protocol_fallback_allowed=adapter.protocol_capabilities.is_cross_protocol_fallback_allowed(
                    from_wire_api="chat_completions",
                    to_wire_api="responses",
                ),
                payload=first_chunk,
            )

        if fallback_candidate:
            if responses_fallback_context_ok(responses_kwargs):
                logger.warning(
                    "Stream chunk missing choices; fallback to responses API: model={} chunk_type={}",
                    model,
                    type(first_chunk).__name__,
                )
                await aclose_stream(stream)
                stream_closed = True
                async for chunk in adapter._stream_chat_via_responses(
                    **(responses_kwargs or {}),
                ):
                    yield chunk
                return
            logger.warning(
                "Stream chunk looked like responses payload but fallback context missing; skip fallback: model={} chunk_type={}",
                model,
                type(first_chunk).__name__,
            )

        first_chat_chunk = convert_chat_chunk(
            adapter=adapter,
            chunk=first_chunk,
            model=model,
        )
        yield first_chat_chunk
        if first_chat_chunk.finish_reason is not None:
            logger.info(
                "Stream finish_reason on first chunk, closing upstream: model={} finish_reason={} wire_api=chat_completions",
                model,
                first_chat_chunk.finish_reason,
            )
            return

        while True:
            try:
                chunk = await adapter._next_stream_event_with_timeout(
                    stream_iter,
                    timeout_seconds=stream_timeout_seconds,
                    model=effective_model,
                    wire_api="chat_completions",
                )
            except StopAsyncIteration:
                break

            chat_chunk = convert_chat_chunk(
                adapter=adapter,
                chunk=chunk,
                model=model,
            )
            yield chat_chunk
            if chat_chunk.finish_reason is not None:
                logger.info(
                    "Stream finish_reason received, closing upstream: model={} finish_reason={} wire_api=chat_completions",
                    model,
                    chat_chunk.finish_reason,
                )
                break
    finally:
        if not stream_closed:
            await aclose_stream(stream)
