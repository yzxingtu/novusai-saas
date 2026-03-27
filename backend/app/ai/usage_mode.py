"""
Chat usage resolution / 聊天用量解析。

Normalizes actual provider usage and explicit estimated fallback so monitoring can
treat future records consistently across streaming and non-streaming calls.
统一真实 usage 与估算 fallback，保证未来监控数据口径一致。
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from app.ai.types import ChatMessage
from app.ai.utils.token_estimator import estimate_tokens

ACTUAL_USAGE_MODE = "actual"
ESTIMATED_USAGE_MODE = "estimated"


@dataclass(frozen=True, slots=True)
class ResolvedChatUsage:
    input_tokens: int
    output_tokens: int
    total_tokens: int
    usage_mode: str


def _coerce_int(value: int | None) -> int:
    try:
        return max(int(value or 0), 0)
    except (TypeError, ValueError):
        return 0


def estimate_input_tokens(
    messages: Iterable[ChatMessage] | None,
    *,
    estimated_input: int = 0,
) -> int:
    """
    Prefer caller-provided estimate, otherwise estimate from visible message text.
    优先使用调用方预估值，否则按消息文本估算。
    """
    resolved = _coerce_int(estimated_input)
    if resolved > 0:
        return resolved
    if not messages:
        return 0
    return sum(estimate_tokens(message.content or "") for message in messages)


def resolve_chat_usage(
    *,
    messages: Iterable[ChatMessage] | None,
    output_text: str,
    input_tokens: int | None,
    output_tokens: int | None,
    total_tokens: int | None,
    estimated_input: int = 0,
) -> ResolvedChatUsage:
    """
    Resolve provider usage; when missing, fall back to a deterministic estimate.
    当供应商未返回 usage 时，回退到确定性的估算值。
    """
    resolved_input = _coerce_int(input_tokens)
    resolved_output = _coerce_int(output_tokens)
    resolved_total = _coerce_int(total_tokens)

    if resolved_total > 0 or resolved_input > 0 or resolved_output > 0:
        if resolved_total <= 0:
            resolved_total = resolved_input + resolved_output
        return ResolvedChatUsage(
            input_tokens=resolved_input,
            output_tokens=resolved_output,
            total_tokens=resolved_total,
            usage_mode=ACTUAL_USAGE_MODE,
        )

    estimated_in = estimate_input_tokens(messages, estimated_input=estimated_input)
    estimated_out = estimate_tokens(output_text or "")
    return ResolvedChatUsage(
        input_tokens=estimated_in,
        output_tokens=estimated_out,
        total_tokens=estimated_in + estimated_out,
        usage_mode=ESTIMATED_USAGE_MODE,
    )


__all__ = [
    "ACTUAL_USAGE_MODE",
    "ESTIMATED_USAGE_MODE",
    "ResolvedChatUsage",
    "estimate_input_tokens",
    "resolve_chat_usage",
]
