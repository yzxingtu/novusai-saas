"""responses stream protocol helpers for OpenAI-compatible adapters."""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any, Protocol

from app.ai.adapters.openai_compatible.support.client_options import (
    with_client_retry_override,
)
from app.ai.exceptions import (
    AIGatewayError,
    ProviderAuthError,
    ProviderConnectionError,
    ProviderError,
    ProviderRateLimitError,
    ProviderTimeoutError,
)
from app.ai.types import ChatChunk, ChatMessage
from app.core.logging import LogManager

logger = LogManager.get_logger("ai")
_DEFAULT_RESPONSES_STREAM_CREATE_TIMEOUT_SECONDS = 20.0
_TIMEOUT_MARKERS = ("timeout", "timed_out", "time_out", "deadline")
_CONNECTION_MARKERS = ("connection", "connect", "network", "socket")


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
        (
            input_tokens,
            output_tokens,
            total_tokens,
        ) = await adapter._retrieve_responses_usage(
            response_id,
        )
    if input_tokens is None and output_tokens is None and total_tokens is None:
        usage_mode = "estimated"
        input_tokens, output_tokens, total_tokens = (
            adapter._estimate_responses_stream_usage(
                messages,
                output_text,
            )
        )
    return input_tokens, output_tokens, total_tokens, usage_mode


