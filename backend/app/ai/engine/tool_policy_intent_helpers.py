"""Intent-derived tool policy helpers."""

from __future__ import annotations

from typing import Any

from app.ai.text_semantics import mentions_weather
from app.ai.tools.types import ToolDefinition
from app.ai.types import ChatMessage

from .base_helpers import tool_call_name
from .intent_runtime_accessors import (
    resolve_intent_plan_view,
    resolve_requested_intents_from_input_variables,
)
from .tool_policy_semantics import tool_semantic_family


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
        if mentions_weather(normalized):
            has_weather_capability = any(
                tool_semantic_family(tool, input_variables) == "weather"
                for tool in tools
            )
            if has_weather_capability:
                return ["weather"]
        return []
    intents: list[str] = []

    def _push(intent_name: str) -> None:
        if intent_name not in intents:
            intents.append(intent_name)

    for intent in planned:
        if intent.family == "none" or not intent.requires_tools:
            continue
        if intent.kind == "weather_query":
            _push("weather")
            continue
    return intents


def collect_completed_turn_intents(
    messages: list[ChatMessage],
    *,
    tools: list[ToolDefinition],
    input_variables: dict[str, Any] | None,
) -> set[str]:
    completed: set[str] = set()
    successful_tool_names_ordered = extract_recent_successful_tool_names(
        messages,
        limit=50,
    )
    successful_tool_names = set(successful_tool_names_ordered)
    weather_tool_names = {
        tool.name
        for tool in tools
        if tool_semantic_family(tool, input_variables) == "weather"
    }

    if successful_tool_names & (
        weather_tool_names | {"get_current_weather", "get_weather_forecast"}
    ):
        completed.add("weather")

    return completed


__all__ = [
    "collect_completed_turn_intents",
    "detect_requested_turn_intents",
]
