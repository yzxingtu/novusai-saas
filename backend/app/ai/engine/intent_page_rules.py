"""Page intent rules extracted from the intent planner for reuse."""

from __future__ import annotations

import re
from typing import Any

from app.ai.engine.intent_signal_helpers import (
    _continuation_families,
    _first_position,
    _has_page_context,
    _IntentSignal,
    _page_operation_names,
)
from app.ai.navigation_semantics import has_navigation_intent
from app.ai.tools.semantic_defaults import tool_semantic_family
from app.ai.tools.types import ToolDefinition

PageIntentSignal = _IntentSignal
continuation_families = _continuation_families
first_position = _first_position
has_page_context = _has_page_context
page_operation_names = _page_operation_names

_EXPLICIT_EXTERNAL_URL_RE = re.compile(r"https?://[^\s<>()\[\]\"']+", re.IGNORECASE)

_PAGE_POINTER_TERMS = (
    "这个页面",
    "当前页面",
    "本页面",
    "本页",
    "列表",
    "表格",
    "页面内容",
    "页面里",
    "页面上",
    "这个表格",
    "当前表格",
    "这个列表",
    "当前列表",
    "这个表单",
    "当前表单",
    "这条记录",
    "当前记录",
    "this page",
    "current page",
    "page content",
    "page contents",
    "on this page",
)
_PAGE_SUMMARY_TERMS = (
    "读取页面",
    "分析页面",
    "查看页面",
    "读一下页面",
    "总结页面",
    "页面有什么内容",
    "看看页面",
    "看看本页面",
    "阅读一下当前页面",
    "read this page",
    "read the page",
    "analyze this page",
    "summarize this page",
    "what is on this page",
    "what's on this page",
    "what does this page contain",
)
_PAGE_FORM_WRITE_TERMS = (
    "创建",
    "新增",
    "添加",
    "修改",
    "编辑",
    "删除",
    "填写",
    "提交",
    "保存",
    "更新",
    "创建记录",
    "新增记录",
    "编辑记录",
    "填写表单",
    "提交表单",
    "保存表单",
    "create",
    "add",
    "edit",
    "update",
    "delete",
    "submit",
    "save",
    "fill",
)
_PAGE_FORM_READ_TERMS = (
    "表单状态",
    "表单选项",
    "读取表单",
    "查看表单",
    "当前表单",
    "必填项",
    "必填字段",
    "required fields",
    "required field",
    "form state",
    "form options",
    "read form",
)
_PAGE_NAV_TERMS = (
    "打开",
    "前往",
    "跳转",
    "进入",
    "导航",
    "去到",
    "切换到",
    "新页面",
    "新的页面",
    "open",
    "go to",
    "navigate",
    "switch to",
)
_PAGE_SEARCH_TERMS = (
    "搜索记录",
    "搜索列表",
    "在页面里搜索",
    "查找记录",
    "清空搜索",
    "清除搜索",
    "清空筛选",
    "清除筛选",
    "刷新列表",
    "刷新表格",
    "筛选",
    "过滤",
    "search records",
    "search the list",
    "clear search",
    "clear filter",
    "refresh list",
)
_PAGE_SEARCH_QUALIFIER_TERMS = (
    "记录",
    "列表",
    "表格",
    "筛选",
    "过滤",
    "条件",
    "结果",
    "数据",
    "搜索条件",
    "搜索结果",
    "页内",
    "页面里",
    "页面上",
    "当前页",
    "本页",
    "records",
    "list",
    "table",
    "filter",
)
_PAGE_SCREENSHOT_TERMS = (
    "截图",
    "截屏",
    "屏幕截图",
    "页面截图",
    "capture screenshot",
    "take a screenshot",
    "screenshot this page",
)
_PAGE_EDITOR_READ_TERMS = (
    "编辑器内容",
    "读取编辑器",
    "查看编辑器",
    "富文本内容",
    "editor content",
    "editor html",
    "editor text",
    "read editor",
)
_PAGE_EDITOR_WRITE_TERMS = (
    "改写正文",
    "替换正文",
    "替换内容",
    "追加内容",
    "追加",
    "插入内容",
    "更新标题",
    "修改标题",
    "替换章节",
    "rewrite section",
    "replace content",
    "append content",
    "insert content",
    "update title",
)
_PAGE_ROW_DETAIL_TERMS = (
    "明细",
    "详情",
    "查看详情",
    "这条记录",
    "可见记录",
    "可见行",
    "row detail",
    "visible rows",
    "read row detail",
)
_PAGE_PAGINATION_TERMS = (
    "下一页",
    "上一页",
    "翻页",
    "分页",
    "每页",
    "page size",
    "next page",
    "prev page",
    "previous page",
    "go to page",
)
_PAGE_CAPABILITY_TERMS = ("页面感知能力", "页面能力", "页面操作能力")
_PAGE_CONTINUE_TERMS = (
    "继续看",
    "再看看",
    "接着看",
    "继续看看",
    "再看一下",
    "接着看看",
)
_PAGE_CONTINUE_SCREENSHOT_TERMS = (
    "截个图看",
    "截一下图",
    "给我看截图",
)
_PAGE_CONTINUE_DETAIL_TERMS = (
    "看这个区域",
    "点进去看",
    "展开看看",
    "展开看",
    "看里面",
    "点开看",
    "继续看下去",
)
_PAGE_CONTINUE_ACTION_TERMS = (
    *_PAGE_CONTINUE_TERMS,
    *_PAGE_CONTINUE_SCREENSHOT_TERMS,
    *_PAGE_CONTINUE_DETAIL_TERMS,
    "截图",
    "截屏",
    "点进去",
    "点开",
    "展开",
    "看看",
)


