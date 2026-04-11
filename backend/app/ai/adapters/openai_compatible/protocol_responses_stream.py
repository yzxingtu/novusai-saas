"""responses stream protocol helpers for OpenAI-compatible adapters."""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any, Protocol

from app.ai.types import ChatChunk, ChatMessage
from app.core.logging import LogManager

logger = LogManager.get_logger("ai")


class ResponsesStreamAdapterProtocol(Protocol):
    client: Any

    def _normalize_timeout_seconds(self, timeout: Any) -> float | None: ...

    def _log_upstream_request(
        self,
        *,
        endpoint_path: str,
        model: str,
        stream: bool,
        wire_api: str | None = None,
    ) -> None: ...

    async def _next_stream_event_with_timeout(
        self,
        stream: Any,
        *,
        timeout_seconds: float | None,
        model: str,
        wire_api: str,
    ) -> Any: ...

    def _extract_usage_tokens(
        self,
        usage: Any,
    ) -> tuple[int | None, int | None, int | None]: ...

    async def _retrieve_responses_usage(
        self,
        response_id: str | None,
    ) -> tuple[int | None, int | None, int | None]: ...

    @staticmethod
    def _estimate_responses_stream_usage(
        messages: list[ChatMessage],
        output_text: str,
    ) -> tuple[int, int, int]: ...

    def _extract_responses_reasoning_text(self, response: Any) -> str | None: ...

    def _extract_responses_text(self, response: Any) -> str: ...


async def _resolve_stream_usage(
    *,
    adapter: ResponsesStreamAdapterProtocol,
    usage: Any,
    response_id: str | None,
    messages: list[ChatMessage],
    output_text: str,
) -> tuple[int | None, int | None, int | None, str]:
    usage_mode = "actual"
    input_tokens, output_tokens, total_tokens = adapter._extract_usage_tokens(usage)
    if input_tokens is None and output_tokens is None and total_tokens is None:
        input_tokens, output_tokens, total_tokens = await adapter._retrieve_responses_usage(
            response_id,
        )
    if input_tokens is None and output_tokens is None and total_tokens is None:
        usage_mode = "estimated"
        input_tokens, output_tokens, total_tokens = adapter._estimate_responses_stream_usage(
            messages,
            output_text,
        )
    return input_tokens, output_tokens, total_tokens, usage_mode


