"""Agent router capability helpers (skills, tool families, vision support)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.ai.routing.router import ModelRouter
from app.ai.tools.semantic_defaults import tool_family_from_name
from app.models.ai.agent import Agent
from app.models.ai.agent_skill_grant import AgentSkillGrant

BASELINE_RUNTIME_FAMILIES = frozenset({"time_ops", "web_research"})


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


def _stable_unique(values: list[Any]) -> list[str]:
    normalized: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if text and text not in normalized:
            normalized.append(text)
    return normalized


def _manifest_skill_candidate_names(entry: Mapping[str, Any]) -> list[str]:
    names = [
        entry.get("name"),
        entry.get("entry_point"),
        entry.get("description"),
    ]
    display_name = entry.get("display_name")
    if isinstance(display_name, str):
        names.append(display_name)
    elif isinstance(display_name, Mapping):
        names.extend(display_name.values())
    return _stable_unique(names)


def _match_manifest_skill_preview(grant: AgentSkillGrant | Any) -> Mapping[str, Any]:
    skill = getattr(grant, "skill", None)
    package = getattr(skill, "package", None)
    manifest = getattr(package, "manifest", None)
    if not isinstance(manifest, Mapping):
        return {}
    extensions = manifest.get("extensions")
    if not isinstance(extensions, Mapping):
        return {}
    skills = extensions.get("skills")
    if not isinstance(skills, list):
        return {}

    candidates = {
        str(getattr(skill, "name", "") or "").strip().lower(),
        str(getattr(skill, "key", "") or "").strip().lower(),
    }
    candidates.discard("")
    for item in skills:
        if not isinstance(item, Mapping):
            continue
        entry_names = {
            name.lower()
            for name in _manifest_skill_candidate_names(item)
            if isinstance(name, str) and name.strip()
        }
        if entry_names & candidates:
            return item
    return {}


def _grant_preview_tool_names(grant: AgentSkillGrant | Any) -> list[str]:
    preview_names: list[str] = []
    skill_name = grant_skill_name_if_active(grant)
    skill = getattr(grant, "skill", None)
    if skill_name and tool_family_from_name(skill_name) != "none":
        preview_names.append(skill_name)
    skill_key = str(getattr(skill, "key", "") or "").strip()
    if skill_key and tool_family_from_name(skill_key) != "none":
        preview_names.append(skill_key)

    skill_config = getattr(skill, "config", None)
    if isinstance(skill_config, Mapping):
        preview_names.extend(list(skill_config.get("preview_tool_names") or []))
        for item in list(skill_config.get("tools") or []):
            if not isinstance(item, Mapping):
                continue
            preview_names.append(item.get("name"))

    manifest_preview = _match_manifest_skill_preview(grant)
    preview_names.extend(list(manifest_preview.get("preview_tool_names") or []))
    return _stable_unique(preview_names)


def _grant_preview_families(grant: AgentSkillGrant | Any) -> list[str]:
    families: list[str] = []
    skill = getattr(grant, "skill", None)
    skill_config = getattr(skill, "config", None)
    if isinstance(skill_config, Mapping):
        families.extend(list(skill_config.get("preview_semantic_families") or []))
    manifest_preview = _match_manifest_skill_preview(grant)
    families.extend(list(manifest_preview.get("preview_semantic_families") or []))
    for tool_name in _grant_preview_tool_names(grant):
        family = tool_family_from_name(tool_name)
        if family != "none":
            families.append(family)
    return _stable_unique(families)


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
        supported.update(_grant_preview_families(grant))
    return all(family in supported for family in families)


__all__ = [
    "BASELINE_RUNTIME_FAMILIES",
    "agent_can_handle_images",
    "agent_needs_function_calling",
    "agent_skill_names",
    "agent_supports_families",
    "agent_supports_images",
    "grant_skill_name_if_active",
]
