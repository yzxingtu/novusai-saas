"""
共享技能辅助函数

从 admin/skills.py 提取，供 admin 和 tenant 端共同使用。
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from app.core.logging import LogManager

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.models.ai.skill import Skill
    from app.schemas.ai.skill import SkillResponse

logger = LogManager.get_logger("ai")


async def enrich_plugin_skill_info(
    db: AsyncSession,
    skill: Skill,
    data: SkillResponse,
) -> None:
    """
    为插件注册的技能补充 source_plugin 和 plugin_tools 信息

    通过 SkillPackage.source_plugin 判断是否为插件技能，
    若是则从 ExtensionRegistry 调用 resolver 获取工具列表。
    """
    from sqlalchemy import select

    from app.models.ai.skill_package import SkillPackage
    from app.schemas.ai.skill import PluginToolInfo

    # 查询所属技能包的 source_plugin
    result = await db.execute(
        select(SkillPackage.source_plugin).where(
            SkillPackage.id == skill.package_id,
        )
    )
    source_plugin = result.scalar_one_or_none()

    if not source_plugin:
        return

    data.source_plugin = source_plugin

    # 从插件 registry 获取 resolver 并调用
    try:
        from app.plugins.registry import ExtensionRegistry

        registry = ExtensionRegistry.get_instance()
        resolver_func = registry.get_plugin_skill_resolver(source_plugin)
        if resolver_func is None:
            return

        config = skill.config or {}
        tool_defs = (
            await resolver_func(skill, config)
            if asyncio.iscoroutinefunction(resolver_func)
            else resolver_func(skill, config)
        )

        if isinstance(tool_defs, list):
            data.plugin_tools = [
                PluginToolInfo(
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
        logger.warning("Failed to resolve plugin tools for skill %d: %s", skill.id, exc)


__all__ = ["enrich_plugin_skill_info"]
