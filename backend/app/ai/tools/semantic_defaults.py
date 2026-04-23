"""
Single source of truth for tool family resolution and default semantic hints.

Provides:
- ``tool_family_from_name`` – canonical name→family mapping (replaces former
  duplicated ``_tool_family_from_name`` in optimizer and ``_tool_family_for_name`` in base).
- ``tool_semantic_family`` / ``tool_semantic_tags`` – unified accessors that
  prefer the ``ToolDefinition`` attribute, falling back to name-based defaults.
- ``FAMILY_HINT_TAGS`` / ``FAMILY_EXPLICIT_REQUEST_HINTS`` – per-family hint
  phrases for scoring and capability-term expansion.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.ai.runtime.contracts import PAGE_CONTEXT_KEY

# Per-family short phrases used for tool optimization and capability-term expansion.
# 按族的短语文本，用于工具优化与能力词扩展。
FAMILY_HINT_TAGS: dict[str, tuple[str, ...]] = {
    "web_research": (
        "联网搜索",
        "网页查询",
        "读取网页",
        "官方来源",
        "最新信息",
        "web search",
    ),
    "weather": (
        "天气查询",
        "天气预报",
        "当前天气",
        "实时天气",
        "weather forecast",
    ),
    "time_ops": (
        "当前时间",
        "现在几点",
        "今天几号",
        "当前日期",
        "time now",
        "timezone",
        "current time",
        "current date",
    ),
    "page_ops": (
        "页面操作",
        "页面交互",
        "页面感知能力",
        "页面感知交互",
        "页面能力",
        "读取页面",
        "填写表单",
        "提交页面",
        "page operation",
    ),
}

# Tags omitted from explicit-request hints (optimizer): slightly shorter / less “broad” cues than full FAMILY_HINT_TAGS.
_EXPLICIT_HINT_EXCLUDE: dict[str, frozenset[str]] = {
    "web_research": frozenset({"最新信息"}),
    "time_ops": frozenset({"time now"}),
}

# Derived from FAMILY_HINT_TAGS — single maintenance point.
FAMILY_EXPLICIT_REQUEST_HINTS: dict[str, tuple[str, ...]] = {
    family: tuple(
        tag
        for tag in tags
        if tag not in _EXPLICIT_HINT_EXCLUDE.get(family, frozenset())
    )
    for family, tags in FAMILY_HINT_TAGS.items()
}

UI_PAGE_TOOL_ORDER: tuple[str, ...] = (
    "ui_get_snapshot",
    "ui_read_region",
    "ui_read_table",
    "ui_list_interactables",
    "ui_click",
    "ui_open_surface",
    "ui_get_form_state",
    "ui_set_field",
    "ui_fill_form",
    "ui_submit_form",
)
UI_PAGE_TOOL_NAMES: frozenset[str] = frozenset(UI_PAGE_TOOL_ORDER)
UI_READONLY_PAGE_TOOL_NAMES: frozenset[str] = frozenset(
    {
        "ui_get_snapshot",
        "ui_read_region",
        "ui_read_table",
        "ui_list_interactables",
        "ui_get_form_state",
    }
)
UI_SAFE_WRITE_PAGE_TOOL_NAMES: frozenset[str] = frozenset(
    {
        "ui_click",
        "ui_open_surface",
        "ui_set_field",
        "ui_fill_form",
    }
)
UI_DANGEROUS_PAGE_TOOL_NAMES: frozenset[str] = frozenset({"ui_submit_form"})


# ---------------------------------------------------------------------------
# Unified family resolver
# ---------------------------------------------------------------------------


def _has_page_context(input_variables: dict[str, Any] | None) -> bool:
    if not input_variables:
        return False
    page_ctx = page_context_payload(input_variables)
    if not isinstance(page_ctx, dict):
        return False
    return bool((page_ctx.get("page_key") or "").strip())


def is_ui_page_tool_name(name: str) -> bool:
    return str(name or "").strip() in UI_PAGE_TOOL_NAMES


def page_context_payload(input_variables: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(input_variables, dict):
        return None
    page_context = input_variables.get(PAGE_CONTEXT_KEY)
    return page_context if isinstance(page_context, dict) else None


def page_context_has_active_form(page_context: Mapping[str, Any] | None) -> bool:
    if not isinstance(page_context, Mapping):
        return False
    if str(page_context.get("active_form_session_id") or "").strip():
        return True
    return isinstance(page_context.get("active_form_summary"), Mapping)


def page_context_has_runtime_state(page_context: Mapping[str, Any] | None) -> bool:
    if not isinstance(page_context, Mapping):
        return False
    if str(page_context.get("page_session_id") or "").strip():
        return True
    if isinstance(page_context.get("ui_epoch"), int):
        return True
    if isinstance(page_context.get("surface_stack"), list) and page_context.get(
        "surface_stack"
    ):
        return True
    if str(page_context.get("active_surface_id") or "").strip():
        return True
    return page_context_has_active_form(page_context)


def page_context_available_ui_tools(
    page_context: Mapping[str, Any] | None,
    *,
    available_tool_names: set[str] | None = None,
    include_secondary: bool = True,
) -> list[str]:
    if not isinstance(page_context, Mapping):
        return []

    inferred: list[str] = []
    if page_context_has_runtime_state(page_context):
        inferred.extend(
            [
                "ui_get_snapshot",
                "ui_read_region",
                "ui_read_table",
                "ui_list_interactables",
                "ui_click",
            ]
        )
    if str(page_context.get("active_surface_id") or "").strip() or (
        isinstance(page_context.get("surface_stack"), list) and page_context.get("surface_stack")
    ):
        inferred.append("ui_open_surface")

    active_form_summary = page_context.get("active_form_summary")
    has_active_form = page_context_has_active_form(page_context)
    if has_active_form:
        inferred.extend(["ui_get_form_state", "ui_set_field", "ui_fill_form"])
        stage = (
            str(active_form_summary.get("stage") or "").strip()
            if isinstance(active_form_summary, Mapping)
            else ""
        )
        can_submit = (
            bool(active_form_summary.get("can_submit"))
            if isinstance(active_form_summary, Mapping)
            else False
        )
        if can_submit or stage in {"ready_to_submit", "submitting", "submitted"}:
            inferred.append("ui_submit_form")

    allowed = (
        {str(name).strip() for name in available_tool_names if str(name).strip()}
        if available_tool_names
        else None
    )
    resolved: list[str] = []
    for name in UI_PAGE_TOOL_ORDER:
        if name not in inferred:
            continue
        if name not in UI_PAGE_TOOL_NAMES or name in resolved:
            continue
        if allowed is not None and name not in allowed:
            continue
        resolved.append(name)
    return resolved


def tool_family_from_name(
    name: str,
    input_variables: dict[str, Any] | None = None,
) -> str:
    """Canonical tool-name → family mapping used by both optimizer and engine."""
    normalized = (name or "").strip()
    if not normalized:
        return "none"
    if normalized in {"web_search", "fetch_url"}:
        return "web_research"
    if normalized == "get_current_time":
        return "time_ops"
    if normalized in {"get_current_weather", "get_weather_forecast"}:
        return "weather"
    if is_ui_page_tool_name(normalized) or (
        normalized.startswith("ui_") and _has_page_context(input_variables)
    ):
        return "page_ops"
    return "none"


def tool_semantic_family(
    tool: Any,
    input_variables: dict[str, Any] | None = None,
) -> str:
    """Return the semantic family, preferring the ToolDefinition attribute."""
    family = str(getattr(tool, "semantic_family", "") or "").strip()
    if family:
        return family
    return tool_family_from_name(getattr(tool, "name", ""), input_variables)


def tool_semantic_tags(tool: Any) -> list[str]:
    """Return semantic tags, falling back to FAMILY_HINT_TAGS defaults."""
    tags = [
        str(tag).strip()
        for tag in (getattr(tool, "semantic_tags", None) or [])
        if str(tag).strip()
    ]
    if tags:
        return tags
    family = tool_semantic_family(tool)
    return list(FAMILY_HINT_TAGS.get(family, ()))
