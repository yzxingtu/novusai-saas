"""responses protocol helpers for OpenAI-compatible adapters."""

from __future__ import annotations

import asyncio
import inspect
from typing import Any, Protocol

from app.ai.adapters.openai_compatible.support.client_options import (
    with_client_retry_override,
)
from app.ai.adapters.openai_compatible.support.responses_reasoning_parser import (
    extract_responses_reasoning_text,
)
from app.ai.exceptions import (
    AIGatewayError,
    ProviderAuthError,
    ProviderConnectionError,
    ProviderError,
    ProviderRateLimitError,
    ProviderTimeoutError,
)
from app.ai.types import ChatMessage, ChatResponse
from app.core.logging import LogManager

logger = LogManager.get_logger("ai")
_RESPONSES_RESPONSE_ID_METADATA_KEY = "responses_response_id"
_RESPONSES_FAILURE_STATUSES = frozenset(
    {"failed", "incomplete", "cancelled", "expired"}
)
_DEFAULT_RESPONSES_CREATE_TIMEOUT_SECONDS = 20.0
_TIMEOUT_MARKERS = ("timeout", "timed_out", "time_out", "deadline")
_CONNECTION_MARKERS = ("connection", "connect", "network", "socket")


class ResponsesAdapterProtocol(Protocol):
    client: Any

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

    def _normalize_timeout_seconds(self, timeout: Any) -> float | None: ...


def extract_responses_text(response: Any) -> str:
    output_text = getattr(response, "output_text", None)
    if isinstance(output_text, str) and output_text:
        return output_text

    parts: list[str] = []
    for item in getattr(response, "output", []) or []:
        if getattr(item, "type", None) != "message":
            continue
        for content in getattr(item, "content", []) or []:
            if getattr(content, "type", None) == "output_text":
                text = getattr(content, "text", None)
                if text:
                    parts.append(text)
    return "".join(parts)


def extract_responses_tool_calls(response: Any) -> list[dict] | None:
    tool_calls: list[dict] = []
    for item in getattr(response, "output", []) or []:
        if getattr(item, "type", None) != "function_call":
            continue
        call_id = getattr(item, "call_id", None) or getattr(item, "id", None) or ""
        tool_calls.append(
            {
                "id": call_id,
                "type": "function",
                "function": {
                    "name": getattr(item, "name", None) or "",
                    "arguments": getattr(item, "arguments", None) or "{}",
                },
            }
        )
    return tool_calls or None


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


def _responses_failure_error(response: Any, *, model: str) -> AIGatewayError | None:
    status = str(_response_field(response, "status", "") or "").strip().lower()
    error_obj = _response_field(response, "error")
    if error_obj is None and status == "incomplete":
        error_obj = _response_field(response, "incomplete_details")
    if error_obj is None and status not in _RESPONSES_FAILURE_STATUSES:
        return None
    fallback = f"Responses API returned {status or 'failed'}"
    return _responses_provider_error(
        error_obj or {"message": fallback, "code": status},
        model=model,
        fallback=fallback,
    )


def _has_forced_hosted_web_search_tool(request_params: dict[str, Any]) -> bool:
    if request_params.get("tool_choice") != "required":
        return False
    return any(
        isinstance(tool, dict) and tool.get("type") == "web_search"
        for tool in (request_params.get("tools") or [])
    )


def _effective_create_timeout_seconds(
    request_params: dict[str, Any],
    timeout_seconds: float | None,
) -> float | None:
    if timeout_seconds is not None:
        return timeout_seconds
    if _has_forced_hosted_web_search_tool(request_params):
        return _DEFAULT_RESPONSES_CREATE_TIMEOUT_SECONDS
    return None


async def _create_responses_with_timeout(
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
            "Responses API request timed out before returning a response",
            provider_code="openai",
            model_code=model,
            error_code="responses_create_timeout",
            status_code=504,
        ) from exc


def _positive_int(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _has_native_web_search_evidence(response: Any) -> bool:
    tool_usage = _response_field(response, "tool_usage")
    web_search_usage = _response_field(tool_usage, "web_search")
    if _positive_int(_response_field(web_search_usage, "num_requests")) > 0:
        return True

    for item in _response_field(response, "output", []) or []:
        item_type = str(_response_field(item, "type", "") or "").strip()
        if item_type == "web_search_call":
            return True
        if item_type != "message":
            continue
        for content in _response_field(item, "content", []) or []:
            if str(_response_field(content, "type", "") or "").strip() != "output_text":
                continue
            for annotation in _response_field(content, "annotations", []) or []:
                if str(
                    _response_field(annotation, "type", "") or ""
                ).strip() == "url_citation" and str(
                    _response_field(annotation, "url", "") or ""
                ).startswith(("http://", "https://")):
                    return True
    return False


def convert_responses_chat_response(
    *,
    adapter: ResponsesAdapterProtocol,
    response: Any,
    model: str,
) -> ChatResponse:
    from app.ai.types import ChatMessage  # local import keeps module lightweight

    tool_calls = extract_responses_tool_calls(response)
    reasoning_content = extract_responses_reasoning_text(response)
    usage = getattr(response, "usage", None)
    input_tokens, output_tokens, total_tokens = adapter._extract_usage_tokens(usage)
    response_id = str(getattr(response, "id", None) or "").strip()
    metadata = {"protocol_path": "responses"}
    if response_id:
        metadata[_RESPONSES_RESPONSE_ID_METADATA_KEY] = response_id
    if _has_native_web_search_evidence(response):
        metadata["native_web_search_observed"] = True
    return ChatResponse(
        message=ChatMessage(
            role="assistant",
            content=extract_responses_text(response),
            reasoning_content=reasoning_content,
            tool_calls=tool_calls,
        ),
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        model=model,
        finish_reason="stop"
        if getattr(response, "status", None) == "completed"
        else getattr(response, "status", None),
        tool_calls=tool_calls,
        metadata=metadata,
        raw_response=response.model_dump() if hasattr(response, "model_dump") else None,
    )


async def execute_chat_via_responses(
    *,
    adapter: ResponsesAdapterProtocol,
    messages: list[ChatMessage],
    model: str,
    request_params: dict[str, Any],
) -> ChatResponse:
    request_params = dict(request_params)
    client_max_retries = request_params.pop("_client_max_retries", None)
    effective_model = str(request_params.get("model") or model)
    adapter._log_upstream_request(
        endpoint_path="responses",
        model=effective_model,
        stream=False,
    )
    logger.info(
        "Responses chat request: model={} messages={}",
        effective_model,
        len(messages),
    )
    client = with_client_retry_override(
        adapter.client,
        max_retries=client_max_retries,
    )
    response = await _create_responses_with_timeout(
        client,
        request_params,
        timeout_seconds=adapter._normalize_timeout_seconds(
            request_params.get("timeout")
        ),
        model=effective_model,
    )
    response_error = _responses_failure_error(response, model=effective_model)
    if response_error is not None:
        raise response_error
    return convert_responses_chat_response(
        adapter=adapter,
        response=response,
        model=model,
    )


__all__ = [
    "ResponsesAdapterProtocol",
    "convert_responses_chat_response",
    "execute_chat_via_responses",
    "extract_responses_text",
    "extract_responses_tool_calls",
]
