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

from typing import Any

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

# ---------------------------------------------------------------------------
# Unified family resolver
# ---------------------------------------------------------------------------


def normalize_semantic_family(value: Any) -> str:
    return (
        str(value or "")
        .strip()
        .lower()
        .replace("-", "_")
        .replace(" ", "_")
        .replace(".", "_")
        .replace(":", "_")
    )


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
