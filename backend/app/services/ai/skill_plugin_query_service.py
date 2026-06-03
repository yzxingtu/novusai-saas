"""Plugin skill preview query helpers."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from sqlalchemy import select

from app.ai.skills.plugin_identity import plugin_skill_lookup_name
from app.core.logging import LogManager
from app.models.ai.skill_package import SkillPackage

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.models.ai.skill import Skill

logger = LogManager.get_logger("ai")


@dataclass
class PluginSkillToolPreview:
    name: str
    description: str = ""
    parameters: list[dict] = field(default_factory=list)


@dataclass
class PluginSkillPreview:
    source_plugin: str = ""
    tools: list[PluginSkillToolPreview] = field(default_factory=list)


async def load_plugin_skill_preview(
    db: AsyncSession,
    skill: Skill,
) -> PluginSkillPreview:
    """Resolve plugin skill preview tools for API read models."""
    result = await db.execute(
        select(SkillPackage.source_plugin).where(
            SkillPackage.id == skill.package_id,
        )
    )
    source_plugin = str(result.scalar_one_or_none() or "").strip()
    preview = PluginSkillPreview(source_plugin=source_plugin)
    if not source_plugin:
        return preview

    try:
        from app.plugins.registry import ExtensionRegistry

        registry = ExtensionRegistry.get_instance()
        skill_lookup_name = plugin_skill_lookup_name(skill, source_plugin)
        if not skill_lookup_name:
            logger.warning(
                "Skip resolving plugin tools for skill {}: missing plugin skill identity",
                skill.id,
            )
            return preview

        resolver_func = registry.get_plugin_skill_resolver(
            source_plugin,
            skill_lookup_name,
        )
        if resolver_func is None:
            return preview

        config = skill.config or {}
        tool_defs = (
            await resolver_func(skill, config)
            if asyncio.iscoroutinefunction(resolver_func)
            else resolver_func(skill, config)
        )
        if not isinstance(tool_defs, list):
            return preview

        preview.tools = [
            PluginSkillToolPreview(
                name=td.name,
                description=td.description,
                parameters=[
                    {
                        "name": p.name,
                        "type": p.type,
                        "description": p.description,
                        "required": p.required,
                    }
                    for p in (td.parameters or [])
                ],
            )
            for td in tool_defs
        ]
    except Exception as exc:
        logger.warning("Failed to resolve plugin tools for skill {}: {}", skill.id, exc)
    return preview


__all__ = [
    "PluginSkillPreview",
    "PluginSkillToolPreview",
    "load_plugin_skill_preview",
]
