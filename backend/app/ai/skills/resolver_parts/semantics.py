from __future__ import annotations

from typing import Any

from app.ai.tools.semantic_defaults import FAMILY_HINT_TAGS
from app.ai.tools.types import ToolDefinition


def semantic_tags(*values: str) -> list[str]:
    tags: list[str] = []
    for value in values:
        text = (value or "").strip()
        if text and text not in tags:
            tags.append(text)
    return tags


def apply_tool_semantics(tool: ToolDefinition) -> None:
    if tool.semantic_family:
        return

    name = (tool.name or "").strip()
    if not name:
        return

    if name in {"web_search", "fetch_url"}:
        tool.semantic_family = "web_research"
        tool.semantic_tags = tool.semantic_tags or semantic_tags(
            *FAMILY_HINT_TAGS["web_research"],
            "website",
            "url",
            "search web",
        )
        return

    if name == "get_current_time":
        tool.semantic_family = "time_ops"
        tool.semantic_tags = tool.semantic_tags or semantic_tags(
            *FAMILY_HINT_TAGS["time_ops"],
            "time",
            "clock",
        )
        return

    if name in {"get_current_weather", "get_weather_forecast"}:
        tool.semantic_family = "weather"
        tool.semantic_tags = tool.semantic_tags or semantic_tags(
            *FAMILY_HINT_TAGS["weather"],
            "weather",
            "forecast",
        )
        return

    # Page-awareness/page-operation tools are retired from AI dialogue. Keep
    # legacy tool names unclassified so they cannot re-enter live activation via
    # semantic hints.


def is_runtime_eligible_skill(skill: Any) -> bool:
    if not skill:
        return False
    if getattr(skill, "is_active", True) is False:
        return False
    if getattr(skill, "is_deleted", False) is True:
        return False
    package = getattr(skill, "package", None)
    if package is None:
        return False
    return bool(
        getattr(package, "is_active", True) is not False
        and getattr(package, "is_deleted", False) is not True
    )
