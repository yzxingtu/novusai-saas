"""responses protocol helpers for OpenAI-compatible adapters."""

from __future__ import annotations

from typing import Any, Protocol

from app.ai.adapters.openai_compatible.support.responses_reasoning_parser import (
    extract_responses_reasoning_text,
)
from app.ai.types import ChatMessage, ChatResponse
from app.core.logging import LogManager

logger = LogManager.get_logger("ai")


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
        metadata={"protocol_path": "responses"},
        raw_response=response.model_dump() if hasattr(response, "model_dump") else None,
    )


async def execute_chat_via_responses(
    *,
    adapter: ResponsesAdapterProtocol,
    messages: list[ChatMessage],
    model: str,
    request_params: dict[str, Any],
) -> ChatResponse:
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
    response = await adapter.client.responses.create(**request_params)
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
