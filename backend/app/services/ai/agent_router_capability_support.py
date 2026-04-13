"""
Agent router capability helpers (skills, tool families, vision support).
"""

from __future__ import annotations

from typing import Any

from app.ai.routing.router import ModelRouter
from app.ai.tools.semantic_defaults import is_ui_page_tool_name, tool_family_from_name
from app.models.ai.agent import Agent
from app.models.ai.agent_skill_grant import AgentSkillGrant

PAGE_OPERATION_REQUIRED_SKILL_GROUPS = (
    frozenset({"ui_get_snapshot", "ui_click"}),
)
BASELINE_RUNTIME_FAMILIES = frozenset({"time_ops"})

WEATHER_DESCRIPTOR_TOKENS = (
    "天气",
    "weather",
    "forecast",
    "气温",
    "温度",
)
TIME_DESCRIPTOR_TOKENS = (
    "时间",
    "日期",
    "time tool",
    "current time",
    "clock",
)
WEB_DESCRIPTOR_TOKENS = (
    "联网",
    "搜索",
    "web",
    "网页",
    "fetch url",
    "url",
)


def grant_skill_name_if_active(grant: AgentSkillGrant | Any) -> str | None:
    if getattr(grant, "enabled", True) is False:
        return None
    skill = getattr(grant, "skill", None)
    if not skill:
        return None
    if not getattr(skill, "is_active", True) or getattr(skill, "is_deleted", False):
        return None
    package = getattr(skill, "package", None)
    if package is None:
        return None
    if not getattr(package, "is_active", True) or getattr(package, "is_deleted", False):
        return None
    skill_name = getattr(skill, "name", None)
    if isinstance(skill_name, str) and skill_name:
        return skill_name
    return None


def agent_skill_names(agent: Agent | None) -> set[str]:
    if agent is None:
        return set()

    skill_names: set[str] = set()
    skill_grants = getattr(agent, "skill_grants", None) or []
    for grant in skill_grants:
        skill_name = grant_skill_name_if_active(grant)
        if skill_name:
            skill_names.add(skill_name)
    return skill_names


def agent_supports_images(agent: Agent | None) -> bool:
    model = getattr(agent, "model", None)
    return bool(getattr(model, "supports_vision", False))


def agent_needs_function_calling(agent: Agent | None) -> bool:
    skill_grants = getattr(agent, "skill_grants", None) or []
    for grant in skill_grants:
        if grant_skill_name_if_active(grant):
            return True
    return False


async def agent_can_handle_images(db: Any, agent: Agent | None) -> bool:
    if agent is None:
        return False
    if agent_supports_images(agent):
        return True
    needs_fc = agent_needs_function_calling(agent)
    return await ModelRouter(db).can_handle_attachments(
        agent,
        has_image=True,
        needs_fc=needs_fc,
    )


def agent_supports_page_operations(agent: Agent | None) -> bool:
    skill_names = agent_skill_names(agent)
    if any(group.issubset(skill_names) for group in PAGE_OPERATION_REQUIRED_SKILL_GROUPS):
        return True
    return any(is_ui_page_tool_name(skill_name) for skill_name in skill_names)


def agent_supports_families(agent: Agent | None, families: list[str]) -> bool:
    if agent is None or not families:
        return False

    supported: set[str] = set()
    supported.update(BASELINE_RUNTIME_FAMILIES)
    skill_grants = getattr(agent, "skill_grants", None) or []
    for grant in skill_grants:
        skill_name = grant_skill_name_if_active(grant)
        if not skill_name:
            continue

        descriptors = {
            str(skill_name).strip().lower(),
        }
        skill = getattr(grant, "skill", None)
        if skill is not None:
            descriptors.add(str(getattr(skill, "key", "") or "").strip().lower())
            descriptors.add(
                str(getattr(skill, "description", "") or "").strip().lower()
            )
            package = getattr(skill, "package", None)
            if package is not None:
                descriptors.add(
                    str(getattr(package, "name", "") or "").strip().lower()
                )
                descriptors.add(
                    str(getattr(package, "description", "") or "").strip().lower()
                )

        family = tool_family_from_name(skill_name)
        if family and family != "none":
            supported.add(family)
        if any(
            token in descriptor
            for descriptor in descriptors
            for token in WEATHER_DESCRIPTOR_TOKENS
        ):
            supported.add("weather")
        if any(
            token in descriptor
            for descriptor in descriptors
            for token in TIME_DESCRIPTOR_TOKENS
        ):
            supported.add("time_ops")
        if any(
            token in descriptor
            for descriptor in descriptors
            for token in WEB_DESCRIPTOR_TOKENS
        ):
            supported.add("web_research")
    return all(family in supported for family in families)


__all__ = [
    "BASELINE_RUNTIME_FAMILIES",
    "PAGE_OPERATION_REQUIRED_SKILL_GROUPS",
    "agent_can_handle_images",
    "agent_needs_function_calling",
    "agent_skill_names",
    "agent_supports_families",
    "agent_supports_images",
    "agent_supports_page_operations",
    "grant_skill_name_if_active",
]
