"""
Agent router policy helpers (intent detection, page-operation routing signals).
"""

from __future__ import annotations

from typing import Any

from app.ai.engine.intent_clause_helpers import _split_clauses
from app.ai.engine.intent_page_rules import detect_page_signal
from app.ai.text_semantics import collapse_whitespace

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
    del page_context
    return False


def requires_vision_page_operation(message: str) -> bool:
    del message
    return False


def page_context_supports_navigation(
    page_context: dict[str, Any] | None,
) -> bool:
    del page_context
    return False


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
    del message, page_context
    return False


def has_non_page_mixed_intent(
    message: str,
    page_context: dict[str, Any] | None = None,
) -> bool:
    del message, page_context
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

    for clause in _iter_message_clauses(message):
        normalized_clause = _normalize_message(clause)
        if not normalized_clause:
            continue
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
