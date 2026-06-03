"""Agent router capability helpers (skills, tool families, vision support)."""

from __future__ import annotations

from typing import Any

from app.ai.routing.router import ModelRouter
from app.ai.tools.semantic_defaults import tool_family_from_name
from app.models.ai.agent import Agent
from app.models.ai.agent_skill_grant import AgentSkillGrant
from app.repositories.ai.retired_skill_catalog_filters import is_retired_skill_instance
from app.schemas.ai.invalid_ai_runtime_input import (
    filter_invalid_ai_runtime_references,
    filter_invalid_ai_runtime_tools,
)

BASELINE_RUNTIME_FAMILIES = frozenset({"time_ops"})


def grant_skill_name_if_active(grant: AgentSkillGrant | Any) -> str | None:
    if getattr(grant, "enabled", True) is False:
        return None
    skill = getattr(grant, "skill", None)
    if not skill:
        return None
    if is_retired_skill_instance(skill):
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
        if not filter_invalid_ai_runtime_references([skill_name]):
            return None
        return skill_name
    return None


def _stable_unique(values: list[Any]) -> list[str]:
    normalized: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if text and text not in normalized:
            normalized.append(text)
    return normalized


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
    return any(grant_skill_name_if_active(grant) for grant in skill_grants)


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


def agent_supports_families(agent: Agent | None, families: list[str]) -> bool:
    if agent is None or not families:
        return False
    normalized_families = [str(family or "").strip() for family in families]
    if not normalized_families or any(not family for family in normalized_families):
        return False

    supported: set[str] = set()
    supported.update(BASELINE_RUNTIME_FAMILIES)
    skill_grants = getattr(agent, "skill_grants", None) or []
    for grant in skill_grants:
        skill_name = grant_skill_name_if_active(grant)
        if not skill_name:
            continue
        family = tool_family_from_name(skill_name)
        if family and family != "none":
            supported.add(family)
    return all(family in supported for family in normalized_families)


def _families_from_tool_names(values: list[Any]) -> set[str]:
    families: set[str] = set()
    for value in filter_invalid_ai_runtime_references(values):
        family = tool_family_from_name(value)
        if family and family != "none":
            families.add(family)
    return families


def _live_tool_names_from_result(result: Any) -> list[str]:
    return _stable_unique(
        filter_invalid_ai_runtime_references(
            [
                getattr(tool, "name", None)
                for tool in filter_invalid_ai_runtime_tools(
                    getattr(result, "tools", []) or []
                )
            ]
        )
    )


def _descriptor_live_tool_names(
    descriptor: Any, live_tool_names: list[str]
) -> list[str]:
    metadata = dict(getattr(descriptor, "metadata", {}) or {})
    if metadata.get("has_execution_tools") is not True:
        return []
    live_tool_name_set = set(live_tool_names)
    if not live_tool_name_set:
        return []
    resolved_tool_names = filter_invalid_ai_runtime_references(
        list(metadata.get("resolved_tool_names") or [])
    )
    return [name for name in resolved_tool_names if name in live_tool_name_set]


def _descriptor_has_execution_tools(
    descriptor: Any,
    live_tool_names: list[str],
) -> bool:
    return bool(_descriptor_live_tool_names(descriptor, live_tool_names))


async def executable_skill_names_for_router(
    db: Any,
    agent: Agent | None,
    *,
    tenant_id: int | None,
) -> list[str]:
    """Return skill names only when the resolver produced executable tools."""

    if agent is None:
        return []
    from app.ai.skills.resolver import resolve_for_agent

    try:
        result = await resolve_for_agent(
            db=db,
            agent=agent,
            tenant_id=tenant_id,
            request=None,
        )
    except Exception:
        return []
    live_tool_names = _live_tool_names_from_result(result)
    names: list[Any] = []
    for descriptor in list(getattr(result, "capability_descriptors", []) or []):
        if not _descriptor_has_execution_tools(descriptor, live_tool_names):
            continue
        names.append(getattr(descriptor, "name", None))
    return _stable_unique(filter_invalid_ai_runtime_references(names))


async def agent_supports_executable_families(
    db: Any,
    agent: Agent | None,
    families: list[str],
    *,
    tenant_id: int | None,
) -> bool:
    if agent is None or not families:
        return False
    normalized_families = [str(family or "").strip() for family in families]
    if not normalized_families or any(not family for family in normalized_families):
        return False

    supported: set[str] = set(BASELINE_RUNTIME_FAMILIES)
    if all(family in supported for family in normalized_families):
        return True

    from app.ai.skills.resolver import resolve_for_agent

    try:
        result = await resolve_for_agent(
            db=db,
            agent=agent,
            tenant_id=tenant_id,
            request=None,
        )
    except Exception:
        return all(family in supported for family in normalized_families)

    live_tools = filter_invalid_ai_runtime_tools(getattr(result, "tools", []) or [])
    live_tool_names = _stable_unique(
        filter_invalid_ai_runtime_references(
            [getattr(tool, "name", None) for tool in live_tools]
        )
    )
    for tool in live_tools:
        supported.update(_families_from_tool_names([getattr(tool, "name", None)]))
        semantic_family = str(getattr(tool, "semantic_family", "") or "").strip()
        if semantic_family and semantic_family != "none":
            supported.add(semantic_family)

    for descriptor in list(getattr(result, "capability_descriptors", []) or []):
        descriptor_tool_names = _descriptor_live_tool_names(descriptor, live_tool_names)
        if not descriptor_tool_names:
            continue
        supported.update(_families_from_tool_names([getattr(descriptor, "name", None)]))
        supported.update(_families_from_tool_names(descriptor_tool_names))
    return all(family in supported for family in normalized_families)


__all__ = [
    "BASELINE_RUNTIME_FAMILIES",
    "agent_can_handle_images",
    "agent_needs_function_calling",
    "agent_skill_names",
    "agent_supports_executable_families",
    "agent_supports_families",
    "agent_supports_images",
    "executable_skill_names_for_router",
    "grant_skill_name_if_active",
]
