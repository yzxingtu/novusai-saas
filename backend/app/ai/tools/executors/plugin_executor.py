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

            # Scope 校验：platform_only 插件拒绝租户端调用
            tenant_id = context.tenant_id if context else None
            if tenant_id is not None:
                scope_check = await self._check_scope(
                    plugin_name, tenant_id, context.db if context else None,
                )
                if scope_check:
                    return ToolResult(
                        tool_call_id=tool_call_id,
                        name=definition.name,
                        success=False,
                        error=scope_check,
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

    @staticmethod
    async def _check_scope(
        plugin_name: str,
        tenant_id: int,
        db: Any | None,
    ) -> str | None:
        """
        检查插件 scope 是否允许该租户调用

        Returns:
            错误消息（拒绝时），或 None（允许时）
        """
        if not db:
            return None

        try:
            from app.repositories.system.plugin_repository import PluginRepository
            from app.enums.plugin import PluginScopeEnum

            repo = PluginRepository(db)
            plugin = await repo.get_by_name(plugin_name)
            if not plugin:
                return None

            if plugin.scope == PluginScopeEnum.PLATFORM_ONLY.value:
                return f"Plugin '{plugin_name}' is platform-only and cannot be used by tenants"

            if plugin.scope in (
                PluginScopeEnum.ASSIGNED_TENANTS.value,
                PluginScopeEnum.TENANT_ONLY.value,
            ):
                from app.repositories.system.plugin_tenant_assignment_repository import (
                    PluginTenantAssignmentRepository,
                )
                assign_repo = PluginTenantAssignmentRepository(db)
                if not await assign_repo.is_assigned(plugin.id, tenant_id):
                    return f"Plugin '{plugin_name}' is not assigned to tenant {tenant_id}"

        except Exception as exc:
            logger.warning(
                "Scope check failed for plugin %s tenant %d: %s",
                plugin_name, tenant_id, str(exc),
            )

        return None

    async def validate(
        self,
        definition: ToolDefinition,
        arguments: dict[str, Any],
    ) -> bool:
        """插件工具参数校验

        当 definition.parameters 为 dict 格式（JSON Schema）时，
        使用 jsonschema 校验 arguments。ToolParameter 列表格式由
        Sandbox 层 InputValidator 处理。
        """
        if isinstance(definition.parameters, dict) and definition.parameters:
            try:
                import jsonschema
                jsonschema.validate(instance=arguments, schema=definition.parameters)
            except jsonschema.ValidationError as exc:
                logger.warning(
                    "Plugin tool parameter validation failed: %s — %s",
                    definition.name, exc.message,
                )
                return False
            except Exception:
                pass
        return True


__all__ = ["PluginSkillExecutor"]
