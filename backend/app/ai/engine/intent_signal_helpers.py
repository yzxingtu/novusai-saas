"""Shared intent signal helpers extracted from IntentPlanner."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.ai.text_semantics import (
    extract_cjk_bigram_and_word_tokens,
    normalize_match_text,
)
from app.ai.tools.semantic_defaults import tool_semantic_family
from app.ai.tools.types import ToolDefinition
from app.ai.types import ChatMessage


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


_ROUTING_SEMANTIC_STOPWORDS = frozenset(
    {
        "",
        "请",
        "请问",
        "帮我",
        "麻烦",
        "麻烦你",
        "一下",
        "一下子",
        "一下下",
        "帮",
        "我",
        "你",
        "他",
        "她",
        "它",
        "这",
        "这个",
        "那个",
        "当前",
        "现在",
        "一下吧",
        "the",
        "this",
        "that",
        "please",
        "help",
        "with",
        "for",
        "and",
        "then",
    }
)


def _last_user_text(messages: list[ChatMessage]) -> str:
    for message in reversed(messages):
        if message.role == "user":
            return (message.content or "").strip()
    return ""


def _tool_families(
    tools: list[ToolDefinition],
    input_variables: dict[str, Any] | None,
) -> set[str]:
    return {
        tool_semantic_family(tool, input_variables)
        for tool in tools
        if tool_semantic_family(tool, input_variables) != "none"
    }


def _continuation_families(continuation_context: Any | None) -> set[str]:
    if continuation_context is None:
        return set()
    retired_families = {"data_ops"}

    def _active_family(value: Any) -> str:
        family = str(value or "").strip()
        return "" if family in retired_families else family

    families = {
        normalized_family
        for family in getattr(
            continuation_context,
            "continuation_capable_families",
            [],
        )
        if (normalized_family := _active_family(family))
    }
    active_family = _active_family(getattr(continuation_context, "family", ""))
    if active_family:
        families.add(active_family)
    tool_families = getattr(continuation_context, "tool_families", []) or []
    families.update(
        normalized_family
        for family in tool_families
        if (normalized_family := _active_family(family))
    )
    return families


def _first_position(text: str, candidates: tuple[str, ...]) -> int:
    positions = [
        text.find(item) for item in candidates if item and text.find(item) >= 0
    ]
    return min(positions) if positions else -1


def _semantic_tokens(
    text: str,
    *,
    stopwords: set[str] | frozenset[str] | None = None,
) -> set[str]:
    blocked = set(_ROUTING_SEMANTIC_STOPWORDS)
    if stopwords:
        blocked.update(normalize_match_text(item) for item in stopwords if item)
    raw_tokens = extract_cjk_bigram_and_word_tokens(
        normalize_match_text(text),
        stopwords=blocked,
    )
    return {token for token in raw_tokens if len(token) >= 2}


def _semantic_profile_position(
    text: str,
    profiles: tuple[str, ...],
    *,
    min_score: int = 2,
    stopwords: set[str] | frozenset[str] | None = None,
) -> int:
    normalized = normalize_match_text(text)
    if not normalized:
        return -1

    text_tokens = _semantic_tokens(normalized, stopwords=stopwords)
    if not text_tokens:
        return -1

    best_score = 0
    best_position = -1
    for profile in profiles:
        profile_tokens = _semantic_tokens(profile, stopwords=stopwords)
        if not profile_tokens:
            continue
        overlap = text_tokens & profile_tokens
        score = len(overlap)
        if score < min_score:
            continue
        position_candidates = [
            normalized.find(token)
            for token in overlap
            if token and normalized.find(token) >= 0
        ]
        position = min(position_candidates) if position_candidates else -1
        if score > best_score or (
            score == best_score
            and position >= 0
            and (best_position < 0 or position < best_position)
        ):
            best_score = score
            best_position = position
    return best_position


__all__ = [
    "_IntentSignal",
    "_continuation_families",
    "_first_position",
    "_last_user_text",
    "_semantic_profile_position",
    "_semantic_tokens",
    "_tool_families",
]
