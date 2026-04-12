"""
Agent router policy helpers (intent detection, page-operation routing signals).
"""

from __future__ import annotations

from typing import Any

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
PAGE_OPERATION_REFERENCE_TOKENS = (
    "current page",
    "current form",
    "current screen",
    "current editor",
    "current list",
    "current record",
    "this page",
    "this form",
    "当前页面",
    "当前表单",
    "这个页面",
    "本页面",
    "当前界面",
    "这个表单",
    "当前编辑器",
    "这个编辑器",
    "当前列表",
    "这条记录",
)
PAGE_OPERATION_ACTION_TOKENS = (
    "apply",
    "add",
    "append",
    "change",
    "capture",
    "click",
    "configure",
    "create",
    "delete",
    "edit",
    "fill",
    "filter",
    "paginate",
    "open",
    "read detail",
    "refresh",
    "replace",
    "save",
    "screenshot",
    "search",
    "select",
    "set",
    "switch to",
    "submit",
    "switch",
    "update",
    "visit",
    "go to",
    "jump to",
    "navigate",
    "上一页",
    "下一页",
    "分页",
    "详情",
    "进入",
    "添加",
    "保存",
    "修改",
    "切换",
    "切到",
    "创建",
    "删除",
    "刷新",
    "新增",
    "填写",
    "打开",
    "操作",
    "搜索",
    "提交",
    "跳转",
    "新建",
    "点击",
    "截图",
    "截屏",
    "编辑器",
    "筛选",
    "追加",
    "插入",
    "编辑",
    "设置",
    "配置",
)
PAGE_OPERATION_TARGET_TOKENS = (
    "button",
    "dialog",
    "drawer",
    "editor",
    "form",
    "list",
    "menu",
    "modal",
    "record",
    "screenshot",
    "tab",
    "按钮",
    "编辑器",
    "列表",
    "菜单",
    "记录",
    "表单",
    "页签",
    "弹窗",
    "抽屉",
    "对话框",
    "截图",
)
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
PAGE_SEARCH_CONTEXT_TOKENS = (
    "记录",
    "列表",
    "表格",
    "筛选",
    "过滤",
    "条件",
    "结果",
    "数据",
    "page",
    "list",
    "table",
    "filter",
)


def _normalize_message(message: str) -> str:
    return collapse_whitespace(message).strip().lower()


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


def requires_page_operation_routing(
    message: str,
    page_context: dict[str, Any] | None,
) -> bool:
    if not message or not page_context:
        return False

    normalized_message = _normalize_message(message)
    if not normalized_message:
        return False

    if not page_context_has_runtime_ui_tools(page_context):
        return False

    has_strong_intent = any(
        token in normalized_message for token in PAGE_OPERATION_STRONG_INTENT_TOKENS
    )
    if has_strong_intent:
        return True

    has_action_token = any(
        token in normalized_message for token in PAGE_OPERATION_ACTION_TOKENS
    )
    has_navigation_request = has_navigation_intent(
        normalized_message,
        page_context,
    )
    if has_navigation_request:
        return True

    if page_context_supports_navigation(page_context) and has_navigation_request:
        return True

    if not has_action_token:
        return False

    has_reference_token = any(
        token in normalized_message for token in PAGE_OPERATION_REFERENCE_TOKENS
    )
    if has_reference_token:
        return True

    return any(
        token in normalized_message for token in PAGE_OPERATION_TARGET_TOKENS
    )


def has_non_page_mixed_intent(message: str) -> bool:
    normalized_message = _normalize_message(message)
    if not normalized_message:
        return False

    if any(token in normalized_message for token in NON_PAGE_WEATHER_TOKENS):
        return True
    if any(token in normalized_message for token in NON_PAGE_TIME_TOKENS):
        return True
    if any(token in normalized_message for token in NON_PAGE_WEB_SEARCH_TOKENS):
        return True
    return ("搜索" in normalized_message or "搜" in normalized_message) and not any(
        token in normalized_message for token in PAGE_SEARCH_CONTEXT_TOKENS
    )


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

    if any(token in normalized_message for token in NON_PAGE_WEATHER_TOKENS):
        add("weather")
    if any(token in normalized_message for token in NON_PAGE_TIME_TOKENS):
        add("time_ops")
    if any(token in normalized_message for token in NON_PAGE_WEB_SEARCH_TOKENS) or (
        ("搜索" in normalized_message or "搜" in normalized_message)
        and not any(token in normalized_message for token in PAGE_SEARCH_CONTEXT_TOKENS)
    ):
        add("web_research")

    if page_context and (
        requires_page_operation_routing(message, page_context)
        or any(
            token in normalized_message for token in PAGE_OPERATION_REFERENCE_TOKENS
        )
        or "页面有什么" in normalized_message
        or "页面都能做什么" in normalized_message
    ):
        add("page_ops")

    return families


__all__ = [
    "NON_PAGE_TIME_TOKENS",
    "NON_PAGE_WEATHER_TOKENS",
    "NON_PAGE_WEB_SEARCH_TOKENS",
    "PAGE_OPERATION_ACTION_TOKENS",
    "PAGE_OPERATION_REFERENCE_TOKENS",
    "PAGE_OPERATION_STRONG_INTENT_TOKENS",
    "PAGE_OPERATION_TARGET_TOKENS",
    "PAGE_SEARCH_CONTEXT_TOKENS",
    "has_non_page_mixed_intent",
    "page_context_has_runtime_ui_tools",
    "page_context_supports_navigation",
    "requested_tool_families",
    "requires_page_operation_routing",
    "requires_vision_page_operation",
]
