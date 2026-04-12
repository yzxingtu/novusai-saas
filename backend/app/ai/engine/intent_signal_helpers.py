"""Shared intent signal helpers extracted from IntentPlanner."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.ai.tools.semantic_defaults import (
    page_context_available_ui_tools,
    tool_semantic_family,
)
from app.ai.tools.types import ToolDefinition
from app.ai.types import ChatMessage
from app.schemas.ai.agent_chat import PAGE_CONTEXT_KEY


@dataclass(frozen=True)
class _IntentSignal:
    kind: str
    family: str
    label: str
    position: int
    requires_tools: bool = True
    shortcircuit: bool = False
    continuation: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


def _last_user_text(messages: list[ChatMessage]) -> str:
    for message in reversed(messages):
        if message.role == "user":
            return (message.content or "").strip()
    return ""


def _has_page_context(input_variables: dict[str, Any] | None) -> bool:
    if not isinstance(input_variables, dict):
        return False
    page_context = input_variables.get(PAGE_CONTEXT_KEY)
    return isinstance(page_context, dict) and bool(
        str(page_context.get("page_key") or "").strip()
    )


def _page_operation_names(input_variables: dict[str, Any] | None) -> set[str]:
    if not isinstance(input_variables, dict):
        return set()
    page_context = input_variables.get(PAGE_CONTEXT_KEY)
    return set(page_context_available_ui_tools(page_context))


def _tool_families(
    tools: list[ToolDefinition],
    input_variables: dict[str, Any] | None,
) -> set[str]:
    families = {
        tool_semantic_family(tool, input_variables)
        for tool in tools
        if tool_semantic_family(tool, input_variables) != "none"
    }
    if input_variables and _has_page_context(input_variables):
        families.add("page_ops")
    return families


def _continuation_families(continuation_context: Any | None) -> set[str]:
    if continuation_context is None:
        return set()
    families = {
        str(family or "").strip()
        for family in getattr(
            continuation_context,
            "continuation_capable_families",
            [],
        )
        if str(family or "").strip()
    }
    active_family = str(getattr(continuation_context, "family", "") or "").strip()
    if active_family:
        families.add(active_family)
    tool_families = getattr(continuation_context, "tool_families", []) or []
    families.update(
        str(family or "").strip()
        for family in tool_families
        if str(family or "").strip()
    )
    return families


def _first_position(text: str, candidates: tuple[str, ...]) -> int:
    positions = [
        text.find(item) for item in candidates if item and text.find(item) >= 0
    ]
    return min(positions) if positions else -1


__all__ = [
    "_IntentSignal",
    "_continuation_families",
    "_first_position",
    "_has_page_context",
    "_last_user_text",
    "_page_operation_names",
    "_tool_families",
]
