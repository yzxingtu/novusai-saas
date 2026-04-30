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

_PAGE_SUMMARY_WORKFLOW_GOALS = frozenset({"page_summary", "table_summary"})
_RUNTIME_PAGE_FACT_KEYS = (
    "_runtime_intent_facts",
    "runtime_intent_facts",
    "intent_facts",
)


def _push_unique(items: list[str], value: str) -> None:
    normalized = str(value or "").strip()
    if normalized and normalized not in items:
        items.append(normalized)


def _canonicalize_page_workflow_goal(
    goal: str,
    *,
    user_text: str | None = None,
) -> str:
    del goal, user_text
    return ""


def _page_intent_kind(
    kind: str | None,
    *,
    metadata: dict[str, Any] | None = None,
    user_text: str | None = None,
) -> str:
    workflow_goal = _page_workflow_goal(
        kind,
        metadata=metadata,
        user_text=user_text,
    )
    return "page_workflow" if workflow_goal else ""


def _runtime_page_metadata(
    input_variables: dict[str, Any] | None,
) -> dict[str, Any] | None:
    del input_variables
    return None


def _requested_page_intent_kind(
    intent_name: str | None,
    *,
    runtime_page_metadata: dict[str, Any] | None = None,
) -> str:
    del intent_name, runtime_page_metadata
    return ""


def _page_workflow_goal(
    kind: str | None,
    *,
    metadata: dict[str, Any] | None = None,
    user_text: str | None = None,
) -> str:
    del kind, metadata, user_text
    return ""


def _canonical_page_workflow_metadata(
    kind: str | None,
    *,
    metadata: dict[str, Any] | None = None,
    user_text: str | None = None,
) -> dict[str, Any] | None:
    payload = dict(metadata or {})
    workflow_goal = _page_workflow_goal(
        kind,
        metadata=payload,
        user_text=user_text,
    )
    if not workflow_goal:
        return payload or None
    payload.setdefault("page_workflow_kind", "page_workflow")
    payload.setdefault("page_workflow_goal", workflow_goal)
    return payload


def _merge_active_page_intent(
    intents: list[str],
    *,
    input_variables: dict[str, Any] | None,
) -> list[str]:
    merged: list[str] = []
    for intent_name in intents:
        _push_unique(merged, intent_name)

    runtime_page_metadata = _runtime_page_metadata(input_variables)
    active_intent_kind = _page_intent_kind(
        resolve_active_intent_kind_from_input_variables(input_variables),
        metadata=runtime_page_metadata,
    )
    if not active_intent_kind:
        return merged

    active_page_workflow_goal = _page_workflow_goal(
        resolve_active_intent_kind_from_input_variables(input_variables),
        metadata=runtime_page_metadata,
    )
    has_page_intent = any(_page_workflow_goal(intent_name) for intent_name in merged)
    if (
        active_page_workflow_goal in _PAGE_SUMMARY_WORKFLOW_GOALS
        and has_page_intent
    ):
        return merged

    if active_page_workflow_goal not in _PAGE_SUMMARY_WORKFLOW_GOALS:
        replaced: list[str] = []
        inserted = False
        for intent_name in merged:
            if _page_workflow_goal(intent_name) in _PAGE_SUMMARY_WORKFLOW_GOALS:
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
    del input_variables
    return []


def _planned_page_intent_completion_override(intent: Any | None) -> bool | None:
    if intent is None:
        return None
    metadata = (
        dict(getattr(intent, "metadata", {}) or {})
        if hasattr(intent, "metadata")
        else {}
    )
    progress = metadata.get("page_workflow_progress")
    if not isinstance(progress, dict):
        return None
    status = str(progress.get("status") or "").strip()
    continuation_required = progress.get("continuation_required")
    if status == "completed" or continuation_required is False:
        return True
    if status or continuation_required is True:
        return False
    return None


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
            runtime_page_metadata = _runtime_page_metadata(input_variables)
            normalized_requested_intents: list[str] = []
            saw_page_intent = False
            for intent_name in requested_intents:
                normalized_page_intent = _requested_page_intent_kind(
                    intent_name,
                    runtime_page_metadata=runtime_page_metadata,
                )
                if normalized_page_intent:
                    _push_unique(normalized_requested_intents, normalized_page_intent)
                    saw_page_intent = True
                    continue
                if intent_name.startswith("page_") or intent_name == "page_workflow":
                    continue
                _push_unique(normalized_requested_intents, intent_name)
            if saw_page_intent:
                return _merge_active_page_intent(
                    normalized_requested_intents,
                    input_variables=input_variables,
                )
            return normalized_requested_intents
        runtime_page_metadata = _runtime_page_metadata(input_variables)
        active_intent_kind = resolve_active_intent_kind_from_input_variables(
            input_variables
        )
        normalized_active_page_intent = _page_intent_kind(
            active_intent_kind,
            metadata=runtime_page_metadata,
        )
        if normalized_active_page_intent:
            return (
                [normalized_active_page_intent] if normalized_active_page_intent else []
            )
        if mentions_weather(normalized):
            has_weather_capability = any(
                tool_semantic_family(tool, input_variables) == "weather"
                for tool in tools
            ) or any(tool.name in {"web_search", "fetch_url"} for tool in tools)
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
            normalized_page_intent = _page_intent_kind(
                intent.kind,
                metadata=getattr(intent, "metadata", None),
                user_text=getattr(intent, "source_text", None),
            )
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
        raw_runtime_page_metadata = _runtime_page_metadata(input_variables)
        runtime_page_metadata = _canonical_page_workflow_metadata(
            resolve_active_intent_kind_from_input_variables(input_variables),
            metadata=raw_runtime_page_metadata,
        )
        planned_intents: dict[str, Any] = {}
        for intent in resolve_intent_plan_view(input_variables):
            if intent.family != "page_ops" or not intent.requires_tools:
                continue
            intent_name = _page_intent_kind(
                intent.kind,
                metadata=getattr(intent, "metadata", None),
                user_text=getattr(intent, "source_text", None),
            )
            if intent_name and intent_name not in planned_intents:
                planned_intents[intent_name] = intent
        for intent_name in requested_page_intents:
            planned_intent = planned_intents.get(intent_name)
            explicit_completion = _planned_page_intent_completion_override(
                planned_intent
            )
            if explicit_completion is True:
                completed.add(intent_name)
                continue
            if explicit_completion is False:
                continue
            if intent_completion_matches(
                "page_ops",
                completed_tool_names=successful_tool_names,
                intent_kind=intent_name,
                allowed_tool_names=successful_tool_names_ordered,
                preferred_tool_names=successful_tool_names_ordered,
                intent_metadata=(
                    _canonical_page_workflow_metadata(
                        planned_intent.kind,
                        metadata=dict(planned_intent.metadata or {}),
                        user_text=getattr(planned_intent, "source_text", None),
                    )
                    if planned_intent is not None
                    else runtime_page_metadata if intent_name == "page_workflow" else None
                ),
                ):
                completed.add(intent_name)
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
