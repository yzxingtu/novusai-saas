"""chat.completions protocol helpers for OpenAI-compatible adapters."""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any, Protocol

from openai.types.chat import ChatCompletion, ChatCompletionChunk

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


def payload_looks_like_api_error(payload: Any) -> bool:
    """True when upstream returned an error object, not a misrouted success body."""
    if payload is None:
        return False
    if getattr(payload, "error", None) is not None:
        return True
    return isinstance(payload, dict) and payload.get("error") is not None


def payload_resembles_responses_api_body(payload: Any) -> bool:
    """Only treat Responses-shaped bodies as cross-protocol fallback candidates."""
    if payload is None:
        return False
    if getattr(payload, "object", None) == "response":
        return True
    if isinstance(payload, dict) and payload.get("object") == "response":
        return True
    if hasattr(payload, "output"):
        return True
    if isinstance(payload, dict) and "output" in payload:
        return True
    if hasattr(payload, "output_text"):
        return True
    return isinstance(payload, dict) and "output_text" in payload


def should_fallback_to_responses(
    *,
    use_responses_api: bool,
    cross_protocol_fallback_allowed: bool,
    payload: Any,
) -> bool:
    if use_responses_api:
        return False
    if not cross_protocol_fallback_allowed:
        return False
    if hasattr(payload, "choices"):
        return False
    if payload_looks_like_api_error(payload):
        return False
    return payload_resembles_responses_api_body(payload)


def is_salvageable_raw_text_chat_response(payload: Any) -> bool:
    """
    Accept plain assistant text from compatible gateways, but reject HTML/JSON junk.
    / 接受兼容网关直接返回的纯文本答复，但拒绝 HTML/JSON 垃圾载荷。
    """
    if not isinstance(payload, str):
        return False

    text = payload.strip()
    if not text:
        return False

    lowered = text.lower()
    if (
        lowered.startswith("<!doctype")
        or lowered.startswith("<html")
        or lowered.startswith("<body")
    ):
        return False
    if text.startswith("<"):
        return False
    return not (text.startswith("{") or text.startswith("["))


def convert_chat_response(
    *,
    adapter: ChatCompletionsAdapterProtocol,
    response: ChatCompletion,
    model: str,
) -> ChatResponse:
    """Convert chat.completions sync payload into the shared ChatResponse."""
    if not response.choices:
        return ChatResponse(
            message=ChatMessage(role="assistant", content=""),
            model=model,
            finish_reason="stop",
            metadata={"protocol_path": "chat_completions"},
        )

    choice = response.choices[0]
    message = choice.message

    tool_calls_dicts: list[dict[str, Any]] | None = None
    if message.tool_calls:
        tool_calls_dicts = [
            {
                "id": tc.id,
                "type": tc.type,
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,
                },
            }
            for tc in message.tool_calls
        ]

    chat_message = ChatMessage(
        role=message.role,
        content=message.content or "",
        tool_calls=tool_calls_dicts,
    )
    input_tokens, output_tokens, total_tokens = adapter._extract_usage_tokens(
        response.usage,
    )

    return ChatResponse(
        message=chat_message,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        model=model,
        finish_reason=choice.finish_reason,
        tool_calls=tool_calls_dicts,
        metadata={"protocol_path": "chat_completions"},
        raw_response=response.model_dump() if hasattr(response, "model_dump") else None,
    )


def convert_chat_chunk(
    *,
    adapter: ChatCompletionsAdapterProtocol,
    chunk: ChatCompletionChunk,
    model: str,
) -> ChatChunk:
    """Convert chat.completions stream chunk into the shared ChatChunk."""
    _ = model
    if not chunk.choices:
        return ChatChunk(delta="")

    choice = chunk.choices[0]
    delta = choice.delta
    delta_content = delta.content or ""
    reasoning_delta = getattr(delta, "reasoning_content", None) or ""
    input_tokens, output_tokens, total_tokens = adapter._extract_usage_tokens(
        chunk.usage,
    )

    tool_calls_dicts: list[dict[str, Any]] | None = None
    if delta.tool_calls:
        tool_calls_dicts = []
        for tc in delta.tool_calls:
            func = getattr(tc, "function", None)
            tool_calls_dicts.append(
                {
                    "index": getattr(tc, "index", None),
                    "id": getattr(tc, "id", None) or "",
                    "type": getattr(tc, "type", None) or "function",
                    "function": {
                        "name": getattr(func, "name", None) or "",
                        "arguments": getattr(func, "arguments", None) or "",
                    },
                }
            )

    return ChatChunk(
        delta=delta_content,
        reasoning_delta=reasoning_delta,
        role=delta.role,
        finish_reason=choice.finish_reason,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        tool_calls=tool_calls_dicts,
    )


async def execute_chat_via_chat_completions(
    *,
    adapter: ChatCompletionsAdapterProtocol,
    request_params: dict[str, Any],
    messages: list[ChatMessage],
    model: str,
    fallback_to_responses: bool = True,
    responses_kwargs: dict[str, Any] | None = None,
) -> ChatResponse:
    effective_model = str(request_params.get("model") or model)
    adapter._log_upstream_request(
        endpoint_path="chat/completions",
        model=effective_model,
        stream=False,
        wire_api="chat_completions",
    )
    logger.info("Chat request: model={} messages={}", effective_model, len(messages))

    response = await adapter.client.chat.completions.create(**request_params)
    response = await retry_chat_completions_with_v1_if_needed(
        adapter=adapter,
        payload=response,
        request_params=request_params,
        model=effective_model,
        stream=False,
    )

    if (
        fallback_to_responses
        and should_fallback_to_responses(
            use_responses_api=adapter._use_responses_api(),
            cross_protocol_fallback_allowed=adapter.protocol_capabilities.is_cross_protocol_fallback_allowed(
                from_wire_api="chat_completions",
                to_wire_api="responses",
            ),
            payload=response,
        )
    ):
        logger.warning(
            "Chat response missing choices; fallback to responses API: model={} response_type={}",
            model,
            type(response).__name__,
        )
        return await adapter._chat_via_responses(**(responses_kwargs or {}))

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
    effective_model = str(request_params.get("model") or model)
    adapter._log_upstream_request(
        endpoint_path="chat/completions",
        model=effective_model,
        stream=True,
        wire_api="chat_completions",
    )
    logger.info("Stream chat request: model={}", effective_model)

    stream = await adapter.client.chat.completions.create(**request_params)
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

        if (
            fallback_to_responses
            and should_fallback_to_responses(
                use_responses_api=adapter._use_responses_api(),
                cross_protocol_fallback_allowed=adapter.protocol_capabilities.is_cross_protocol_fallback_allowed(
                    from_wire_api="chat_completions",
                    to_wire_api="responses",
                ),
                payload=first_chunk,
            )
        ):
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

