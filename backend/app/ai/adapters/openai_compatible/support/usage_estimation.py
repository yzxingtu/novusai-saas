"""Usage estimation helpers for Responses streams."""

from __future__ import annotations

from app.ai.types import ChatMessage
from app.ai.usage_mode import resolve_chat_usage


def estimate_responses_stream_usage(
    messages: list[ChatMessage],
    output_text: str,
) -> tuple[int, int, int]:
    usage = resolve_chat_usage(
        messages=messages,
        output_text=output_text,
        input_tokens=None,
        output_tokens=None,
        total_tokens=None,
    )
    return usage.input_tokens, usage.output_tokens, usage.total_tokens


__all__ = ["estimate_responses_stream_usage"]
