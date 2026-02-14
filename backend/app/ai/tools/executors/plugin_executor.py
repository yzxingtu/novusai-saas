"""
插件 Skill 执行器

将插件注册的 Skill 工具调用委托给 SkillPlugin.execute()。
SkillResolver 解析插件 Skill 时会设置 tool_type="plugin" 并在
config 中注入 _plugin_name 和 _skill_type，本执行器据此找到
对应的 SkillPlugin 实例并执行。
"""

from __future__ import annotations

import json
from typing import Any, TYPE_CHECKING

from app.ai.tools.executors.base import BaseToolExecutor
from app.ai.tools.types import ToolDefinition, ToolResult
from app.core.logging import LogManager

if TYPE_CHECKING:
    from app.ai.tools.types import ExecutionContext

logger = LogManager.get_logger("ai.tool.plugin")


class PluginSkillExecutor(BaseToolExecutor):
    """
    插件 Skill 执行器

    从 ToolDefinition.config 中读取 _plugin_name，
    从 PluginManager 获取 SkillPlugin 实例，
    调用其 execute(tool_name, arguments, context) 方法。
    """

    async def execute(
        self,
        definition: ToolDefinition,
        tool_call_id: str,
        arguments: dict[str, Any],
        context: ExecutionContext | None = None,
    ) -> ToolResult:
        """执行插件提供的工具"""
        plugin_name = definition.config.get("_plugin_name")
        skill_type = definition.config.get("_skill_type", "unknown")

        if not plugin_name:
            return ToolResult(
                tool_call_id=tool_call_id,
                name=definition.name,
                success=False,
                error=f"Plugin tool missing _plugin_name in config (skill_type={skill_type})",
            )

        try:
            from app.plugins.manager import get_plugin_manager

            manager = get_plugin_manager()
            instance = manager.get_skill_plugin(skill_type)

            if not instance:
                return ToolResult(
                    tool_call_id=tool_call_id,
                    name=definition.name,
                    success=False,
                    error=f"Plugin skill '{skill_type}' not loaded (plugin={plugin_name})",
                )

            skill_cfg = {
                k: v for k, v in (definition.config or {}).items()
                if not k.startswith("_")
            }

            plugin_ctx = await manager.build_execution_context(
                instance,
                db=context.db if context else None,
                tenant_id=context.tenant_id if context else None,
                skill_config=skill_cfg,
            )

            result = await instance.execute(
                definition.name, arguments, plugin_ctx,
            )

            if isinstance(result, dict):
                output = json.dumps(result, ensure_ascii=False, default=str)
            elif isinstance(result, str):
                output = result
            else:
                output = str(result)

            logger.info(
                "Plugin tool executed: plugin=%s tool=%s skill_type=%s",
                plugin_name, definition.name, skill_type,
            )
            return ToolResult(
                tool_call_id=tool_call_id,
                name=definition.name,
                success=True,
                output=output,
            )

        except Exception as exc:
            logger.error(
                "Plugin tool execution failed: plugin=%s tool=%s error=%s",
                plugin_name, definition.name, str(exc),
                exc_info=True,
            )
            return ToolResult(
                tool_call_id=tool_call_id,
                name=definition.name,
                success=False,
                error=f"Plugin execution error: {str(exc)}",
            )

    async def validate(
        self,
        definition: ToolDefinition,
        arguments: dict[str, Any],
    ) -> bool:
        """插件工具参数校验（委托给 JSON Schema 校验，此处简单放行）"""
        return True


__all__ = ["PluginSkillExecutor"]
