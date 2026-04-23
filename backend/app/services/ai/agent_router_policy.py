"""
Agent router policy helpers (intent detection, page-operation routing signals).
"""

from __future__ import annotations

from typing import Any

from app.ai.engine.intent_clause_helpers import _split_clauses
from app.ai.engine.intent_page_rules import detect_page_signal
from app.ai.navigation_semantics import has_navigation_intent
from app.ai.text_semantics import collapse_whitespace
from app.ai.tools.semantic_defaults import (
    page_context_available_ui_tools,
    page_context_has_runtime_state,
)

PAGE_OPERATION_STRONG_INTENT_TOKENS = (
    "operate on the current page",
    "operate on this page",
    "perform the page action",
    "help me operate on the current page",
    "帮我操作当前页面",
    "帮我操作这个页面",
    "操作当前页面",
    "操作这个页面",
    "操作本页面",
    "帮我截图当前页面",
    "帮我截屏当前页面",
    "帮我编辑当前页面",
    "帮我填写当前表单",
)
PAGE_READONLY_WORKFLOW_GOALS = frozenset({"page_summary", "table_summary"})
PAGE_ROUTING_REQUIRED_READONLY_PROVENANCE = frozenset({"page_summary_shortcircuit"})
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


def page_context_has_runtime_ui_tools(page_context: dict[str, Any] | None) -> bool:
    return bool(
        page_context_has_runtime_state(page_context)
        and page_context_available_ui_tools(page_context)
    )


def requires_vision_page_operation(message: str) -> bool:
    normalized_message = _normalize_message(message)
    if not normalized_message:
        return False
    return any(
        token in normalized_message
        for token in (
            "截图",
            "截屏",
            "屏幕截图",
            "页面截图",
            "screenshot",
            "capture screenshot",
            "take a screenshot",
        )
    )


def page_context_supports_navigation(
    page_context: dict[str, Any] | None,
) -> bool:
    tool_names = set(page_context_available_ui_tools(page_context))
    return bool({"ui_click", "ui_open_surface", "ui_list_interactables"} & tool_names)


def _detect_page_signal(
    message: str,
    page_context: dict[str, Any] | None,
) -> Any | None:
    if not message or not page_context_has_runtime_ui_tools(page_context):
        return None
    return detect_page_signal(
        clause=message,
        offset=0,
        input_variables={"page_context": page_context},
    )


def _page_signal_snapshot(
    message: str,
    page_context: dict[str, Any] | None,
) -> dict[str, str] | None:
    signal = _detect_page_signal(message, page_context)
    if signal is None:
        return None
    payload = dict(signal.metadata or {})
    return {
        "workflow_goal": str(payload.get("page_workflow_goal") or "").strip(),
        "routing_mode": str(payload.get("routing_mode") or "").strip(),
        "routing_provenance": str(payload.get("routing_provenance") or "").strip(),
    }


def _is_page_scoped_search_request(
    message: str,
    page_context: dict[str, Any] | None,
) -> bool:
    page_signal = _page_signal_snapshot(message, page_context)
    return bool(
        page_context_has_runtime_ui_tools(page_context)
        and page_signal
        and page_signal["workflow_goal"] == "search"
    )


def _page_signal_requires_page_agent_routing(
    page_signal: dict[str, str] | None,
) -> bool:
    if not page_signal:
        return False
    normalized_goal = str(page_signal.get("workflow_goal") or "").strip()
    if not normalized_goal:
        return False
    if normalized_goal in PAGE_READONLY_WORKFLOW_GOALS:
        return (
            str(page_signal.get("routing_provenance") or "").strip()
            in PAGE_ROUTING_REQUIRED_READONLY_PROVENANCE
        )
    return True


def requires_page_operation_routing(
    message: str,
    page_context: dict[str, Any] | None,
) -> bool:
    if not message or not page_context:
        return False

    normalized_message = _normalize_message(message)
    if not normalized_message:
        return False

    page_signal = _page_signal_snapshot(message, page_context)
    if _page_signal_requires_page_agent_routing(page_signal):
        return True

    if not page_context_has_runtime_ui_tools(page_context):
        return False

    if any(token in normalized_message for token in PAGE_OPERATION_STRONG_INTENT_TOKENS):
        return True

    has_navigation_request = has_navigation_intent(
        normalized_message,
        page_context,
    )
    return bool(has_navigation_request)


def has_non_page_mixed_intent(
    message: str,
    page_context: dict[str, Any] | None = None,
) -> bool:
    normalized_message = _normalize_message(message)
    if not normalized_message:
        return False

    clauses = _iter_message_clauses(message)
    has_page_clause = any(
        _page_signal_snapshot(clause, page_context) is not None for clause in clauses
    )
    if not has_page_clause:
        return False

    for clause in clauses:
        normalized_clause = _normalize_message(clause)
        if not normalized_clause:
            continue
        if _is_page_scoped_search_request(clause, page_context):
            continue
        if any(token in normalized_clause for token in NON_PAGE_WEATHER_TOKENS):
            return True
        if any(token in normalized_clause for token in NON_PAGE_TIME_TOKENS):
            return True
        if any(token in normalized_clause for token in NON_PAGE_WEB_SEARCH_TOKENS):
            return True
        if "搜索" in normalized_clause or "搜" in normalized_clause:
            return True
    return False


def requested_tool_families(
    message: str,
    page_context: dict[str, Any] | None,
) -> list[str]:
    normalized_message = _normalize_message(message)
    if not normalized_message:
        return []

    families: list[str] = []

    def add(family: str) -> None:
        if family not in families:
            families.append(family)

    has_page_runtime_ui = page_context_has_runtime_ui_tools(page_context)
    for clause in _iter_message_clauses(message):
        normalized_clause = _normalize_message(clause)
        if not normalized_clause:
            continue
        page_signal = _page_signal_snapshot(clause, page_context)
        page_scoped_search_request = _is_page_scoped_search_request(
            clause,
            page_context,
        )

        if not page_scoped_search_request and any(
            token in normalized_clause for token in NON_PAGE_WEATHER_TOKENS
        ):
            add("weather")
        if not page_scoped_search_request and any(
            token in normalized_clause for token in NON_PAGE_TIME_TOKENS
        ):
            add("time_ops")
        if (
            not page_scoped_search_request
            and any(token in normalized_clause for token in NON_PAGE_WEB_SEARCH_TOKENS)
        ) or (
            not page_scoped_search_request
            and ("搜索" in normalized_clause or "搜" in normalized_clause)
        ):
            add("web_research")

        if has_page_runtime_ui and (
            page_signal is not None
            or page_scoped_search_request
            or requires_page_operation_routing(clause, page_context)
            or any(
                token in normalized_clause
                for token in PAGE_OPERATION_STRONG_INTENT_TOKENS
            )
        ):
            add("page_ops")

    return families


__all__ = [
    "NON_PAGE_TIME_TOKENS",
    "NON_PAGE_WEATHER_TOKENS",
    "NON_PAGE_WEB_SEARCH_TOKENS",
    "PAGE_OPERATION_STRONG_INTENT_TOKENS",
    "has_non_page_mixed_intent",
    "page_context_has_runtime_ui_tools",
    "page_context_supports_navigation",
    "requested_tool_families",
    "requires_page_operation_routing",
    "requires_vision_page_operation",
]
