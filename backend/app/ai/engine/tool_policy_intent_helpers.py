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
from .system_prompt_intent_helpers import intent_completion_matches
from .tool_policy_semantics import tool_semantic_family
from .turn_research_helpers import (
    collect_web_research_evidence,
    extract_recent_successful_tool_names,
)


def _push_unique(items: list[str], value: str) -> None:
    normalized = str(value or "").strip()
    if normalized and normalized not in items:
        items.append(normalized)


def _normalize_page_intent_name(kind: str | None) -> str:
    normalized = str(kind or "").strip()
    return normalized if normalized.startswith("page_") else ""


def _merge_active_page_intent(
    intents: list[str],
    *,
    input_variables: dict[str, Any] | None,
) -> list[str]:
    merged: list[str] = []
    for intent_name in intents:
        _push_unique(merged, intent_name)

    active_intent_kind = _normalize_page_intent_name(
        resolve_active_intent_kind_from_input_variables(input_variables)
    )
    if not active_intent_kind:
        return merged

    has_page_intent = any(intent.startswith("page_") for intent in merged)
    if active_intent_kind == "page_summary" and has_page_intent:
        return merged

    if active_intent_kind != "page_summary":
        replaced: list[str] = []
        inserted = False
        for intent_name in merged:
            if intent_name == "page_summary":
                if not inserted:
                    replaced.append(active_intent_kind)
                    inserted = True
                continue
            _push_unique(replaced, intent_name)
        merged = replaced

    _push_unique(merged, active_intent_kind)
    return merged


def _requested_page_intents(
    input_variables: dict[str, Any] | None,
) -> list[str]:
    intents: list[str] = []
    planned = resolve_intent_plan_view(input_variables)
    for intent in planned:
        if intent.family != "page_ops" or not intent.requires_tools:
            continue
        _push_unique(intents, _normalize_page_intent_name(intent.kind))
    if intents:
        return _merge_active_page_intent(intents, input_variables=input_variables)

    requested = resolve_requested_intents_from_input_variables(input_variables)
    for intent_name in requested:
        normalized = _normalize_page_intent_name(intent_name)
        if normalized.startswith("page_"):
            _push_unique(intents, normalized)
    return _merge_active_page_intent(intents, input_variables=input_variables)


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
            requested_intents = [str(intent_name or "").strip() for intent_name in requested]
            if any(
                _normalize_page_intent_name(intent_name) for intent_name in requested_intents
            ):
                return _merge_active_page_intent(
                    requested_intents,
                    input_variables=input_variables,
                )
            return requested_intents
        active_intent_kind = resolve_active_intent_kind_from_input_variables(
            input_variables
        )
        if active_intent_kind and str(active_intent_kind).startswith("page_"):
            normalized_active_page_intent = _normalize_page_intent_name(
                active_intent_kind
            )
            return [normalized_active_page_intent] if normalized_active_page_intent else []
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
            normalized_page_intent = _normalize_page_intent_name(intent.kind)
            if normalized_page_intent:
                _push(normalized_page_intent)
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
    successful_tool_names_ordered = extract_recent_successful_tool_names(
        messages,
        limit=50,
    )
    successful_tool_names = set(successful_tool_names_ordered)
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

    requested_page_intents = _requested_page_intents(input_variables)
    if requested_page_intents:
        planned_intents = {
            str(intent.kind or "").strip(): intent
            for intent in resolve_intent_plan_view(input_variables)
            if intent.family == "page_ops" and intent.requires_tools
        }
        for intent_name in requested_page_intents:
            planned_intent = planned_intents.get(intent_name)
            if intent_completion_matches(
                "page_ops",
                completed_tool_names=successful_tool_names,
                intent_kind=intent_name,
                allowed_tool_names=successful_tool_names_ordered,
                preferred_tool_names=successful_tool_names_ordered,
                intent_metadata=(
                    dict(planned_intent.metadata or {})
                    if planned_intent is not None
                    else None
                ),
            ):
                completed.add(intent_name)
    elif successful_tool_names & {
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