async def execute_stream_chat_via_responses(
    *,
    adapter: ResponsesStreamAdapterProtocol,
    messages: list[ChatMessage],
    model: str,
    request_params: dict[str, Any],
    aclose_stream: Callable[[Any], Awaitable[None]],
) -> AsyncIterator[ChatChunk]:
    effective_model = str(request_params.get("model") or model)
    stream_timeout_seconds = adapter._normalize_timeout_seconds(
        request_params.get("timeout")
    )
    adapter._log_upstream_request(
        endpoint_path="responses",
        model=effective_model,
        stream=True,
    )
    logger.info("Responses stream request: model={}", effective_model)
    stream = await adapter.client.responses.create(**request_params)
    stream_iter = aiter(stream)
    emitted_text = False
    emitted_reasoning = False
    response_id: str | None = None
    collected_text = ""

    try:
        while True:
            try:
                event = await adapter._next_stream_event_with_timeout(
                    stream_iter,
                    timeout_seconds=stream_timeout_seconds,
                    model=effective_model,
                    wire_api="responses",
                )
            except StopAsyncIteration:
                break
            event_type = getattr(event, "type", "")

            if event_type == "response.created":
                response_obj = getattr(event, "response", None)
                response_id = getattr(response_obj, "id", None) or response_id
                continue

            # Keepalive progress chunk during hosted web search.
            if event_type.startswith("response.web_search_call"):
                yield ChatChunk(delta="", metadata={"web_search_in_progress": True})
                continue

            if event_type == "response.output_text.delta":
                delta = getattr(event, "delta", "") or ""
                if delta:
                    collected_text += delta
                    emitted_text = True
                    yield ChatChunk(delta=delta)
                continue

            # Some compatible gateways emit output_text.done without response.completed.
            if event_type == "response.output_text.done":
                text = getattr(event, "text", None) or ""
                if text and not emitted_text:
                    yield ChatChunk(delta=text)
                    collected_text += text
                    emitted_text = True
                usage = getattr(event, "usage", None)
                input_tokens, output_tokens, total_tokens, usage_mode = (
                    await _resolve_stream_usage(
                        adapter=adapter,
                        usage=usage,
                        response_id=response_id,
                        messages=messages,
                        output_text=collected_text or text,
                    )
                )
                yield ChatChunk(
                    delta="",
                    finish_reason="stop",
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    total_tokens=total_tokens,
                    metadata={"usage_mode": usage_mode},
                )
                logger.info(
                    "Responses stream response.output_text.done, closing upstream: model={} wire_api=responses",
                    model,
                )
                return

            if event_type in {
                "response.reasoning_text.delta",
                "response.reasoning_summary_text.delta",
            }:
                delta = getattr(event, "delta", "") or ""
                if delta:
                    emitted_reasoning = True
                    yield ChatChunk(delta="", reasoning_delta=delta)
                continue

            if event_type in {
                "response.reasoning.delta",
                "response.thinking.delta",
            }:
                delta = getattr(event, "delta", "") or getattr(event, "text", "") or ""
                if delta:
                    emitted_reasoning = True
                    yield ChatChunk(delta="", reasoning_delta=delta)
                continue

            if event_type == "response.output_item.added":
                item = getattr(event, "item", None)
                if getattr(item, "type", None) == "function_call":
                    yield ChatChunk(
                        delta="",
                        tool_calls=[
                            {
                                "index": getattr(event, "output_index", None),
                                "id": getattr(item, "call_id", None)
                                or getattr(item, "id", None)
                                or "",
                                "function": {
                                    "name": getattr(item, "name", None) or "",
                                    "arguments": getattr(item, "arguments", None) or "",
                                },
                            }
                        ],
                    )
                continue

            if event_type == "response.function_call_arguments.delta":
                yield ChatChunk(
                    delta="",
                    tool_calls=[
                        {
                            "index": getattr(event, "output_index", None),
                            "id": getattr(event, "item_id", None) or "",
                            "function": {"arguments": getattr(event, "delta", "") or ""},
                        }
                    ],
                )
                continue

            if event_type == "response.function_call_arguments.done":
                yield ChatChunk(
                    delta="",
                    tool_calls=[
                        {
                            "index": getattr(event, "output_index", None),
                            "id": getattr(event, "item_id", None) or "",
                            "function": {
                                "name": getattr(event, "name", None) or "",
                                "arguments": getattr(event, "arguments", None) or "{}",
                            },
                        }
                    ],
                )
                continue

            if event_type == "response.completed":
                response = getattr(event, "response", None)
                response_id = getattr(response, "id", None) or response_id
                if response is not None and not emitted_reasoning:
                    final_reasoning = adapter._extract_responses_reasoning_text(response)
                    if final_reasoning:
                        yield ChatChunk(
                            delta="",
                            reasoning_delta=final_reasoning,
                        )
                    else:
                        response_output = (
                            response.get("output", [])
                            if isinstance(response, dict)
                            else getattr(response, "output", [])
                        )
                        output_types = [
                            (
                                item.get("type", "unknown")
                                if isinstance(item, dict)
                                else getattr(item, "type", "unknown")
                            )
                            for item in (response_output or [])
                        ]
                        reasoning_content = (
                            response.get("reasoning_content")
                            if isinstance(response, dict)
                            else getattr(response, "reasoning_content", None)
                        )
                        logger.debug(
                            "Responses stream completed without reasoning: output_types={} has_reasoning_content={}",
                            output_types,
                            bool(reasoning_content),
                        )
                if response is not None and not emitted_text:
                    final_text = adapter._extract_responses_text(response)
                    if final_text:
                        collected_text += final_text
                        yield ChatChunk(delta=final_text)
                usage = getattr(response, "usage", None) if response is not None else None
                final_text = (
                    adapter._extract_responses_text(response)
                    if response is not None
                    else collected_text
                )
                input_tokens, output_tokens, total_tokens, usage_mode = (
                    await _resolve_stream_usage(
                        adapter=adapter,
                        usage=usage,
                        response_id=response_id,
                        messages=messages,
                        output_text=final_text or collected_text,
                    )
                )
                yield ChatChunk(
                    delta="",
                    finish_reason="stop",
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    total_tokens=total_tokens,
                    metadata={"usage_mode": usage_mode},
                )
                logger.info(
                    "Responses stream response.completed, closing upstream: model={} wire_api=responses",
                    model,
                )
                return

            if event_type in {"response.error", "response.failed"}:
                error_obj = getattr(event, "error", None)
                if error_obj is not None:
                    raise RuntimeError(str(error_obj))
                raise RuntimeError(event_type)
    finally:
        await aclose_stream(stream)


__all__ = [
    "ResponsesStreamAdapterProtocol",
    "execute_stream_chat_via_responses",
]
