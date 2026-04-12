"""Intent-derived tool policy helpers."""

from __future__ import annotations

from typing import Any

from app.ai.text_semantics import mentions_rail_ticket, mentions_weather
from app.ai.tools.types import ToolDefinition
from app.ai.types import ChatMessage

from .intent_runtime_accessors import (
    resolve_active_intent_kind_from_input_variables,
    resolve_intent_plan_view,
    resolve_requested_intents_from_input_variables,
)
from .tool_policy_semantics import tool_semantic_family
from .turn_research_helpers import (
    collect_web_research_evidence,
    extract_recent_successful_tool_names,
)


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
            return requested
        active_intent_kind = resolve_active_intent_kind_from_input_variables(
            input_variables
        )
        if active_intent_kind and str(active_intent_kind).startswith("page_"):
            return ["page_summary"]
        if mentions_weather(normalized):
            has_weather_capability = any(
                tool_semantic_family(tool, input_variables) == "weather" for tool in tools
            ) or any(
                tool.name in {"web_search", "fetch_url"} for tool in tools
            )
            if has_weather_capability:
                return ["weather"]
        if mentions_rail_ticket(normalized) and any(
            tool.name in {"web_search", "fetch_url"} for tool in tools
        ):
            return ["rail_ticket_research"]
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
        if intent.family == "page_ops":
            _push("page_summary")
            continue
        if intent.kind == "web_research":
            label = str(intent.user_visible_label or "").strip()
            if label == "weather_web_research":
                _push("weather")
                continue
            if label == "rail_search" or mentions_rail_ticket(normalized):
                _push("rail_ticket_research")

    return intents


def collect_completed_turn_intents(
    messages: list[ChatMessage],
    *,
    tools: list[ToolDefinition],
    input_variables: dict[str, Any] | None,
) -> set[str]:
    completed: set[str] = set()
    successful_tool_names = set(extract_recent_successful_tool_names(messages, limit=50))
    successful_queries, fetched_urls = collect_web_research_evidence(messages)
    weather_tool_names = {
        tool.name
        for tool in tools
        if tool_semantic_family(tool, input_variables) == "weather"
    }

    if successful_tool_names & (
        weather_tool_names | {"get_current_weather", "get_weather_forecast"}
    ):
        completed.add("weather")
    if any(
        any(
            token in url.lower()
            for token in ("weather", "cma.cn", "qweather", "weather.com")
        )
        for url in fetched_urls
    ):
        completed.add("weather")

    if successful_tool_names & {
        "ui_get_snapshot",
        "ui_read_region",
        "ui_read_table",
        "ui_list_interactables",
    }:
        completed.add("page_summary")

    rail_search_seen = any(mentions_rail_ticket(query) for query in successful_queries)
    rail_fetch_seen = any(
        any(token in url.lower() for token in ("12306", "gaotie", "huoche", "trains"))
        for url in fetched_urls
    )
    if rail_search_seen or rail_fetch_seen:
        completed.add("rail_ticket_research")

    return completed


__all__ = [
    "collect_completed_turn_intents",
    "detect_requested_turn_intents",
]
