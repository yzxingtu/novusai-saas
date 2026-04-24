"""Page-specific tool policy helpers."""

from __future__ import annotations

from typing import Any

from app.ai.text_semantics import mentions_page_detail_operation
from app.ai.tools.types import ToolDefinition

from .intent_page_rules import detect_page_signal
from .intent_runtime_accessors import (
    resolve_active_intent_kind_from_input_variables,
    resolve_intent_plan_view,
)
from .page_workflow_state_machine import resolve_page_workflow_goal
from .tool_policy_semantics import tool_semantic_family
from .turn_research_helpers import has_page_context

_RUNTIME_PAGE_FACT_KEYS = (
    "_runtime_intent_facts",
    "runtime_intent_facts",
    "intent_facts",
)

def _canonicalize_page_workflow_goal(
    goal: str,
    *,
    user_text: str | None = None,
) -> str:
    return str(goal or "").strip()


def _page_workflow_goal_from_kind(
    kind: str | None,
    *,
    metadata: dict[str, Any] | None = None,
    user_text: str | None = None,
) -> str:
    workflow_goal = resolve_page_workflow_goal(
        intent_kind=str(kind or "").strip(),
        intent_metadata=dict(metadata or {}),
        user_text=user_text,
    )
    return _canonicalize_page_workflow_goal(
        workflow_goal,
        user_text=user_text,
    )


def _page_intent_kind(
    kind: str | None,
    *,
    metadata: dict[str, Any] | None = None,
    user_text: str | None = None,
) -> str:
    payload = dict(metadata or {})
    workflow_goal = _page_workflow_goal_from_kind(
        kind,
        metadata=payload,
        user_text=user_text,
    )
    return "page_workflow" if workflow_goal else ""


def _runtime_page_metadata(
    input_variables: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if not isinstance(input_variables, dict):
        return None

    sources: list[dict[str, Any]] = []
    for key in _RUNTIME_PAGE_FACT_KEYS:
        value = input_variables.get(key)
        if isinstance(value, dict):
            sources.append(value)

    context_diagnostics = input_variables.get("context_diagnostics")
    if isinstance(context_diagnostics, dict):
        sources.append(context_diagnostics)
        for key in _RUNTIME_PAGE_FACT_KEYS:
            value = context_diagnostics.get(key)
            if isinstance(value, dict):
                sources.append(value)

    for source in sources:
        if str(source.get("page_workflow_goal") or "").strip():
            return dict(source)
    return None


def first_page_intent_kind(
    *,
    user_text: str,
    tools: list[ToolDefinition],
    input_variables: dict[str, Any] | None = None,
) -> str | None:
    intents = resolve_intent_plan_view(input_variables)
    if not intents:
        runtime_page_metadata = _runtime_page_metadata(input_variables)
        active_intent_kind = resolve_active_intent_kind_from_input_variables(
            input_variables
        )
        active_page_intent = _page_intent_kind(
            active_intent_kind,
            metadata=runtime_page_metadata,
            user_text=user_text,
        )
        if active_page_intent:
            return active_page_intent
        detected_signal = detect_page_signal(
            clause=user_text,
            offset=0,
            input_variables=input_variables,
        )
        if detected_signal:
            return _page_intent_kind(
                detected_signal.kind,
                metadata=detected_signal.metadata,
                user_text=user_text,
            )
        return None
    for intent in intents:
        if intent.family == "page_ops":
            return _page_intent_kind(
                intent.kind,
                metadata=getattr(intent, "metadata", None),
                user_text=getattr(intent, "source_text", None) or user_text,
            )
    return None


def first_page_workflow_goal(
    *,
    user_text: str,
    tools: list[ToolDefinition],
    input_variables: dict[str, Any] | None = None,
) -> str | None:
    intents = resolve_intent_plan_view(input_variables)
    if not intents:
        runtime_page_metadata = _runtime_page_metadata(input_variables)
        active_intent_kind = resolve_active_intent_kind_from_input_variables(
            input_variables
        )
        active_workflow_goal = _page_workflow_goal_from_kind(
            active_intent_kind,
            metadata=runtime_page_metadata,
            user_text=user_text,
        )
        if active_workflow_goal:
            return active_workflow_goal
        detected_signal = detect_page_signal(
            clause=user_text,
            offset=0,
            input_variables=input_variables,
        )
        if detected_signal:
            return _page_workflow_goal_from_kind(
                detected_signal.kind,
                metadata=detected_signal.metadata,
                user_text=user_text,
            )
        return None
    for intent in intents:
        if intent.family != "page_ops":
            continue
        return _page_workflow_goal_from_kind(
            intent.kind,
            metadata=getattr(intent, "metadata", None),
            user_text=getattr(intent, "source_text", None) or user_text,
        )
    return None


def looks_like_generic_page_summary_request(
    user_text: str,
    tools: list[ToolDefinition],
    input_variables: dict[str, Any] | None = None,
) -> bool:
    normalized = (user_text or "").strip()
    if not normalized:
        return False
    workflow_goal = first_page_workflow_goal(
        user_text=normalized,
        tools=tools,
        input_variables=input_variables,
    )
    if workflow_goal != "page_summary":
        return False
    if mentions_page_detail_operation(normalized):
        return False
    return bool(
        has_page_context(input_variables)
        or any(tool.name in {"ui_get_snapshot"} for tool in tools)
    )


def restrict_page_tools_for_generic_summary(
    *,
    selected_tools: list[ToolDefinition],
    all_tools: list[ToolDefinition],
    user_text: str,
    input_variables: dict[str, Any] | None = None,
) -> tuple[list[ToolDefinition], bool]:
    if not looks_like_generic_page_summary_request(
        user_text,
        all_tools,
        input_variables,
    ):
        return selected_tools, False

    page_context_tool = next(
        (tool for tool in all_tools if tool.name in {"ui_get_snapshot"}),
        None,
    )
    if page_context_tool is None:
        return selected_tools, False

    restricted: list[ToolDefinition] = []
    seen_names: set[str] = set()
    for tool in selected_tools:
        if tool.name in {"ui_get_snapshot"}:
            if tool.name not in seen_names:
                restricted.append(tool)
                seen_names.add(tool.name)
            continue

        if tool_semantic_family(tool, input_variables) == "page_ops":
            continue

        if tool.name not in seen_names:
            restricted.append(tool)
            seen_names.add(tool.name)

    if page_context_tool.name not in seen_names:
        restricted.append(page_context_tool)

    restricted_names = [tool.name for tool in restricted]
    selected_names = [tool.name for tool in selected_tools]
    return restricted, restricted_names != selected_names


__all__ = [
    "first_page_intent_kind",
    "first_page_workflow_goal",
    "looks_like_generic_page_summary_request",
    "restrict_page_tools_for_generic_summary",
]
