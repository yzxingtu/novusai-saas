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
    _semantic_profile_position,
)
from app.ai.navigation_semantics import has_navigation_intent
from app.ai.tools.semantic_defaults import tool_semantic_family
from app.ai.tools.types import ToolDefinition

from .page_workflow_state_machine import resolve_page_workflow_goal

PageIntentSignal = _IntentSignal
continuation_families = _continuation_families
first_position = _first_position
has_page_context = _has_page_context
page_operation_names = _page_operation_names

_PAGE_WORKFLOW_KIND = "page_workflow"

_EXPLICIT_EXTERNAL_URL_RE = re.compile(r"https?://[^\s<>()\[\]\"']+", re.IGNORECASE)
_CODE_MIXED_PAGE_REFERENCE_RE = re.compile(
    r"(?:这个|当前|本)\s*page(?:\s*(?:上|里|内容))?"
    r"|(?:this|current)\s*page(?:\s*(?:content|contents|on))?",
    re.IGNORECASE,
)
# SHORTCIRCUIT: keep a narrow current-page deictic guard for prompts such as
# "这里都有啥？" / "what's here?" when page_context is attached. This is an
# explicit page-reference fallback, not a general phrase bucket.
_DEICTIC_PAGE_REFERENCE_RE = re.compile(
    r"^(?:这里|这儿|here)(?:都)?(?:上|里)?(?:有什么|有啥|是什么|叫啥|叫什么)?[？?!.。]*$"
    r"|^(?:what(?:'s| is)\s+here|what\s+is\s+on\s+(?:this\s+)?page)[?.!]*$",
    re.IGNORECASE,
)
_READ_ONLY_PAGE_WRITE_HINT_RE = re.compile(
    r"(?:不要|别|不用|不必|无需|先不要|暂时不要|不要帮我|先别)"
    r"|(?:do not|don't|without|not yet)",
    re.IGNORECASE,
)
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
    "当前页",
    "页面内容",
    "页面里",
    "页面上",
    "this page",
    "current page",
    "page content",
    "page contents",
    "on this page",
    "这个列表",
    "当前列表",
    "this list",
    "current list",
    "这个表格",
    "当前表格",
    "this table",
    "current table",
    "这个表单",
    "当前表单",
    "this form",
    "current form",
    "这条记录",
    "当前记录",
    "this record",
    "current record",
)
# SHORTCIRCUIT: keep only a bounded generic follow-up vocabulary for active
# page workflows until planner-time LLM structured routing fully owns page
# intent selection.
_PAGE_CONTINUATION_SCREENSHOT_RE = re.compile(
    r"(?:截图|截屏|截.{0,1}图|screenshot)",
    re.IGNORECASE,
)
_PAGE_CONTINUATION_ACTION_RE = re.compile(
    r"(?:继续|再|接着|继续看|再看|接着看|continue|again|keep going"
    r"|截图|截屏|截.{0,1}图|screenshot"
    r"|详情|明细|detail|区域|展开|里面"
    r"|点击|单击|click|open|打开|进入)",
    re.IGNORECASE,
)
_PAGE_CONTINUATION_NAVIGATION_RE = re.compile(
    r"(?:点击|单击|click|open|打开|进入)",
    re.IGNORECASE,
)
_PAGE_CONTINUATION_DETAIL_RE = re.compile(
    r"(?:详情|明细|detail|区域|展开|里面)",
    re.IGNORECASE,
)
_SHORT_PAGE_FOLLOW_UP_RE = re.compile(
    r"(?:看|截图|截屏|screenshot|展开|详情|明细|区域|点击|click|open)",
    re.IGNORECASE,
)
_PAGE_ROW_DETAIL_TOOL_NAMES = frozenset(
    {
        "ui_click",
        "ui_open_surface",
        "ui_read_region",
        "ui_read_table",
    }
)
_PAGE_SCREENSHOT_RE = re.compile(r"(?:截图|截屏|截.{0,1}图|screenshot)", re.IGNORECASE)
_IMPLICIT_PAGE_PAGINATION_RE = re.compile(
    r"(?:上一页|下一页|前一页|后一页|翻页|翻到第?\s*\d+\s*页|翻回上一页|每页(?:显示|展示)?\s*\d+\s*条"
    r"|page\s*\d+|next page|previous page|prev page|per page|page size)",
    re.IGNORECASE,
)
_PAGE_GOAL_SEMANTIC_PROFILES = {
    "search": (
        "搜索 查找 筛选 过滤 清除筛选 清空筛选 清除搜索 重置筛选 记录 列表 表格 数据 结果 search filter"
    ),
    "row_detail_detail": ("详情 明细 详细 detail details"),
    "row_detail_context": ("第一条 第1条 首条 记录 行 row record show view read"),
    "form_read": ("表单 字段 状态 选项 form field fields state options"),
    "write_action": (
        "创建 新增 添加 编辑 修改 更新 删除 提交 填写 create add edit update delete submit fill"
    ),
    "write_target": (
        "记录 表单 字段 名称 标题 正文 内容 一条 一项 一个 record form field name title content"
    ),
}
_IMPLICIT_PAGE_GOAL_ORDER = (
    "pagination",
    "form_read",
    "row_detail",
    "search",
    "form_write",
)
_EDITOR_CONTEXT_TERMS = ("editor", "编辑器")


