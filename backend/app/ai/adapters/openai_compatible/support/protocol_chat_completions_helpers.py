"""Helper utilities for chat.completions protocol handling."""

from __future__ import annotations

from typing import Any, Protocol

from openai.types.chat import ChatCompletion, ChatCompletionChunk

from app.ai.types import ChatChunk, ChatMessage, ChatResponse


class _UsageExtractor(Protocol):
    def _extract_usage_tokens(
        self,
        usage: Any,
    ) -> tuple[int | None, int | None, int | None]: ...


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
    output = getattr(payload, "output", None)
    if isinstance(output, (list, tuple)):
        return True
    if isinstance(payload, dict) and isinstance(payload.get("output"), list):
        return True
    output_text = getattr(payload, "output_text", None)
    if isinstance(output_text, str):
        return True
    return isinstance(payload, dict) and isinstance(payload.get("output_text"), str)


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


def responses_fallback_context_ok(responses_kwargs: dict[str, Any] | None) -> bool:
    """Ensure responses fallback has enough context to avoid accidental cross-protocol hops."""
    if not responses_kwargs:
        return False
    messages = responses_kwargs.get("messages")
    model = responses_kwargs.get("model")
    return isinstance(messages, list) and isinstance(model, str) and bool(model.strip())


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
    adapter: _UsageExtractor,
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
    adapter: _UsageExtractor,
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


__all__ = [
    "convert_chat_chunk",
    "convert_chat_response",
    "is_salvageable_raw_text_chat_response",
    "payload_looks_like_api_error",
    "payload_resembles_responses_api_body",
    "responses_fallback_context_ok",
    "should_fallback_to_responses",
]
