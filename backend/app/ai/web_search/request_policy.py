"""Turn-level web-search request policy helpers."""

from __future__ import annotations

from typing import Any

_DIRECT_WEB_TOOL_NAMES = ("web_search", "fetch_url")
_WEB_SEARCH_TERMS = (
    "联网搜索",
    "网络搜索",
    "网上搜索",
    "网上查",
    "搜索",
    "搜",
    "web search",
    "search online",
    "online search",
    "fetch",
    "url",
    "网址",
    "网页",
)
_TOOL_OR_SKILL_TERMS = (
    "技能",
    "工具",
    "tool",
    "skill",
    "builtin",
    "built-in",
    "内置",
)
_CALL_TERMS = (
    "调用",
    "call",
    "invoke",
)


def normalize_web_search_request_text(value: Any) -> str:
    """Normalize free-form user text for stable policy checks."""

    return " ".join(str(value or "").strip().lower().split())


def is_explicit_builtin_web_search_request(user_text: Any) -> bool:
    """
    Return true only when the user asks for the builtin/skill/tool search path.

    Generic current-information requests such as "联网查一下最新消息" are not
    explicit builtin requests; those should prefer provider-native web search.
    """

    normalized = normalize_web_search_request_text(user_text)
    if not normalized:
        return False

    if any(tool_name in normalized for tool_name in _DIRECT_WEB_TOOL_NAMES):
        return True

    mentions_search = any(term in normalized for term in _WEB_SEARCH_TERMS)
    if not mentions_search:
        return False

    if any(term in normalized for term in _TOOL_OR_SKILL_TERMS):
        return True
    return any(term in normalized for term in _CALL_TERMS)


__all__ = [
    "is_explicit_builtin_web_search_request",
    "normalize_web_search_request_text",
]
