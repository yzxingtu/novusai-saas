"""Page-specific tool policy helpers."""

from __future__ import annotations

from typing import Any

from app.ai.text_semantics import mentions_page_detail_operation, mentions_page_summary
from app.ai.tools.types import ToolDefinition

from .intent_page_rules import detect_page_signal
from .intent_runtime_accessors import (
    resolve_active_intent_kind_from_input_variables,
    resolve_intent_plan_view,
)
from .tool_policy_semantics import tool_semantic_family
from .turn_research_helpers import has_page_context


def first_page_intent_kind(
    *,
    user_text: str,
    tools: list[ToolDefinition],
    input_variables: dict[str, Any] | None = None,
) -> str | None:
    intents = resolve_intent_plan_view(input_variables)
    if not intents:
        active_intent_kind = resolve_active_intent_kind_from_input_variables(
            input_variables
        )
        if active_intent_kind and str(active_intent_kind).startswith("page_"):
            return active_intent_kind
        detected_signal = detect_page_signal(
            clause=user_text,
            offset=0,
            input_variables=input_variables,
        )
        if detected_signal:
            return detected_signal.kind
        if has_page_context(input_variables) and mentions_page_summary(user_text):
            return "page_summary"
        return None
    for intent in intents:
        if intent.family == "page_ops":
            return intent.kind
    return None


def looks_like_generic_page_summary_request(
    user_text: str,
    tools: list[ToolDefinition],
    input_variables: dict[str, Any] | None = None,
) -> bool:
    normalized = (user_text or "").strip()
    if not normalized:
        return False
    page_intent_kind = first_page_intent_kind(
        user_text=normalized,
        tools=tools,
        input_variables=input_variables,
    )
    if page_intent_kind != "page_summary":
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
    "looks_like_generic_page_summary_request",
    "restrict_page_tools_for_generic_summary",
]
