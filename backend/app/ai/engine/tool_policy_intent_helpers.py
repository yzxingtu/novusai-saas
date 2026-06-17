"""Intent-derived tool policy helpers.

After intent planner removal (#57), these functions return empty results
since intent_plan is no longer computed. Retained for API compatibility
with tool contract breach analysis.
"""

from __future__ import annotations

from typing import Any

from app.ai.tools.types import ToolDefinition
from app.ai.types import ChatMessage

from .base_helpers import tool_call_name


def extract_recent_successful_tool_names(
    messages: list[ChatMessage],
    *,
    limit: int = 12,
) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    for message in reversed(messages):
        if message.role != "assistant" or not message.tool_calls:
            continue
        for tool_call in reversed(message.tool_calls):
            if tool_call.get("success") is not True:
                continue
            tool_name = tool_call_name(tool_call)
            if not tool_name or tool_name in seen:
                continue
            names.append(tool_name)
            seen.add(tool_name)
            if len(names) >= limit:
                return names
    return names


def detect_requested_turn_intents(
    user_text: str,
    *,
    tools: list[ToolDefinition],
    input_variables: dict[str, Any] | None,
) -> list[str]:
    """No-op after intent planner removal (#57)."""
    _ = user_text, tools, input_variables
    return []


def collect_completed_turn_intents(
    messages: list[ChatMessage],
    *,
    tools: list[ToolDefinition],
    input_variables: dict[str, Any] | None,
) -> set[str]:
    """No-op after intent planner removal (#57)."""
    _ = messages, tools, input_variables
    return set()


__all__ = [
    "collect_completed_turn_intents",
    "detect_requested_turn_intents",
    "extract_recent_successful_tool_names",
]