def _response_field(value: Any, field_name: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(field_name, default)
    return getattr(value, field_name, default)


def _response_status_code(value: Any) -> int | None:
    raw_status = (
        _response_field(value, "status_code")
        or _response_field(value, "status")
        or _response_field(value, "http_status")
    )
    try:
        return int(raw_status) if raw_status is not None else None
    except (TypeError, ValueError):
        return None


def _response_error_code(value: Any) -> str:
    return str(
        _response_field(value, "code")
        or _response_field(value, "type")
        or _response_field(value, "error_code")
        or ""
    ).strip()


def _response_error_message(value: Any, *, fallback: str) -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()
    message = str(
        _response_field(value, "message")
        or _response_field(value, "detail")
        or _response_field(value, "reason")
        or fallback
    ).strip()
    return message or fallback


def _responses_provider_error(
    error_obj: Any,
    *,
    model: str,
    fallback: str,
) -> AIGatewayError:
    status_code = _response_status_code(error_obj)
    error_code = _response_error_code(error_obj)
    message = _response_error_message(error_obj, fallback=fallback)
    haystack = " ".join((error_code, message)).lower()
    kwargs = {
        "provider_code": "openai",
        "model_code": model,
        "error_code": error_code or (str(status_code) if status_code else None),
        "status_code": status_code,
    }

    if status_code == 429:
        return ProviderRateLimitError(message, **kwargs)
    if status_code in {401, 403}:
        return ProviderAuthError(message, **kwargs)
    if status_code in {408, 504} or any(
        marker in haystack for marker in _TIMEOUT_MARKERS
    ):
        return ProviderTimeoutError(message, **kwargs)
    if any(marker in haystack for marker in _CONNECTION_MARKERS):
        return ProviderConnectionError(message, **kwargs)
    return ProviderError(message, **kwargs)


def _responses_stream_event_error(
    event: Any,
    *,
    event_type: str,
    model: str,
) -> AIGatewayError:
    error_obj = _response_field(event, "error")
    response = _response_field(event, "response")
    if error_obj is None:
        error_obj = _response_field(response, "error")
    fallback = f"Responses stream returned {event_type}"
    return _responses_provider_error(
        error_obj or {"message": fallback, "code": event_type},
        model=model,
        fallback=fallback,
    )


def _effective_create_timeout_seconds(
    request_params: dict[str, Any],
    timeout_seconds: float | None,
) -> float | None:
    if timeout_seconds is not None:
        return timeout_seconds
    if request_params.get("stream") is True:
        return _DEFAULT_RESPONSES_STREAM_CREATE_TIMEOUT_SECONDS
    return None


async def _create_responses_stream_with_timeout(
    client: Any,
    request_params: dict[str, Any],
    *,
    timeout_seconds: float | None,
    model: str,
) -> Any:
    create = client.responses.create
    effective_timeout_seconds = _effective_create_timeout_seconds(
        request_params,
        timeout_seconds,
    )

    async def invoke_create() -> Any:
        if inspect.iscoroutinefunction(create):
            return await create(**request_params)
        result = await asyncio.to_thread(create, **request_params)
        if inspect.isawaitable(result):
            return await result
        return result

    if effective_timeout_seconds is None:
        return await invoke_create()
    try:
        return await asyncio.wait_for(
            invoke_create(),
            timeout=effective_timeout_seconds,
        )
    except TimeoutError as exc:
        raise ProviderTimeoutError(
            "Responses stream request timed out before returning a stream",
            provider_code="openai",
            model_code=model,
            error_code="responses_stream_create_timeout",
            status_code=504,
        ) from exc


def _positive_int(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _has_url_citation_annotations(value: Any) -> bool:
    for annotation in _response_field(value, "annotations", []) or []:
        if str(_response_field(annotation, "type", "") or "").strip() != (
            "url_citation"
        ):
            continue
        if str(_response_field(annotation, "url", "") or "").startswith(
            ("http://", "https://")
        ):
            return True
    return False


def _extract_output_item_text(item: Any) -> str:
    parts: list[str] = []
    for content in _response_field(item, "content", []) or []:
        if _response_field(content, "type") != "output_text":
            continue
        text = str(_response_field(content, "text") or "")
        if text:
            parts.append(text)
    return "".join(parts)


def _has_native_web_search_evidence(response: Any) -> bool:
    if response is None:
        return False
    tool_usage = _response_field(response, "tool_usage")
    web_search_usage = _response_field(tool_usage, "web_search")
    if _positive_int(_response_field(web_search_usage, "num_requests")) > 0:
        return True

    response_type = str(_response_field(response, "type", "") or "").strip()
    if response_type == "web_search_call":
        return True
    if _has_url_citation_annotations(response):
        return True
    if response_type == "message":
        items = [response]
    else:
        items = list(_response_field(response, "output", []) or [])

    for item in items:
        item_type = str(_response_field(item, "type", "") or "").strip()
        if item_type == "web_search_call":
            return True
        if item_type != "message":
            continue
        for content in _response_field(item, "content", []) or []:
            if str(_response_field(content, "type", "") or "").strip() != "output_text":
                continue
            if _has_url_citation_annotations(content):
                return True
    return False


def _tool_call_state_key(index: Any, call_id: str | None) -> str:
    if isinstance(index, int):
        return f"idx:{index}"
    normalized_call_id = str(call_id or "").strip()
    if normalized_call_id:
        return f"id:{normalized_call_id}"
    return "anonymous"


def _merge_stream_fragment(current: str, incoming: str) -> str:
    if not incoming:
        return current
    if not current:
        return incoming
    if incoming == current or incoming in current:
        return current
    if incoming.startswith(current):
        return incoming
    max_overlap = min(len(current), len(incoming))
    for overlap in range(max_overlap, 0, -1):
        if current.endswith(incoming[:overlap]):
            return current + incoming[overlap:]
    return current + incoming


def _tool_call_delta_payload(
    *,
    state: dict[str, str],
    index: Any,
    call_id: str | None,
    name: str = "",
    arguments: str = "",
) -> dict[str, Any] | None:
    incoming_name = str(name or "")
    incoming_arguments = str(arguments or "")
    previous_name = str(state.get("name") or "")
    previous_arguments = str(state.get("arguments") or "")

    merged_name = _merge_stream_fragment(previous_name, incoming_name)
    merged_arguments = _merge_stream_fragment(previous_arguments, incoming_arguments)

    emitted_name = (
        merged_name[len(previous_name) :]
        if merged_name.startswith(previous_name)
        else merged_name
    )
    emitted_arguments = (
        merged_arguments[len(previous_arguments) :]
        if merged_arguments.startswith(previous_arguments)
        else merged_arguments
    )

    state["name"] = merged_name
    state["arguments"] = merged_arguments
    if call_id:
        state["id"] = str(call_id)

    function_payload: dict[str, str] = {}
    if emitted_name:
        function_payload["name"] = emitted_name
    if emitted_arguments:
        function_payload["arguments"] = emitted_arguments
    if not function_payload:
        return None
    return {
        "index": index,
        "id": str(state.get("id") or call_id or ""),
        "function": function_payload,
    }


async def execute_stream_chat_via_responses(
    *,
    adapter: ResponsesStreamAdapterProtocol,
    messages: list[ChatMessage],
    model: str,
    request_params: dict[str, Any],
    aclose_stream: Callable[[Any], Awaitable[None]],
) -> AsyncIterator[ChatChunk]:
    request_params = dict(request_params)
    client_max_retries = request_params.pop("_client_max_retries", None)
    effective_model = str(request_params.get("model") or model)
    stream_timeout_seconds = adapter._normalize_timeout_seconds(
        request_params.get("timeout")
    )
    if stream_timeout_seconds is None and request_params.get("stream") is True:
        stream_timeout_seconds = _DEFAULT_RESPONSES_STREAM_CREATE_TIMEOUT_SECONDS
    adapter._log_upstream_request(
        endpoint_path="responses",
        model=effective_model,
        stream=True,
    )
    logger.info("Responses stream request: model={}", effective_model)
    client = with_client_retry_override(
        adapter.client,
        max_retries=client_max_retries,
    )
    stream = await _create_responses_stream_with_timeout(
        client,
        request_params,
        timeout_seconds=stream_timeout_seconds,
        model=effective_model,
    )
    stream_iter = aiter(stream)
    emitted_text = False
    emitted_reasoning = False
    response_id: str | None = None
    collected_text = ""
    tool_call_states: dict[str, dict[str, str]] = {}
    saw_native_web_search = False
    required_output_deadline_started_at: float | None = None
    if request_params.get("tool_choice") == "required" and stream_timeout_seconds:
        required_output_deadline_started_at = asyncio.get_running_loop().time()

    def raise_if_required_output_stalled() -> None:
        if required_output_deadline_started_at is None:
            return
        if emitted_text or tool_call_states:
            return
        elapsed_seconds = (
            asyncio.get_running_loop().time() - required_output_deadline_started_at
        )
        if elapsed_seconds < stream_timeout_seconds:
            return
        raise ProviderTimeoutError(
            "Responses stream request timed out before required tool or text output",
            provider_code="openai",
            model_code=effective_model,
            error_code="responses_stream_required_output_timeout",
            status_code=504,
        )

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
                raise_if_required_output_stalled()
                continue

            # Keepalive progress chunk during hosted web search.
            if event_type.startswith("response.web_search_call"):
                saw_native_web_search = True
                yield ChatChunk(delta="", metadata={"web_search_in_progress": True})
                raise_if_required_output_stalled()
                continue

            if event_type == "response.output_text.delta":
                delta = getattr(event, "delta", "") or ""
                if delta:
                    collected_text += delta
                    emitted_text = True
                    yield ChatChunk(delta=delta)
                raise_if_required_output_stalled()
                continue

            # Some compatible gateways emit output_text.done without response.completed.
            if event_type == "response.output_text.done":
                text = getattr(event, "text", None) or ""
                if text and not emitted_text:
                    yield ChatChunk(delta=text)
                    collected_text += text
                    emitted_text = True
                usage = getattr(event, "usage", None)
                (
                    input_tokens,
                    output_tokens,
                    total_tokens,
                    usage_mode,
                ) = await _resolve_stream_usage(
                    adapter=adapter,
                    usage=usage,
                    response_id=response_id,
                    messages=messages,
                    output_text=collected_text or text,
                )
                yield ChatChunk(
                    delta="",
                    finish_reason="stop",
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    total_tokens=total_tokens,
                    metadata={
                        "protocol_path": "responses",
                        "responses_response_id": response_id,
                        "usage_mode": usage_mode,
                        "native_web_search_observed": bool(
                            saw_native_web_search
                            or _has_native_web_search_evidence(event)
                            or _has_native_web_search_evidence(
                                getattr(event, "response", None)
                            )
                        ),
                    },
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
                raise_if_required_output_stalled()
                continue

            if event_type in {
                "response.reasoning.delta",
                "response.thinking.delta",
            }:
                delta = getattr(event, "delta", "") or getattr(event, "text", "") or ""
                if delta:
                    emitted_reasoning = True
                    yield ChatChunk(delta="", reasoning_delta=delta)
                raise_if_required_output_stalled()
                continue

            if event_type == "response.output_item.added":
                item = getattr(event, "item", None)
                if getattr(item, "type", None) == "function_call":
                    call_payload = _tool_call_delta_payload(
                        state=tool_call_states.setdefault(
                            _tool_call_state_key(
                                getattr(event, "output_index", None),
                                getattr(item, "call_id", None)
                                or getattr(item, "id", None),
                            ),
                            {},
                        ),
                        index=getattr(event, "output_index", None),
                        call_id=getattr(item, "call_id", None)
                        or getattr(item, "id", None),
                        name=getattr(item, "name", None) or "",
                        arguments=getattr(item, "arguments", None) or "",
                    )
                    if call_payload is not None:
                        yield ChatChunk(
                            delta="",
                            tool_calls=[call_payload],
                        )
                raise_if_required_output_stalled()
                continue

            if event_type == "response.output_item.done":
                item = getattr(event, "item", None)
                item_type = _response_field(item, "type", "")
                if item_type == "function_call":
                    call_payload = _tool_call_delta_payload(
                        state=tool_call_states.setdefault(
                            _tool_call_state_key(
                                getattr(event, "output_index", None),
                                _response_field(item, "call_id")
                                or _response_field(item, "id")
                                or getattr(event, "item_id", None),
                            ),
                            {},
                        ),
                        index=getattr(event, "output_index", None),
                        call_id=_response_field(item, "call_id")
                        or _response_field(item, "id")
                        or getattr(event, "item_id", None),
                        name=_response_field(item, "name") or "",
                        arguments=_response_field(item, "arguments") or "{}",
                    )
                    if call_payload is not None:
                        yield ChatChunk(
                            delta="",
                            tool_calls=[call_payload],
                        )
                    raise_if_required_output_stalled()
                    continue
                if item_type == "message":
                    if _has_native_web_search_evidence(item):
                        saw_native_web_search = True
                    text = _extract_output_item_text(item)
                    if text and not emitted_text:
                        collected_text += text
                        emitted_text = True
                        yield ChatChunk(delta=text)
                    raise_if_required_output_stalled()
                    continue

            if event_type == "response.function_call_arguments.delta":
                call_payload = _tool_call_delta_payload(
                    state=tool_call_states.setdefault(
                        _tool_call_state_key(
                            getattr(event, "output_index", None),
                            getattr(event, "item_id", None),
                        ),
                        {},
                    ),
                    index=getattr(event, "output_index", None),
                    call_id=getattr(event, "item_id", None),
                    arguments=getattr(event, "delta", "") or "",
                )
                if call_payload is not None:
                    yield ChatChunk(
                        delta="",
                        tool_calls=[call_payload],
                    )
                raise_if_required_output_stalled()
                continue

            if event_type == "response.function_call_arguments.done":
                call_payload = _tool_call_delta_payload(
                    state=tool_call_states.setdefault(
                        _tool_call_state_key(
                            getattr(event, "output_index", None),
                            getattr(event, "item_id", None),
                        ),
                        {},
                    ),
                    index=getattr(event, "output_index", None),
                    call_id=getattr(event, "item_id", None),
                    name=getattr(event, "name", None) or "",
                    arguments=getattr(event, "arguments", None) or "{}",
                )
                if call_payload is not None:
                    yield ChatChunk(
                        delta="",
                        tool_calls=[call_payload],
                    )
                raise_if_required_output_stalled()
                continue

            if event_type == "response.completed":
                response = getattr(event, "response", None)
                response_id = getattr(response, "id", None) or response_id
                if response is not None and not emitted_reasoning:
                    final_reasoning = adapter._extract_responses_reasoning_text(
                        response
                    )
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
                usage = (
                    getattr(response, "usage", None) if response is not None else None
                )
                final_text = (
                    adapter._extract_responses_text(response)
                    if response is not None
                    else collected_text
                )
                (
                    input_tokens,
                    output_tokens,
                    total_tokens,
                    usage_mode,
                ) = await _resolve_stream_usage(
                    adapter=adapter,
                    usage=usage,
                    response_id=response_id,
                    messages=messages,
                    output_text=final_text or collected_text,
                )
                yield ChatChunk(
                    delta="",
                    finish_reason="stop",
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    total_tokens=total_tokens,
                    metadata={
                        "protocol_path": "responses",
                        "responses_response_id": response_id,
                        "usage_mode": usage_mode,
                        "native_web_search_observed": bool(
                            saw_native_web_search
                            or (
                                response is not None
                                and _has_native_web_search_evidence(response)
                            )
                        ),
                    },
                )
                logger.info(
                    "Responses stream response.completed, closing upstream: model={} wire_api=responses",
                    model,
                )
                return

            if event_type in {"response.error", "response.failed"}:
                raise _responses_stream_event_error(
                    event,
                    event_type=event_type,
                    model=model,
                )
            raise_if_required_output_stalled()
    finally:
        await aclose_stream(stream)


__all__ = [
    "ResponsesStreamAdapterProtocol",
    "execute_stream_chat_via_responses",
]
