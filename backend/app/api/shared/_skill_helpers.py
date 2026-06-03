"""
共享技能辅助函数 / Shared Skill Helpers

从 admin/skills.py 提取，供 admin 和 tenant 端共同使用。
Extracted from admin/skills.py, shared by admin and tenant endpoints.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.models.ai.skill import Skill
    from app.schemas.ai.skill import SkillResponse


async def enrich_plugin_skill_info(
    db: AsyncSession,
    skill: Skill,
    data: SkillResponse,
) -> None:
    """
    为插件注册的技能补充 source_plugin 和 plugin_tools 信息 / Enrich plugin skill with source_plugin and plugin_tools.

    通过 SkillPackage.source_plugin 判断是否为插件技能，
    Determines if skill is plugin-registered via SkillPackage.source_plugin,
    若是则从 ExtensionRegistry 调用 resolver 获取工具列表。
    if so, calls resolver from ExtensionRegistry to get tool list.
    """
    from app.schemas.ai.skill import PluginToolInfo
    from app.services.ai.skill_plugin_query_service import load_plugin_skill_preview

    preview = await load_plugin_skill_preview(db, skill)
    if not preview.source_plugin:
        return

    data.source_plugin = preview.source_plugin
    data.plugin_tools = [
        PluginToolInfo(
            name=tool.name,
            description=tool.description,
            parameters=tool.parameters,
        )
        for tool in preview.tools
    ]


__all__ = ["enrich_plugin_skill_info"]
