"""Semantic helpers for tool policy decisions."""

from __future__ import annotations

from typing import Any

from app.ai.text_semantics import (
    extract_textual_tool_call_names as extract_textual_tool_call_names_from_text,
)
from app.ai.text_semantics import (
    has_capability_denial_phrase,
    has_tool_planning_leak_phrase,
)
from app.ai.tools.semantic_defaults import (
    FAMILY_HINT_TAGS as _SEMANTIC_FAMILY_HINT_TAGS,
)
from app.ai.tools.semantic_defaults import (
    tool_family_from_name as _tool_family_from_name_unified,
)
from app.ai.tools.semantic_defaults import (
    tool_semantic_family as _tool_semantic_family_unified,
)
from app.ai.tools.semantic_defaults import (
    tool_semantic_tags as _tool_semantic_tags_unified,
)
from app.ai.tools.types import ToolDefinition


def tool_family_for_name(
    tool_name: str,
    input_variables: dict[str, Any] | None = None,
) -> str:
    return _tool_family_from_name_unified(tool_name, input_variables)


def tool_semantic_family(
    tool: ToolDefinition,
    input_variables: dict[str, Any] | None = None,
) -> str:
    return _tool_semantic_family_unified(tool, input_variables)


def tool_semantic_tags(tool: ToolDefinition) -> list[str]:
    return _tool_semantic_tags_unified(tool)


def family_capability_terms(
    family: str,
    tools: list[ToolDefinition],
    input_variables: dict[str, Any] | None = None,
) -> set[str]:
    from app.ai.tools.optimizer import _tokenize

    terms: set[str] = set()
    for hint in _SEMANTIC_FAMILY_HINT_TAGS.get(family, ()):
        normalized_hint = hint.strip().lower()
        if len(normalized_hint) >= 2:
            terms.add(normalized_hint)
        terms |= {token for token in _tokenize(hint) if len(token) >= 2}

    for tool in tools:
        if tool_semantic_family(tool, input_variables) != family:
            continue
        for value in [tool.name, tool.description or "", *tool_semantic_tags(tool)]:
            text = str(value or "").strip().lower()
            if len(text) >= 2:
                terms.add(text)
            terms |= {token for token in _tokenize(text) if len(token) >= 2}
    return terms


def response_denies_family_capability(
    *,
    normalized_text: str,
    family: str,
    tools: list[ToolDefinition],
    input_variables: dict[str, Any] | None,
) -> bool:
    if not has_capability_denial_phrase(normalized_text):
        return False
    capability_terms = family_capability_terms(family, tools, input_variables)
    return any(term in normalized_text for term in capability_terms)


def extract_textual_tool_call_names(
    response_text: str,
    tools: list[ToolDefinition],
) -> list[str]:
    text = " ".join((response_text or "").strip().split())
    if not text:
        return []

    known_tool_names = {tool.name for tool in tools} if tools else None
    tool_aliases: dict[str, str] = {}
    for tool in tools or []:
        tool_aliases[tool.name] = tool.name
        underlying_operation = str(
            (tool.config or {}).get("underlying_operation") or ""
        ).strip()
        if underlying_operation:
            tool_aliases[underlying_operation] = tool.name
    return extract_textual_tool_call_names_from_text(
        text,
        alias_to_tool_name=tool_aliases,
        known_tool_names=known_tool_names,
    )


def looks_like_tool_planning_leak(
    response_text: str,
    tools: list[ToolDefinition],
) -> bool:
    text = " ".join((response_text or "").strip().split())
    if not text:
        return False
    if not has_tool_planning_leak_phrase(text):
        return False
    return bool(extract_textual_tool_call_names(text, tools))


def looks_like_explicit_web_research_request(
    user_text: str,
    tools: list[ToolDefinition],
) -> bool:
    if not user_text or not tools:
        return False
    web_tools = [
        tool
        for tool in tools
        if tool_semantic_family(tool) == "web_research"
        or tool.name in {"web_search", "fetch_url"}
    ]
    if not web_tools:
        return False

    from app.ai.tools.optimizer import _tokenize

    query_text = user_text.lower()
    query_tokens = _tokenize(user_text)
    semantic_tokens: set[str] = set()
    for tool in web_tools:
        semantic_source = " ".join(
            [tool.name, tool.description or "", *tool_semantic_tags(tool)]
        )
        semantic_tokens |= _tokenize(semantic_source)

    if query_tokens & semantic_tokens:
        return True

    return any(
        tool.name.lower() in query_text
        or tool.name.lower().replace("_", " ") in query_text
        for tool in web_tools
    )


def looks_like_explicit_time_request(
    user_text: str,
    tools: list[ToolDefinition],
) -> bool:
    if not user_text or not tools:
        return False
    time_tools = [
        tool
        for tool in tools
        if tool_semantic_family(tool) == "time_ops" or tool.name == "get_current_time"
    ]
    if not time_tools:
        return False

    from app.ai.tools.optimizer import _tokenize

    query_tokens = _tokenize(user_text)
    semantic_tokens: set[str] = set()
    for tool in time_tools:
        semantic_source = " ".join(
            [tool.name, tool.description or "", *tool_semantic_tags(tool)]
        )
        semantic_tokens |= _tokenize(semantic_source)
    return bool(query_tokens & semantic_tokens)


__all__ = [
    "extract_textual_tool_call_names",
    "family_capability_terms",
    "looks_like_explicit_time_request",
    "looks_like_explicit_web_research_request",
    "looks_like_tool_planning_leak",
    "response_denies_family_capability",
    "tool_family_for_name",
    "tool_semantic_family",
    "tool_semantic_tags",
]