def _page_context_from_input_variables(
    input_variables: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if not isinstance(input_variables, dict):
        return None
    page_context = input_variables.get("page_context")
    return page_context if isinstance(page_context, dict) else None


def _page_context_has_active_form(page_context: dict[str, Any] | None) -> bool:
    if not isinstance(page_context, dict):
        return False
    if str(page_context.get("active_form_session_id") or "").strip():
        return True
    active_form_summary = page_context.get("active_form_summary")
    if not isinstance(active_form_summary, dict):
        return False
    return bool(
        str(active_form_summary.get("form_session_id") or "").strip()
        or str(active_form_summary.get("stage") or "").strip()
        or active_form_summary.get("can_submit") is not None
    )


def _page_workflow_shortcircuit_goal(workflow_goal: str) -> bool:
    return str(workflow_goal or "").strip() in {
        "page_summary",
        "table_summary",
        "page_screenshot",
        "search",
    }


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
    if _PAGE_CONTINUATION_ACTION_RE.search(lowered) or _has_screenshot_follow_up(
        lowered
    ):
        return True
    return bool(
        looks_like_short_directive_follow_up(lowered)
        and _SHORT_PAGE_FOLLOW_UP_RE.search(lowered)
    )


def _has_screenshot_follow_up(text: str) -> bool:
    return _PAGE_CONTINUATION_SCREENSHOT_RE.search(text) is not None


def _page_reference_position(text: str) -> int:
    positions = [first_position(text, _PAGE_POINTER_TERMS)]
    code_mixed_match = _CODE_MIXED_PAGE_REFERENCE_RE.search(text)
    if code_mixed_match:
        positions.append(code_mixed_match.start())
    deictic_match = _DEICTIC_PAGE_REFERENCE_RE.search(text)
    if deictic_match:
        positions.append(deictic_match.start())
    known_positions = [position for position in positions if position >= 0]
    return min(known_positions) if known_positions else -1


def _looks_like_explicit_page_write_request(text: str) -> bool:
    return _looks_like_page_write_request(
        text,
        target_min_score=1,
    )


def _semantic_profile_goal_position(
    text: str,
    profiles: tuple[str, ...],
    *,
    min_score: int = 2,
) -> int:
    return _semantic_profile_position(
        text,
        profiles,
        min_score=min_score,
    )


def _goal_profile_position(
    text: str,
    profile_key: str,
    *,
    min_score: int = 2,
) -> int:
    profile = str(_PAGE_GOAL_SEMANTIC_PROFILES.get(profile_key) or "").strip()
    if not profile:
        return -1
    return _semantic_profile_goal_position(
        text,
        (profile,),
        min_score=min_score,
    )


def _looks_like_implicit_page_pagination_request(text: str) -> bool:
    return _IMPLICIT_PAGE_PAGINATION_RE.search(text) is not None


def _looks_like_implicit_page_search_request(text: str) -> bool:
    return _goal_profile_position(
        text,
        "search",
        min_score=2,
    ) >= 0


def _looks_like_implicit_page_row_detail_request(text: str) -> bool:
    return bool(
        _goal_profile_position(
            text,
            "row_detail_detail",
            min_score=1,
        )
        >= 0
        and _goal_profile_position(
            text,
            "row_detail_context",
            min_score=1,
        )
        >= 0
    )


def _looks_like_implicit_page_form_read_request(
    text: str,
    *,
    page_context: dict[str, Any] | None,
) -> bool:
    min_score = 1 if _page_context_has_active_form(page_context) else 2
    return _goal_profile_position(
        text,
        "form_read",
        min_score=min_score,
    ) >= 0


def _looks_like_implicit_page_form_write_request(text: str) -> bool:
    if _PAGE_CONTINUATION_NAVIGATION_RE.search(text):
        return False
    target_min_score = 2
    if any(term in text for term in _EDITOR_CONTEXT_TERMS):
        target_min_score = 1
    return _looks_like_page_write_request(
        text,
        target_min_score=target_min_score,
    )


def _looks_like_page_write_request(
    text: str,
    *,
    target_min_score: int,
) -> bool:
    normalized = str(text or "").strip().lower()
    if not normalized:
        return False
    if _READ_ONLY_PAGE_WRITE_HINT_RE.search(normalized):
        return False
    if _goal_profile_position(normalized, "write_action", min_score=1) < 0:
        return False
    return _goal_profile_position(
        normalized,
        "write_target",
        min_score=target_min_score,
    ) >= 0


def _implicit_current_page_workflow_goal(
    text: str,
    *,
    page_context: dict[str, Any] | None,
) -> str:
    normalized = str(text or "").strip().lower()
    if not normalized:
        return ""
    # SHORTCIRCUIT: keep only a bounded set of strong current-page actions on
    # the page_workflow owner even when the user omits an explicit page pointer.
    goal_predicates = {
        "pagination": lambda: _looks_like_implicit_page_pagination_request(normalized),
        "form_read": lambda: _looks_like_implicit_page_form_read_request(
            normalized,
            page_context=page_context,
        ),
        "row_detail": lambda: _looks_like_implicit_page_row_detail_request(normalized),
        "search": lambda: _looks_like_implicit_page_search_request(normalized),
        "form_write": lambda: _looks_like_implicit_page_form_write_request(normalized),
    }
    for workflow_goal in _IMPLICIT_PAGE_GOAL_ORDER:
        if goal_predicates[workflow_goal]():
            return workflow_goal
    return ""


def _page_workflow_snapshot(
    *,
    intent_kind: str | None = None,
    intent_metadata: dict[str, Any] | None = None,
) -> dict[str, str]:
    payload = dict(intent_metadata or {})
    normalized_kind = str(intent_kind or "").strip()
    workflow_kind = str(payload.get("page_workflow_kind") or "").strip()
    workflow_goal = str(payload.get("page_workflow_goal") or "").strip()
    if workflow_kind == _PAGE_WORKFLOW_KIND or normalized_kind == _PAGE_WORKFLOW_KIND:
        workflow_kind = _PAGE_WORKFLOW_KIND
    return {
        "workflow_kind": workflow_kind,
        "workflow_goal": workflow_goal,
    }


def _canonical_page_workflow_goal(workflow_goal: str, default: str = "page_summary") -> str:
    normalized_goal = str(workflow_goal or "").strip()
    return normalized_goal or default


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
        if active_intent_kind == kind:
            return snapshot
    return _page_workflow_snapshot(intent_kind=active_intent_kind)


def page_continuation_workflow_goal(
    *,
    clause: str,
    input_variables: dict[str, Any] | None,
    continuation_context: Any | None,
) -> str:
    lowered = clause.lower()
    page_context = _page_context_from_input_variables(input_variables)
    # SHORTCIRCUIT: keep a bounded continuation action guard while the planner
    # migrates to LLM-first page workflow routing.
    if _has_screenshot_follow_up(lowered):
        return "page_screenshot"
    if has_navigation_intent(clause, page_context) or _PAGE_CONTINUATION_NAVIGATION_RE.search(
        lowered
    ):
        return "navigation"
    if _PAGE_CONTINUATION_DETAIL_RE.search(lowered):
        page_ops = page_operation_names(input_variables)
        if _PAGE_ROW_DETAIL_TOOL_NAMES & page_ops:
            return "row_detail"
    active_page_workflow = _active_page_workflow_snapshot(
        input_variables=input_variables,
        continuation_context=continuation_context,
    )
    active_workflow_goal = active_page_workflow["workflow_goal"]
    if active_workflow_goal:
        return _canonical_page_workflow_goal(active_workflow_goal)
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
    if not bool(getattr(continuation_context, "active", False)):
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

    workflow_goal = page_continuation_workflow_goal(
        clause=clause,
        input_variables=input_variables,
        continuation_context=continuation_context,
    )
    return _page_signal(
        workflow_goal=workflow_goal,
        position=offset,
        routing_mode="deterministic_shortcircuit",
        routing_provenance="page_continuation_guard",
        continuation=True,
        metadata={
            "continuation_source": "page_ops",
        },
    )


def strip_negated_page_references(text: str) -> str:
    normalized = str(text or "").strip().lower()
    if not normalized:
        return ""
    stripped = normalized
    for pattern in _NEGATED_PAGE_REFERENCE_PATTERNS:
        stripped = pattern.sub(" ", stripped)
    return re.sub(r"\s+", " ", stripped).strip()


def explicit_external_url_position(clause: str) -> int:
    match = _EXPLICIT_EXTERNAL_URL_RE.search(str(clause or "").strip())
    return match.start() if match else -1


def _page_workflow_metadata(
    *,
    workflow_goal: str,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = dict(metadata or {})
    payload.setdefault("routing_mode", "deterministic_shortcircuit")
    payload.setdefault("routing_provenance", "page_shortcircuit")
    payload.setdefault("page_workflow_kind", _PAGE_WORKFLOW_KIND)
    payload.setdefault(
        "page_workflow_goal",
        _canonical_page_workflow_goal(workflow_goal),
    )
    return payload


def _page_signal(
    *,
    workflow_goal: str,
    position: int,
    routing_provenance: str,
    routing_mode: str = "structured_semantic",
    shortcircuit: bool | None = None,
    continuation: bool = False,
    metadata: dict[str, Any] | None = None,
) -> PageIntentSignal:
    payload = _page_workflow_metadata(
        workflow_goal=workflow_goal,
        metadata={
            "routing_mode": routing_mode,
            "routing_provenance": routing_provenance,
            **dict(metadata or {}),
        },
    )
    return PageIntentSignal(
        kind=_PAGE_WORKFLOW_KIND,
        family="page_ops",
        label=_PAGE_WORKFLOW_KIND,
        position=position,
        shortcircuit=(
            _page_workflow_shortcircuit_goal(
                str(payload.get("page_workflow_goal") or "")
            )
            if shortcircuit is None
            else shortcircuit
        ),
        continuation=continuation,
        metadata=payload,
    )


def _page_reference_summary_workflow_goal(text: str) -> str:
    inferred_goal = resolve_page_workflow_goal(
        intent_kind=_PAGE_WORKFLOW_KIND,
        intent_metadata=None,
        user_text=text,
    )
    return "table_summary" if inferred_goal == "table_summary" else "page_summary"


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
    explicit_page_reference_position = _page_reference_position(normalized_page_clause)
    navigation_from_catalog = has_navigation_intent(clause, page_context)
    if (
        explicit_url_position >= 0
        and explicit_page_reference_position < 0
        and not navigation_from_catalog
    ):
        return None

    if navigation_from_catalog:
        return _page_signal(
            workflow_goal="navigation",
            position=offset,
            routing_provenance="navigation_catalog_semantics",
            shortcircuit=False,
        )

    if explicit_page_reference_position >= 0 and _PAGE_SCREENSHOT_RE.search(
        normalized_page_clause
    ):
        return _page_signal(
            workflow_goal="page_screenshot",
            position=offset + max(explicit_page_reference_position, 0),
            routing_provenance="page_workflow_semantic_profile",
            shortcircuit=True,
        )

    if _looks_like_implicit_page_row_detail_request(normalized_page_clause):
        return _page_signal(
            workflow_goal="row_detail",
            position=offset + max(explicit_page_reference_position, 0),
            routing_provenance="page_workflow_semantic_profile",
            shortcircuit=False,
        )

    if explicit_page_reference_position < 0:
        implicit_workflow_goal = _implicit_current_page_workflow_goal(
            normalized_page_clause,
            page_context=page_context,
        )
        if not implicit_workflow_goal:
            return None
        return _page_signal(
            workflow_goal=implicit_workflow_goal,
            position=offset,
            routing_provenance="active_page_action_semantics",
            shortcircuit=implicit_workflow_goal in {"page_summary", "table_summary"},
        )

    if _looks_like_explicit_page_write_request(normalized_page_clause):
        return _page_signal(
            workflow_goal="form_write",
            position=offset + max(explicit_page_reference_position, 0),
            routing_provenance="page_reference_write_semantics",
            shortcircuit=False,
        )

    summary_workflow_goal = _page_reference_summary_workflow_goal(
        normalized_page_clause,
    )
    if summary_workflow_goal == "table_summary":
        return _page_signal(
            workflow_goal=summary_workflow_goal,
            position=offset + max(explicit_page_reference_position, 0),
            routing_provenance="page_workflow_semantic_profile",
            shortcircuit=True,
        )

    return _page_signal(
        workflow_goal="page_summary",
        position=offset + explicit_page_reference_position,
        routing_mode="deterministic_shortcircuit",
        routing_provenance="page_reference_fallback",
        shortcircuit=True,
    )


__all__ = [
    "PageIntentSignal",
    "continuation_families",
    "detect_page_continuation_signal",
    "detect_page_signal",
    "first_position",
    "has_page_context",
    "looks_like_page_follow_up",
    "page_operation_names",
]
