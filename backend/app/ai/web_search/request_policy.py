"""Turn-level web-search request policy helpers."""

from __future__ import annotations

import re
from typing import Any

_DIRECT_WEB_TOOL_NAMES = ("web_search", "fetch_url")
_DIRECT_WEB_TOOL_PATTERN = re.compile(
    r"(?<![a-z0-9_])(?:web_search|fetch_url)(?![a-z0-9_])",
)
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
_EXPLICIT_BUILTIN_WEB_SEARCH_PHRASES = (
    "联网搜索技能",
    "网络搜索技能",
    "网上搜索技能",
    "联网搜索工具",
    "网络搜索工具",
    "网上搜索工具",
    "内置搜索",
    "内置搜索工具",
    "内置联网搜索",
    "内置联网搜索工具",
    "内置网络搜索",
    "内置的搜索",
    "内置的搜索工具",
    "内置的联网搜索",
    "内置的联网搜索工具",
    "系统内置搜索",
    "系统内置搜索工具",
    "系统内置的搜索能力",
    "自带的搜索工具",
    "builtin search",
    "built-in search",
    "built-in web search",
    "built in search",
    "built in web search",
    "internal web search",
)
_EXPLICIT_USE_WEB_SEARCH_PHRASES = (
    "使用搜索工具",
    "使用搜索技能",
    "使用联网搜索",
    "使用联网搜索工具",
    "使用系统内置搜索",
    "使用系统内置的搜索能力",
    "用搜索工具",
    "用搜索技能",
    "用内置搜索",
    "用内置的搜索工具",
    "用自带的搜索工具",
    "通过搜索工具",
    "通过搜索技能",
    "走搜索工具",
    "走搜索技能",
    "走内置搜索",
    "走内置的联网搜索",
    "use search tool",
    "use search skill",
    "use the search tool",
    "use the search skill",
    "use web search tool",
    "use web search skill",
    "use the web search tool",
    "use the web search skill",
    "use built-in web search",
    "use the built-in web search",
    "use internal web search",
    "with search tool",
    "with search skill",
    "using the search tool",
    "using the search skill",
    "using web search tool",
    "using the web search tool",
)
_EXPLICIT_CALL_WEB_SEARCH_PHRASES = (
    "调用联网搜索",
    "调用网络搜索",
    "调用网上搜索",
    "调用搜索工具",
    "调用搜索技能",
    "call web search",
    "call online search",
    "call search tool",
    "call search skill",
    "call web search tool",
    "call web search skill",
    "invoke web search",
    "invoke online search",
    "invoke search tool",
    "invoke search skill",
    "invoke web search tool",
    "invoke web search skill",
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

    if _DIRECT_WEB_TOOL_PATTERN.search(normalized):
        return True

    if any(phrase in normalized for phrase in _EXPLICIT_BUILTIN_WEB_SEARCH_PHRASES):
        return True

    if any(phrase in normalized for phrase in _EXPLICIT_USE_WEB_SEARCH_PHRASES):
        return True

    if any(phrase in normalized for phrase in _EXPLICIT_CALL_WEB_SEARCH_PHRASES):
        return True

    mentions_search = any(term in normalized for term in _WEB_SEARCH_TERMS)
    if not mentions_search:
        return False

    # Avoid false positives where "工具/skill/call" is the research subject,
    # e.g. "联网搜索最新 AI 工具" or "search how to call a tool".
    return False


__all__ = [
    "is_explicit_builtin_web_search_request",
    "normalize_web_search_request_text",
]
