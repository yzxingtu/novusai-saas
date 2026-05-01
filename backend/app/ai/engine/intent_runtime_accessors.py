"""Accessors for runtime intent facts without planner side effects."""

from __future__ import annotations

from typing import Any

from .intent_plan_accessors import resolve_intent_plan_from_input_variables
from .types import IntentPlan

_RUNTIME_INTENT_FACT_KEYS = (
    "_runtime_intent_facts",
    "runtime_intent_facts",
    "intent_facts",
)


def _coerce_intent_plan(raw_value: Any) -> list[IntentPlan]:
    if not isinstance(raw_value, list):
        return []
    intent_plan: list[IntentPlan] = []
    for item in raw_value:
        if isinstance(item, IntentPlan):
            intent_plan.append(item)
            continue
        if not isinstance(item, dict):
            continue
        try:
            intent_plan.append(IntentPlan(**item))
        except TypeError:
            continue
    return intent_plan


def _coerce_text_list(raw_value: Any) -> list[str]:
    if raw_value is None:
        return []
    if isinstance(raw_value, str):
        raw_items = [raw_value]
    elif isinstance(raw_value, list):
        raw_items = raw_value
    else:
        return []
    seen: set[str] = set()
    items: list[str] = []
    for item in raw_items:
        value = str(item or "").strip()
        if not value or value in seen:
            continue
        items.append(value)
        seen.add(value)
    return items


def _iter_runtime_intent_fact_sources(
    input_variables: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    if not isinstance(input_variables, dict):
        return []

    sources: list[dict[str, Any]] = []
    for key in _RUNTIME_INTENT_FACT_KEYS:
        value = input_variables.get(key)
        if isinstance(value, dict):
            sources.append(value)

    tool_planner = input_variables.get("tool_planner")
    if isinstance(tool_planner, dict):
        sources.append({"tool_planner": tool_planner})

    context_diagnostics = input_variables.get("context_diagnostics")
    if isinstance(context_diagnostics, dict):
        sources.append(context_diagnostics)
        for key in _RUNTIME_INTENT_FACT_KEYS:
            value = context_diagnostics.get(key)
            if isinstance(value, dict):
                sources.append(value)
        tool_planner = context_diagnostics.get("tool_planner")
        if isinstance(tool_planner, dict):
            sources.append({"tool_planner": tool_planner})

    return sources


def resolve_intent_plan_view(
    input_variables: dict[str, Any] | None,
) -> list[IntentPlan]:
    intent_plan = resolve_intent_plan_from_input_variables(input_variables)
    if intent_plan:
        return intent_plan

    for source in _iter_runtime_intent_fact_sources(input_variables):
        intent_plan = _coerce_intent_plan(source.get("intent_plan"))
        if intent_plan:
            return intent_plan
        tool_planner = source.get("tool_planner")
        if isinstance(tool_planner, dict):
            intent_plan = _coerce_intent_plan(tool_planner.get("intent_plan"))
            if intent_plan:
                return intent_plan

    return []


def resolve_requested_intents_from_input_variables(
    input_variables: dict[str, Any] | None,
) -> list[str]:
    for source in _iter_runtime_intent_fact_sources(input_variables):
        for key in (
            "requested_intents",
            "requested_intent_names",
            "requested_intent_kinds",
        ):
            requested = _coerce_text_list(source.get(key))
            if requested:
                return requested
    return []


def resolve_active_intent_kind_from_input_variables(
    input_variables: dict[str, Any] | None,
) -> str | None:
    for source in _iter_runtime_intent_fact_sources(input_variables):
        for key in ("active_intent_kind", "intent_kind"):
            value = str(source.get(key) or "").strip()
            if value and value != "none":
                return value
        tool_planner = source.get("tool_planner")
        if isinstance(tool_planner, dict):
            value = str(tool_planner.get("intent") or "").strip()
            if value and value != "none":
                return value
    return None


__all__ = [
    "resolve_active_intent_kind_from_input_variables",
    "resolve_intent_plan_view",
    "resolve_requested_intents_from_input_variables",
]
