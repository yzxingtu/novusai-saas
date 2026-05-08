"""Intent-derived tool policy helpers."""

from __future__ import annotations

from typing import Any

from app.ai.tools.types import ToolDefinition
from app.ai.types import ChatMessage

from .base_helpers import tool_call_name
from .intent_runtime_accessors import (
    resolve_intent_plan_view,
    resolve_requested_intents_from_input_variables,
)


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


def _push_unique(items: list[str], value: str) -> None:
    normalized = str(value or "").strip()
    if normalized and normalized not in items:
        items.append(normalized)


def detect_requested_turn_intents(
    user_text: str,
    *,
    tools: list[ToolDefinition],
    input_variables: dict[str, Any] | None,
) -> list[str]:
    normalized = (user_text or "").strip()
    if not normalized:
        return []

    planned = resolve_intent_plan_view(input_variables)
    if not planned:
        requested = resolve_requested_intents_from_input_variables(input_variables)
        if requested:
            requested_intents = [
                str(intent_name or "").strip() for intent_name in requested
            ]
            normalized_requested_intents: list[str] = []
            for intent_name in requested_intents:
                _push_unique(normalized_requested_intents, intent_name)
            return normalized_requested_intents
        _ = tools, input_variables
        return []
    _ = planned
    return []


def collect_completed_turn_intents(
    messages: list[ChatMessage],
    *,
    tools: list[ToolDefinition],
    input_variables: dict[str, Any] | None,
) -> set[str]:
    _ = messages, tools, input_variables
    return set()


__all__ = [
    "collect_completed_turn_intents",
    "detect_requested_turn_intents",
]
