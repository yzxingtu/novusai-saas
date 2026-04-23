"""Page intent rules extracted from the intent planner for reuse."""

from __future__ import annotations

import re
from typing import Any

from app.ai.engine.intent_runtime_accessors import resolve_intent_plan_view
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

_PAGE_WORKFLOW_KIND = "page_workflow"
_PAGE_WORKFLOW_GOALS: dict[str, str] = {
    "page_summary": "page_summary",
    "page_screenshot": "page_screenshot",
    "page_navigation": "navigation",
    "page_search": "search",
    "page_pagination": "pagination",
    "page_row_detail": "row_detail",
    "page_form_read": "form_read",
    "page_form_write": "form_write",
    "page_editor_read": "editor_read",
    "page_editor_write": "editor_write",
}
_PAGE_WORKFLOW_ALIASES_BY_GOAL: dict[str, str] = {
    goal: alias for alias, goal in _PAGE_WORKFLOW_GOALS.items()
}

_EXPLICIT_EXTERNAL_URL_RE = re.compile(r"https?://[^\s<>()\[\]\"']+", re.IGNORECASE)
_NEGATED_PAGE_REFERENCE_PATTERNS = (
    re.compile(
        r"(?:不要|别|不用|不必|无需)[^，,。；;]{0,8}"
        r"(?:参考|基于|看|查看|读取|分析)?[^，,。；;]{0,4}"
        r"(?:当前页面|本页面|这个页面|本页|页面内容|页面里|页面上|当前页)"
    ),
    re.compile(
        r"(?:do not|don't|without)[^,.;]{0,16}"
        r"(?:use|reference|read|inspect|look at)?[^,.;]{0,6}"
        r"(?:this page|current page|page content|page contents|on this page)",
        re.IGNORECASE,
    ),
)

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
_PAGE_FORM_WRITE_TERMS = (
    "创建",
    "新增",
    "添加",
    "绑定",
    "授权",
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
    "bind",
    "grant",
    "edit",
    "update",
    "delete",
    "submit",
    "save",
    "fill",
)
_GENERIC_PAGE_FORM_WRITE_TERMS = frozenset(
    {
        "创建",
        "新增",
        "添加",
        "绑定",
        "授权",
        "修改",
        "编辑",
        "删除",
        "填写",
        "提交",
        "保存",
        "更新",
        "create",
        "add",
        "bind",
        "grant",
        "edit",
        "update",
        "delete",
        "submit",
        "save",
        "fill",
    }
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
_PAGE_CONTINUE_NAVIGATION_TERMS = (
    "点进去",
    "点开",
    "打开",
    "进入",
    "展开",
    "点击",
    "单击",
    "click",
)
_PAGE_CONTINUE_ACTION_TERMS = (
    *_PAGE_CONTINUE_TERMS,
    *_PAGE_CONTINUE_SCREENSHOT_TERMS,
    *_PAGE_CONTINUE_DETAIL_TERMS,
    *_PAGE_CONTINUE_NAVIGATION_TERMS,
    "截图",
    "截屏",
    "看看",
)
_PAGE_ROW_DETAIL_TOOL_NAMES = frozenset(
    {
        "ui_click",
        "ui_open_surface",
        "ui_read_region",
        "ui_read_table",
    }
)
_PAGE_WRITE_ANCHOR_TERMS = (
    *_PAGE_POINTER_TERMS,
    *_PAGE_SEARCH_QUALIFIER_TERMS,
    "表单",
    "字段",
    "按钮",
    "菜单",
    "技能",
    "技能包",
    "权限",
    "知识库",
    "skill",
    "skills",
    "permission",
    "knowledge base",
    "field",
    "fields",
    "button",
    "menu",
)
_EXPLICIT_PAGE_SUMMARY_RE = re.compile(
    r"(?:查看|读取|阅读|总结|概括|分析|看看|read|summarize|analyze|review)"
    r"[^。！？?]{0,24}"
    r"(?:当前页面|本页面|这个页面|页面内容|当前页|本页|this page|current page|page content|page contents)",
    re.IGNORECASE,
)
_COLLOQUIAL_PAGE_SUMMARY_RE = re.compile(
    r"(?:这里|这儿)(?:都)?(?:有(?:什么|啥)|能做什么)"
)
_PAGE_PAGINATION_NUMBERED_RE = re.compile(
    r"(?:翻到|翻回|到)?第\s*[0-9一二三四五六七八九十]+\s*页",
    re.IGNORECASE,
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


def _pattern_position(text: str, pattern: re.Pattern[str]) -> int:
    match = pattern.search(text)
    return match.start() if match else -1


def _first_known_page_reference_position(text: str) -> int:
    positions = [
        first_position(text, _PAGE_POINTER_TERMS + _PAGE_SEARCH_TERMS + _PAGE_SCREENSHOT_TERMS),
        _page_summary_position(text),
        _page_form_read_position(text),
        _page_editor_read_position(text),
        _page_editor_write_position(text),
        _page_row_detail_position(text),
        _pattern_position(text, _COLLOQUIAL_PAGE_SUMMARY_RE),
    ]
    known_positions = [position for position in positions if position >= 0]
    return min(known_positions) if known_positions else -1


def _page_summary_position(text: str) -> int:
    positions = [
        _pattern_position(text, _EXPLICIT_PAGE_SUMMARY_RE),
        _pattern_position(text, _COLLOQUIAL_PAGE_SUMMARY_RE),
    ]
    summary_positions = [position for position in positions if position >= 0]
    return min(summary_positions) if summary_positions else -1


def _page_form_read_position(text: str) -> int:
    form_anchor = text.find("表单")
    if form_anchor < 0:
        form_anchor = text.find("form")
    if form_anchor < 0:
        return -1
    read_anchor = first_position(
        text,
        ("状态", "选项", "必填", "字段", "required", "field", "fields"),
    )
    if read_anchor < 0:
        return -1
    return min(form_anchor, read_anchor)


def _page_editor_read_position(text: str) -> int:
    editor_anchor = text.find("编辑器")
    if editor_anchor < 0:
        editor_anchor = text.find("editor")
    if editor_anchor < 0:
        return -1
    read_anchor = first_position(
        text,
        ("内容", "html", "文本", "content", "text"),
    )
    if read_anchor < 0:
        return -1
    return min(editor_anchor, read_anchor)


def _page_editor_write_position(text: str) -> int:
    editor_anchor = text.find("编辑器")
    if editor_anchor < 0:
        editor_anchor = text.find("editor")
    if editor_anchor < 0:
        return -1
    write_anchor = first_position(
        text,
        (
            "修改",
            "改写",
            "替换",
            "追加",
            "插入",
            "更新",
            "标题",
            "正文",
            "rewrite",
            "replace",
            "append",
            "insert",
            "update",
            "edit",
        ),
    )
    if write_anchor < 0:
        return -1
    return min(editor_anchor, write_anchor)


def _page_row_detail_position(text: str) -> int:
    detail_anchor = first_position(
        text,
        ("详情", "明细", "详细信息", "row detail", "record detail"),
    )
    if detail_anchor < 0:
        return -1
    if any(
        token in text
        for token in ("记录", "列表", "表格", "对话", "record", "row", "table")
    ):
        return detail_anchor
    return -1


def _page_pagination_position(text: str) -> int:
    positions = [
        first_position(text, _PAGE_PAGINATION_TERMS),
        _pattern_position(text, _PAGE_PAGINATION_NUMBERED_RE),
    ]
    pagination_positions = [position for position in positions if position >= 0]
    return min(pagination_positions) if pagination_positions else -1


def _page_workflow_snapshot(
    *,
    intent_kind: str | None = None,
    intent_metadata: dict[str, Any] | None = None,
) -> dict[str, str]:
    payload = dict(intent_metadata or {})
    normalized_kind = str(intent_kind or "").strip()
    workflow_kind = str(payload.get("page_workflow_kind") or "").strip()
    workflow_goal = str(payload.get("page_workflow_goal") or "").strip()
    workflow_alias = ""
    if workflow_kind == _PAGE_WORKFLOW_KIND or normalized_kind == _PAGE_WORKFLOW_KIND:
        workflow_kind = _PAGE_WORKFLOW_KIND
    if normalized_kind != _PAGE_WORKFLOW_KIND and normalized_kind.startswith("page_"):
        workflow_alias = workflow_alias or normalized_kind
        workflow_goal = workflow_goal or _PAGE_WORKFLOW_GOALS.get(normalized_kind, "")
        workflow_kind = workflow_kind or _PAGE_WORKFLOW_KIND
    if workflow_goal and not workflow_alias:
        workflow_alias = _page_workflow_alias_for_goal(workflow_goal=workflow_goal)
    if workflow_alias and not workflow_goal:
        workflow_goal = _PAGE_WORKFLOW_GOALS.get(workflow_alias, "")
    return {
        "workflow_kind": workflow_kind,
        "workflow_goal": workflow_goal,
        "workflow_alias": workflow_alias,
    }


def _page_workflow_alias_for_goal(
    *,
    workflow_goal: str,
    workflow_alias: str = "",
) -> str:
    normalized_alias = str(workflow_alias or "").strip()
    if normalized_alias.startswith("page_"):
        return normalized_alias
    normalized_goal = str(workflow_goal or "").strip()
    if normalized_goal == "table_summary":
        return "page_summary"
    return _PAGE_WORKFLOW_ALIASES_BY_GOAL.get(normalized_goal, "page_summary")


def _iter_active_page_intents(
    input_variables: dict[str, Any] | None,
) -> list[tuple[str, dict[str, Any]]]:
    runtime_intents = resolve_intent_plan_view(input_variables)
    page_intents: list[tuple[str, dict[str, Any]]] = []
    fallback_page_intents: list[tuple[str, dict[str, Any]]] = []
    for intent in runtime_intents:
        if str(getattr(intent, "family", "") or "").strip() != "page_ops":
            continue
        metadata = dict(getattr(intent, "metadata", {}) or {})
        item = (str(getattr(intent, "kind", "") or "").strip(), metadata)
        status = str(getattr(intent, "status", "") or "").strip()
        if status not in {"completed", "failed", "skipped"}:
            page_intents.append(item)
        fallback_page_intents.append(item)
    return page_intents or fallback_page_intents


def _active_page_workflow_snapshot(
    *,
    input_variables: dict[str, Any] | None,
    continuation_context: Any | None,
) -> dict[str, str]:
    active_intent_kind = str(
        getattr(continuation_context, "active_intent_kind", "") or ""
    ).strip()
    for kind, metadata in _iter_active_page_intents(input_variables):
        snapshot = _page_workflow_snapshot(
            intent_kind=kind,
            intent_metadata=metadata,
        )
        if not active_intent_kind:
            return snapshot
        if active_intent_kind in {kind, snapshot["workflow_alias"]}:
            return snapshot
    return _page_workflow_snapshot(intent_kind=active_intent_kind)


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
        token in lowered for token in _PAGE_CONTINUE_NAVIGATION_TERMS
    ):
        return "page_navigation"
    if first_position(lowered, _PAGE_CONTINUE_DETAIL_TERMS) >= 0 or any(
        token in lowered for token in ("区域", "明细", "详情")
    ):
        page_ops = page_operation_names(input_variables)
        if _PAGE_ROW_DETAIL_TOOL_NAMES & page_ops:
            return "page_row_detail"
    active_page_workflow = _active_page_workflow_snapshot(
        input_variables=input_variables,
        continuation_context=continuation_context,
    )
    active_workflow_goal = active_page_workflow["workflow_goal"]
    if active_workflow_goal not in {"", "form_write", "editor_write"}:
        return _page_workflow_alias_for_goal(
            workflow_goal=active_workflow_goal,
            workflow_alias=active_page_workflow["workflow_alias"],
        )
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
    last_tool_name = str(getattr(continuation_context, "last_tool_name", "") or "").strip()
    active_page_workflow = _active_page_workflow_snapshot(
        input_variables=input_variables,
        continuation_context=continuation_context,
    )
    prior_page_family = (
        active_family == "page_ops"
        or active_page_workflow["workflow_kind"] == _PAGE_WORKFLOW_KIND
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
    metadata = _page_workflow_metadata(
        intent_kind=intent_kind,
        metadata={
            "continuation_source": "page_ops",
            "routing_mode": "deterministic_shortcircuit",
            "routing_provenance": "page_continuation_guard",
        },
    )
    return PageIntentSignal(
        kind=intent_kind,
        family="page_ops",
        label=intent_kind,
        position=offset,
        shortcircuit=(metadata.get("page_workflow_goal") == "page_summary"),
        continuation=True,
        metadata=metadata,
    )


def looks_like_page_jump_request(lowered: str) -> bool:
    if any(token in lowered for token in _PAGE_PAGINATION_TERMS):
        return True
    return _pattern_position(lowered, _PAGE_PAGINATION_NUMBERED_RE) >= 0


def strip_negated_page_references(text: str) -> str:
    normalized = str(text or "").strip().lower()
    if not normalized:
        return ""
    stripped = normalized
    for pattern in _NEGATED_PAGE_REFERENCE_PATTERNS:
        stripped = pattern.sub(" ", stripped)
    return re.sub(r"\s+", " ", stripped).strip()


def looks_like_page_search_request(lowered: str) -> bool:
    normalized = strip_negated_page_references(lowered)
    explicit_page_search = first_position(normalized, _PAGE_SEARCH_TERMS) >= 0
    if explicit_page_search:
        return True
    if "搜索" not in normalized and "搜" not in normalized and "查找" not in normalized:
        return False
    search_position = first_position(normalized, ("搜索", "搜", "查找"))
    qualifier_position = first_position(
        normalized,
        _PAGE_POINTER_TERMS + _PAGE_SEARCH_QUALIFIER_TERMS,
    )
    if search_position < 0 or qualifier_position < 0:
        return False
    return abs(search_position - qualifier_position) <= 18


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


def _first_matching_term(text: str, candidates: tuple[str, ...]) -> tuple[int, str]:
    def _match_position(candidate: str) -> int:
        if candidate.isascii() and any(char.isalpha() for char in candidate):
            match = re.search(
                rf"(?<![a-z0-9_-]){re.escape(candidate)}(?![a-z0-9_-])",
                text,
                re.IGNORECASE,
            )
            return match.start() if match else -1
        return text.find(candidate)

    best_position = -1
    best_term = ""
    for item in candidates:
        if not item:
            continue
        position = _match_position(item)
        if position < 0:
            continue
        if best_position < 0 or position < best_position:
            best_position = position
            best_term = item
    return best_position, best_term


def _has_active_form_session(page_context: dict[str, Any] | None) -> bool:
    if not isinstance(page_context, dict):
        return False
    if str(page_context.get("active_form_session_id") or "").strip():
        return True
    return isinstance(page_context.get("active_form_summary"), dict)


def should_add_page_form_write_signal(
    *,
    clause: str,
    lowered: str,
    page_context: dict[str, Any] | None,
    explicit_page_reference: bool,
) -> bool:
    _position, matched_term = _first_matching_term(lowered, _PAGE_FORM_WRITE_TERMS)
    if not matched_term:
        return False
    if matched_term not in _GENERIC_PAGE_FORM_WRITE_TERMS:
        return True
    if _has_active_form_session(page_context):
        return True
    if explicit_page_reference:
        return True
    if has_navigation_intent(clause, page_context):
        return True
    if first_position(lowered, _PAGE_CONTINUE_NAVIGATION_TERMS) >= 0:
        return True
    return first_position(lowered, _PAGE_WRITE_ANCHOR_TERMS) >= 0


def _page_workflow_metadata(
    *,
    intent_kind: str,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = dict(metadata or {})
    payload.setdefault("routing_mode", "deterministic_shortcircuit")
    payload.setdefault("routing_provenance", "page_shortcircuit")
    payload.setdefault("page_workflow_kind", _PAGE_WORKFLOW_KIND)
    payload.setdefault(
        "page_workflow_goal",
        _PAGE_WORKFLOW_GOALS.get(intent_kind, ""),
    )
    return payload


def detect_page_signal(
    *,
    clause: str,
    offset: int,
    input_variables: dict[str, Any] | None,
) -> PageIntentSignal | None:
    lowered = clause.lower()
    normalized_page_clause = strip_negated_page_references(lowered)
    if not has_page_context(input_variables):
        return None
    page_context = _page_context_from_input_variables(input_variables)
    explicit_url_position = explicit_external_url_position(clause)
    explicit_page_reference = (
        _first_known_page_reference_position(normalized_page_clause) >= 0
    )
    if (
        explicit_url_position >= 0
        and not explicit_page_reference
        and not has_navigation_intent(clause, page_context)
    ):
        return None

    form_write_position, _matched_form_write_term = _first_matching_term(
        normalized_page_clause,
        _PAGE_FORM_WRITE_TERMS,
    )
    page_position_candidates = [
        _first_known_page_reference_position(normalized_page_clause),
        first_position(normalized_page_clause, _PAGE_NAV_TERMS),
        form_write_position,
    ]
    page_position = min(
        position for position in page_position_candidates if position >= 0
    ) if any(position >= 0 for position in page_position_candidates) else -1
    if page_position < 0 and not any(
        token in normalized_page_clause
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
            "翻到",
            "翻回",
            "第",
            "页",
            "详情",
        )
    ):
        return None

    candidates: list[tuple[int, int, PageIntentSignal]] = []

    def add_candidate(
        kind: str,
        label: str,
        position: int,
        priority: int,
        *,
        routing_mode: str,
        routing_provenance: str,
    ) -> None:
        if position < 0:
            return
        metadata = _page_workflow_metadata(
            intent_kind=kind,
            metadata={
                "routing_mode": routing_mode,
                "routing_provenance": routing_provenance,
            },
        )
        candidates.append(
            (
                position,
                priority,
                PageIntentSignal(
                    kind,
                    "page_ops",
                    label,
                    offset + position,
                    shortcircuit=(metadata.get("page_workflow_goal") == "page_summary"),
                    metadata=metadata,
                ),
            )
        )

    nav_position = first_position(normalized_page_clause, _PAGE_NAV_TERMS)
    navigation_from_catalog = has_navigation_intent(clause, page_context)
    if navigation_from_catalog or nav_position >= 0:
        add_candidate(
            "page_navigation",
            "page_navigation",
            nav_position if nav_position >= 0 else max(page_position, 0),
            0,
            routing_mode=(
                "structured_semantic"
                if navigation_from_catalog
                else "deterministic_shortcircuit"
            ),
            routing_provenance=(
                "navigation_catalog_semantics"
                if navigation_from_catalog
                else "page_navigation_shortcircuit"
            ),
        )

    # SHORTCIRCUIT: explicit screenshot requests map directly to the screenshot workflow.
    add_candidate(
        "page_screenshot",
        "page_screenshot",
        first_position(lowered, _PAGE_SCREENSHOT_TERMS),
        1,
        routing_mode="deterministic_shortcircuit",
        routing_provenance="page_screenshot_shortcircuit",
    )

    editor_anchor = normalized_page_clause.find("编辑器")
    editor_write_position = _page_editor_write_position(normalized_page_clause)
    if editor_anchor >= 0 and any(
        token in normalized_page_clause
        for token in ("修改", "改写", "优化", "润色", "追加", "插入", "标题", "正文")
    ):
        editor_write_position = (
            editor_anchor
            if editor_write_position < 0
            else min(editor_anchor, editor_write_position)
        )
    add_candidate(
        "page_editor_write",
        "page_editor_write",
        editor_write_position,
        2,
        routing_mode="deterministic_shortcircuit",
        routing_provenance="page_editor_write_shortcircuit",
    )

    editor_read_position = _page_editor_read_position(normalized_page_clause)
    if editor_anchor >= 0 and any(
        token in normalized_page_clause for token in ("什么", "内容", "html", "文本")
    ):
        editor_read_position = (
            editor_anchor
            if editor_read_position < 0
            else min(editor_anchor, editor_read_position)
        )
    add_candidate(
        "page_editor_read",
        "page_editor_read",
        editor_read_position,
        3,
        routing_mode="deterministic_shortcircuit",
        routing_provenance="page_editor_read_shortcircuit",
    )

    should_add_form_write = should_add_page_form_write_signal(
        clause=clause,
        lowered=normalized_page_clause,
        page_context=page_context,
        explicit_page_reference=explicit_page_reference,
    )
    if (
        should_add_form_write
        and not (editor_anchor >= 0 and editor_write_position >= 0)
        and not looks_like_read_only_form_instruction(normalized_page_clause)
    ):
        # SHORTCIRCUIT: explicit create/edit/delete intents on the active page stay deterministic.
        add_candidate(
            "page_form_write",
            "page_form_write",
            form_write_position,
            4,
            routing_mode="deterministic_shortcircuit",
            routing_provenance="page_form_write_shortcircuit",
        )

    form_read_position = _page_form_read_position(normalized_page_clause)
    if looks_like_required_field_form_read(normalized_page_clause):
        form_anchor = normalized_page_clause.find("表单")
        if form_anchor < 0:
            form_anchor = normalized_page_clause.find("form")
        required_anchor = normalized_page_clause.find("必填")
        if required_anchor < 0:
            required_anchor = normalized_page_clause.find("required")
        for anchor in (form_anchor, required_anchor):
            if anchor >= 0 and (form_read_position < 0 or anchor < form_read_position):
                form_read_position = anchor
    if looks_like_field_listing_form_read(normalized_page_clause, page_context):
        field_anchor = normalized_page_clause.find("字段")
        if field_anchor < 0:
            field_anchor = normalized_page_clause.find("field")
        form_anchor = normalized_page_clause.find("表单")
        if form_anchor < 0:
            form_anchor = normalized_page_clause.find("form")
        for anchor in (form_anchor, field_anchor):
            if anchor >= 0 and (form_read_position < 0 or anchor < form_read_position):
                form_read_position = anchor
    add_candidate(
        "page_form_read",
        "page_form_read",
        form_read_position,
        5,
        routing_mode="deterministic_shortcircuit",
        routing_provenance="page_form_read_shortcircuit",
    )

    search_position = first_position(normalized_page_clause, _PAGE_SEARCH_TERMS)
    if search_position < 0 and looks_like_page_search_request(normalized_page_clause):
        search_position = normalized_page_clause.find("搜索")
    # SHORTCIRCUIT: page-scoped search is intentionally bounded to explicit in-page search cues.
    add_candidate(
        "page_search",
        "page_search",
        search_position,
        6,
        routing_mode="deterministic_shortcircuit",
        routing_provenance="page_search_shortcircuit",
    )

    pagination_position = (
        _page_pagination_position(normalized_page_clause)
        if looks_like_page_jump_request(normalized_page_clause)
        else -1
    )
    add_candidate(
        "page_pagination",
        "page_pagination",
        pagination_position,
        7,
        routing_mode="deterministic_shortcircuit",
        routing_provenance="page_pagination_shortcircuit",
    )
    row_detail_position = _page_row_detail_position(normalized_page_clause)
    add_candidate(
        "page_row_detail",
        "page_row_detail",
        row_detail_position,
        8,
        routing_mode="deterministic_shortcircuit",
        routing_provenance="page_row_detail_shortcircuit",
    )

    summary_position = _page_summary_position(normalized_page_clause)
    suppressed_generic_form_write = form_write_position >= 0 and not should_add_form_write
    if not candidates and suppressed_generic_form_write and summary_position < 0:
        return None

    if not candidates:
        summary_provenance = (
            "page_summary_shortcircuit"
            if summary_position >= 0
            else "page_reference_fallback"
        )
        add_candidate(
            "page_summary",
            "page_summary",
            summary_position if summary_position >= 0 else page_position,
            9,
            routing_mode="deterministic_shortcircuit",
            routing_provenance=summary_provenance,
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
