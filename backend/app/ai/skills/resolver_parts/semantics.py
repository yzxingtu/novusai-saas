from __future__ import annotations

from typing import Any

from app.ai.tools.semantic_defaults import FAMILY_HINT_TAGS
from app.ai.tools.types import ToolDefinition
from app.enums.skill import SkillStatusEnum


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

    if name == "get_current_time":
        tool.semantic_family = "time_ops"
        tool.semantic_tags = tool.semantic_tags or semantic_tags(
            *FAMILY_HINT_TAGS["time_ops"],
            "time",
            "clock",
        )
        return


def _status_value(value: Any) -> str:
    status = getattr(value, "value", value)
    return str(status or "").strip()


def _has_runtime_active_status(value: Any) -> bool:
    if not hasattr(value, "status"):
        return True
    return _status_value(value.status) == SkillStatusEnum.ACTIVE.value


def is_runtime_eligible_skill(skill: Any) -> bool:
    if not skill:
        return False
    if getattr(skill, "is_active", True) is False:
        return False
    if not _has_runtime_active_status(skill):
        return False
    if getattr(skill, "is_deleted", False) is True:
        return False
    package = getattr(skill, "package", None)
    if package is None:
        return True
    return bool(
        getattr(package, "is_active", True) is not False
        and _has_runtime_active_status(package)
        and getattr(package, "is_deleted", False) is not True
    )
