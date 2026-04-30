"""
Agent router policy helpers for non-page AI routing signals.
"""

from __future__ import annotations

from app.ai.engine.intent_clause_helpers import _split_clauses
from app.ai.text_semantics import collapse_whitespace

NON_PAGE_WEATHER_TOKENS = (
    "天气",
    "气温",
    "温度",
    "weather",
)
NON_PAGE_TIME_TOKENS = (
    "几点",
    "星期几",
    "周几",
    "几号",
    "current time",
    "what day is it",
)
NON_PAGE_WEB_SEARCH_TOKENS = (
    "联网",
    "网上查",
    "网络搜索",
    "官网",
    "链接",
    "url",
    "网址",
    "网页",
    "web search",
    "search online",
    "online search",
    "fetch",
    "新闻",
    "热点",
    "排行",
    "高铁票",
    "火车票",
    "12306",
)


def _normalize_message(message: str) -> str:
    return collapse_whitespace(message).strip().lower()


def _iter_message_clauses(message: str) -> list[str]:
    text = str(message or "").strip()
    if not text:
        return []
    clauses = [clause.strip() for _offset, clause in _split_clauses(text) if clause.strip()]
    return clauses or [text]


def requested_tool_families(message: str) -> list[str]:
    """Infer explicit non-page tool families requested by the user's message."""
    normalized_message = _normalize_message(message)
    if not normalized_message:
        return []

    families: list[str] = []

    def add(family: str) -> None:
        if family not in families:
            families.append(family)

    for clause in _iter_message_clauses(message):
        normalized_clause = _normalize_message(clause)
        if not normalized_clause:
            continue

        if any(token in normalized_clause for token in NON_PAGE_WEATHER_TOKENS):
            add("weather")
        if any(token in normalized_clause for token in NON_PAGE_TIME_TOKENS):
            add("time_ops")
        if any(token in normalized_clause for token in NON_PAGE_WEB_SEARCH_TOKENS) or (
            "搜索" in normalized_clause or "搜" in normalized_clause
        ):
            add("web_research")

    return families


__all__ = [
    "NON_PAGE_TIME_TOKENS",
    "NON_PAGE_WEATHER_TOKENS",
    "NON_PAGE_WEB_SEARCH_TOKENS",
    "requested_tool_families",
]
