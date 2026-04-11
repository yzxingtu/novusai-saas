"""Low-level usage field extraction helpers."""

from __future__ import annotations

from typing import Any

from app.core.logging import LogManager

logger = LogManager.get_logger("ai")


def extract_usage_int(usage: Any, *field_names: str) -> int | None:
    """Extract token counts from SDK objects or dict payloads returned by compatible gateways."""
    if usage is None:
        return None

    for field_name in field_names:
        if isinstance(usage, dict):
            value = usage.get(field_name)
        else:
            value = getattr(usage, field_name, None)
        if value is None:
            continue
        try:
            return int(value)
        except (TypeError, ValueError):
            logger.debug("Ignore non-integer usage field {}={!r}", field_name, value)
            return None

    return None


def extract_usage_tokens(
    usage: Any,
) -> tuple[int | None, int | None, int | None]:
    """Support both Responses-style and Chat Completions-style usage field names."""
    input_tokens = extract_usage_int(usage, "input_tokens", "prompt_tokens")
    output_tokens = extract_usage_int(usage, "output_tokens", "completion_tokens")
    total_tokens = extract_usage_int(usage, "total_tokens")
    if total_tokens is None and (input_tokens is not None or output_tokens is not None):
        total_tokens = (input_tokens or 0) + (output_tokens or 0)
    return input_tokens, output_tokens, total_tokens


__all__ = [
    "extract_usage_int",
    "extract_usage_tokens",
]
