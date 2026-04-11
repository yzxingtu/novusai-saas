"""Helpers for accessing precomputed intent plans in runtime input variables."""

from __future__ import annotations

from typing import Any

from .types import IntentPlan


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


def resolve_intent_plan_from_input_variables(
    input_variables: dict[str, Any] | None,
) -> list[IntentPlan]:
    if not isinstance(input_variables, dict):
        return []
    for key in ("_runtime_intent_plan", "intent_plan"):
        intent_plan = _coerce_intent_plan(input_variables.get(key))
        if intent_plan:
            return intent_plan
    context_diagnostics = input_variables.get("context_diagnostics")
    if isinstance(context_diagnostics, dict):
        intent_plan = _coerce_intent_plan(context_diagnostics.get("intent_plan"))
        if intent_plan:
            return intent_plan
    return []


def attach_intent_plan_to_input_variables(
    input_variables: dict[str, Any] | None,
    intent_plan: list[IntentPlan] | None,
) -> None:
    if not intent_plan or not isinstance(input_variables, dict):
        return
    if "_runtime_intent_plan" in input_variables:
        return
    input_variables["_runtime_intent_plan"] = [intent.to_dict() for intent in intent_plan]


__all__ = [
    "attach_intent_plan_to_input_variables",
    "resolve_intent_plan_from_input_variables",
]