def _page_context_from_input_variables(
    input_variables: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if not isinstance(input_variables, dict):
        return None
    page_context = input_variables.get("page_context")
    return page_context if isinstance(page_context, dict) else None


def looks_like_short_directive_follow_up(text: str) -> bool:
    normalized = re.sub(r"\s+", "", str(text or "").strip().lower())
    if not normalized:
        return False
    if "?" in normalized or "？" in normalized:
        return False
    if len(normalized) <= 10:
        return True
    return len(normalized) <= 18 and len(normalized.split()) <= 6


def looks_like_page_follow_up(text: str) -> bool:
    lowered = str(text or "").strip().lower()
    if not lowered:
        return False
    if first_position(lowered, _PAGE_CONTINUE_ACTION_TERMS) >= 0:
        return True
    return looks_like_short_directive_follow_up(lowered) and any(
        token in lowered for token in ("看", "截图", "截屏", "展开", "点", "明细", "详情")
    )


def page_continuation_intent_kind(
    *,
    clause: str,
    input_variables: dict[str, Any] | None,
    continuation_context: Any | None,
) -> str:
    lowered = clause.lower()
    page_context = _page_context_from_input_variables(input_variables)
    if first_position(lowered, _PAGE_CONTINUE_SCREENSHOT_TERMS) >= 0 or (
        first_position(lowered, _PAGE_SCREENSHOT_TERMS) >= 0
        and looks_like_page_follow_up(lowered)
    ):
        return "page_screenshot"
    if has_navigation_intent(clause, page_context) or any(
        token in lowered for token in ("点进去", "点开", "打开", "进入", "展开")
    ):
        return "page_navigation"
    if first_position(lowered, _PAGE_CONTINUE_DETAIL_TERMS) >= 0 or any(
        token in lowered for token in ("区域", "明细", "详情")
    ):
        page_ops = page_operation_names(input_variables)
        if {"read_visible_rows", "read_row_detail", "open_row_detail"} & page_ops:
            return "page_row_detail"
    active_intent_kind = str(
        getattr(continuation_context, "active_intent_kind", "") or ""
    ).strip()
    if active_intent_kind.startswith("page_") and active_intent_kind not in {
        "page_form_write",
        "page_editor_write",
    }:
        return active_intent_kind
    return "page_summary"


def detect_page_continuation_signal(
    *,
    clause: str,
    offset: int,
    input_variables: dict[str, Any] | None,
    continuation_context: Any | None,
) -> PageIntentSignal | None:
    if not has_page_context(input_variables):
        return None
    active_families = continuation_families(continuation_context)
    if "page_ops" not in active_families:
        return None

    active_family = str(getattr(continuation_context, "family", "") or "").strip()
    active_intent_kind = str(
        getattr(continuation_context, "active_intent_kind", "") or ""
    ).strip()
    last_tool_name = str(getattr(continuation_context, "last_tool_name", "") or "").strip()
    prior_page_family = (
        active_family == "page_ops"
        or active_intent_kind.startswith("page_")
        or tool_semantic_family(
            ToolDefinition(name=last_tool_name, description=""),
            input_variables,
        )
        == "page_ops"
    )
    if not prior_page_family:
        return None

    lowered = clause.lower()
    if not looks_like_page_follow_up(lowered):
        return None

    intent_kind = page_continuation_intent_kind(
        clause=clause,
        input_variables=input_variables,
        continuation_context=continuation_context,
    )
    return PageIntentSignal(
        kind=intent_kind,
        family="page_ops",
        label=intent_kind,
        position=offset,
        shortcircuit=(intent_kind == "page_summary"),
        continuation=True,
        metadata={"continuation_source": "page_ops"},
    )


def looks_like_page_jump_request(lowered: str) -> bool:
    return any(token in lowered for token in _PAGE_PAGINATION_TERMS) or (
        "页" in lowered and any(token in lowered for token in ("第", "上一", "下一", "每页"))
    )


def looks_like_page_search_request(lowered: str) -> bool:
    explicit_page_search = first_position(lowered, _PAGE_SEARCH_TERMS) >= 0
    if explicit_page_search:
        return True
    if "搜索" not in lowered and "搜" not in lowered and "查找" not in lowered:
        return False
    return first_position(lowered, _PAGE_POINTER_TERMS + _PAGE_SEARCH_QUALIFIER_TERMS) >= 0


def looks_like_read_only_form_instruction(lowered: str) -> bool:
    if not lowered:
        return False
    hints = ("不要", "别", "先不要", "不需要", "暂时不", "不要帮我")
    actions = ("创建", "新增", "填", "提交", "点击", "operate", "create", "click")
    return any(hint in lowered for hint in hints) and any(
        action in lowered for action in actions
    )


def explicit_external_url_position(clause: str) -> int:
    match = _EXPLICIT_EXTERNAL_URL_RE.search(str(clause or "").strip())
    return match.start() if match else -1


def looks_like_required_field_form_read(lowered: str) -> bool:
    if "表单" not in lowered and "form" not in lowered:
        return False
    return any(token in lowered for token in ("必填", "required"))


def looks_like_field_listing_form_read(
    lowered: str,
    page_context: dict[str, Any] | None,
) -> bool:
    has_field_term = any(token in lowered for token in ("字段", "field", "fields"))
    if not has_field_term:
        return False
    if "表单" in lowered or "form" in lowered:
        return True
    if not isinstance(page_context, dict):
        return False
    active_form_session_id = str(page_context.get("active_form_session_id") or "").strip()
    active_form_summary = page_context.get("active_form_summary")
    has_active_form = bool(active_form_session_id) or isinstance(active_form_summary, dict)
    if not has_active_form:
        return False
    return any(token in lowered for token in ("当前", "这个", "里面", "哪些", "有哪些"))


def detect_page_signal(
    *,
    clause: str,
    offset: int,
    input_variables: dict[str, Any] | None,
) -> PageIntentSignal | None:
    lowered = clause.lower()
    if not has_page_context(input_variables):
        return None
    page_context = _page_context_from_input_variables(input_variables)
    explicit_url_position = explicit_external_url_position(clause)
    explicit_page_reference = (
        first_position(
            lowered,
            _PAGE_POINTER_TERMS
            + _PAGE_FORM_READ_TERMS
            + _PAGE_SEARCH_TERMS
            + _PAGE_SCREENSHOT_TERMS
            + _PAGE_EDITOR_READ_TERMS
            + _PAGE_EDITOR_WRITE_TERMS
            + _PAGE_ROW_DETAIL_TERMS
            + _PAGE_CAPABILITY_TERMS,
        )
        >= 0
    )
    if (
        explicit_url_position >= 0
        and not explicit_page_reference
        and not has_navigation_intent(clause, page_context)
    ):
        return None

    page_position = first_position(
        lowered,
        _PAGE_POINTER_TERMS
        + _PAGE_SUMMARY_TERMS
        + _PAGE_FORM_READ_TERMS
        + _PAGE_FORM_WRITE_TERMS
        + _PAGE_NAV_TERMS
        + _PAGE_SEARCH_TERMS
        + _PAGE_SCREENSHOT_TERMS
        + _PAGE_EDITOR_READ_TERMS
        + _PAGE_EDITOR_WRITE_TERMS
        + _PAGE_ROW_DETAIL_TERMS
        + _PAGE_CAPABILITY_TERMS,
    )
    if page_position < 0 and not any(
        token in lowered
        for token in (
            "搜索",
            "查找",
            "刷新",
            "筛选",
            "截图",
            "编辑器",
            "表单",
            "字段",
            "field",
            "fields",
            "分页",
            "上一页",
            "下一页",
            "翻页",
            "每页",
            "详情",
        )
    ):
        return None

    candidates: list[tuple[int, int, PageIntentSignal]] = []

    def add_candidate(kind: str, label: str, position: int, priority: int) -> None:
        if position < 0:
            return
        candidates.append(
            (
                position,
                priority,
                PageIntentSignal(
                    kind,
                    "page_ops",
                    label,
                    offset + position,
                    shortcircuit=(kind == "page_summary"),
                ),
            )
        )

    nav_position = first_position(lowered, _PAGE_NAV_TERMS)
    if has_navigation_intent(clause, page_context) or nav_position >= 0:
        add_candidate(
            "page_navigation",
            "page_navigation",
            nav_position if nav_position >= 0 else max(page_position, 0),
            0,
        )

    add_candidate(
        "page_screenshot",
        "page_screenshot",
        first_position(lowered, _PAGE_SCREENSHOT_TERMS),
        1,
    )

    editor_anchor = lowered.find("编辑器")
    editor_write_position = first_position(lowered, _PAGE_EDITOR_WRITE_TERMS)
    if editor_anchor >= 0 and any(
        token in lowered for token in ("修改", "改写", "优化", "润色", "追加", "插入", "标题", "正文")
    ):
        editor_write_position = (
            editor_anchor
            if editor_write_position < 0
            else min(editor_anchor, editor_write_position)
        )
    add_candidate("page_editor_write", "page_editor_write", editor_write_position, 2)

    editor_read_position = first_position(lowered, _PAGE_EDITOR_READ_TERMS)
    if editor_anchor >= 0 and any(
        token in lowered for token in ("什么", "内容", "html", "文本")
    ):
        editor_read_position = (
            editor_anchor
            if editor_read_position < 0
            else min(editor_anchor, editor_read_position)
        )
    add_candidate("page_editor_read", "page_editor_read", editor_read_position, 3)

    form_write_position = first_position(lowered, _PAGE_FORM_WRITE_TERMS)
    if not (editor_anchor >= 0 and editor_write_position >= 0) and not looks_like_read_only_form_instruction(
        lowered
    ):
        add_candidate("page_form_write", "page_form_write", form_write_position, 4)

    form_read_position = first_position(lowered, _PAGE_FORM_READ_TERMS)
    if looks_like_required_field_form_read(lowered):
        form_anchor = lowered.find("表单")
        if form_anchor < 0:
            form_anchor = lowered.find("form")
        required_anchor = lowered.find("必填")
        if required_anchor < 0:
            required_anchor = lowered.find("required")
        for anchor in (form_anchor, required_anchor):
            if anchor >= 0 and (form_read_position < 0 or anchor < form_read_position):
                form_read_position = anchor
    if looks_like_field_listing_form_read(lowered, page_context):
        field_anchor = lowered.find("字段")
        if field_anchor < 0:
            field_anchor = lowered.find("field")
        form_anchor = lowered.find("表单")
        if form_anchor < 0:
            form_anchor = lowered.find("form")
        for anchor in (form_anchor, field_anchor):
            if anchor >= 0 and (form_read_position < 0 or anchor < form_read_position):
                form_read_position = anchor
    add_candidate("page_form_read", "page_form_read", form_read_position, 5)

    search_position = first_position(lowered, _PAGE_SEARCH_TERMS)
    if search_position < 0 and looks_like_page_search_request(lowered):
        search_position = lowered.find("搜索")
    add_candidate("page_search", "page_search", search_position, 6)

    pagination_position = (
        first_position(lowered, _PAGE_PAGINATION_TERMS)
        if looks_like_page_jump_request(lowered)
        else -1
    )
    add_candidate("page_pagination", "page_pagination", pagination_position, 7)
    add_candidate(
        "page_row_detail",
        "page_row_detail",
        first_position(lowered, _PAGE_ROW_DETAIL_TERMS),
        8,
    )

    if not candidates:
        summary_position = first_position(
            lowered,
            _PAGE_SUMMARY_TERMS + _PAGE_POINTER_TERMS + _PAGE_CAPABILITY_TERMS,
        )
        add_candidate(
            "page_summary",
            "page_summary",
            summary_position if summary_position >= 0 else page_position,
            9,
        )

    if not candidates:
        return None
    return min(candidates, key=lambda item: (item[0], item[1]))[2]


__all__ = [
    "PageIntentSignal",
    "continuation_families",
    "detect_page_continuation_signal",
    "detect_page_signal",
    "first_position",
    "has_page_context",
    "looks_like_page_follow_up",
    "looks_like_page_jump_request",
    "looks_like_page_search_request",
    "looks_like_required_field_form_read",
    "looks_like_read_only_form_instruction",
    "page_continuation_intent_kind",
    "page_operation_names",
]
