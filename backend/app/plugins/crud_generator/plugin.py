"""
CRUD Generator Plugin — 可视化代码生成器插件

同时实现 ApiPlugin（动态路由）和 SkillPlugin（AI 技能）：
- ApiPlugin: POST /preview, /generate, /conflicts, /ddl, GET/POST /records
- SkillPlugin: 8 个 AI 工具（fill_crud_config, add_fields, add_relations, ...）
"""

from __future__ import annotations

import inspect
import re
from typing import Any, TYPE_CHECKING

from app.core.i18n import _
from app.plugins.extensions.api_plugin import ApiPlugin
from app.plugins.extensions.skill_plugin import SkillPlugin

if TYPE_CHECKING:
    from fastapi import APIRouter
    from app.ai.tools.types import ToolDefinition
    from app.plugins.context import PluginContext


class CrudGeneratorPlugin(ApiPlugin, SkillPlugin):
    """CRUD 代码生成器插件（API + Skill 双扩展点）"""

    @property
    def name(self) -> str:
        return "crud-generator"

    @property
    def display_name(self) -> str:
        return _("plugin.crud_generator.display_name")

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def description(self) -> str:
        return _("plugin.crud_generator.description")

    @property
    def icon(self) -> str:
        return "lucide:wand-2"

    @property
    def scope(self) -> str:
        return "platform_only"

    # ========================================
    # ApiPlugin — 动态路由
    # ========================================

    def get_router(self) -> APIRouter:
        from app.plugins.crud_generator.api.dev_crud import router as crud_router
        from app.plugins.crud_generator.api.dev_crud_records import (
            router as records_router,
        )

        from fastapi import APIRouter

        combined = APIRouter()
        combined.include_router(crud_router, prefix="/crud")
        combined.include_router(records_router, prefix="/crud/records")
        return combined

    def get_route_prefix(self) -> str:
        return ""

    def get_auth_level(self) -> str:
        return "admin_only"

    # ========================================
    # SkillPlugin — AI 技能
    # ========================================

    def get_skill_type(self) -> str:
        return "crud_generator"

    def get_skill_display_name(self) -> str:
        return "CRUD Generator Toolkit"

    def get_skill_icon(self) -> str:
        return "lucide:wand-2"

    def get_skill_config_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "dev_only": {
                    "type": "boolean",
                    "title": "Dev Only",
                    "description": "Only available in development environment",
                    "default": True,
                },
            },
        }

    def resolve(
        self,
        skill_config: dict[str, Any],
    ) -> list[ToolDefinition]:
        """将 crud_form_toolkit.Tools 的公开方法解析为 ToolDefinition 列表"""
        from app.ai.tools.types import ToolDefinition, ToolParameter
        from app.plugins.crud_generator.codegen.crud_form_toolkit import Tools

        tool_defs: list[ToolDefinition] = []
        instance = Tools()

        for method_name in dir(instance):
            if method_name.startswith("_"):
                continue
            method = getattr(instance, method_name)
            if not callable(method):
                continue

            sig = inspect.signature(method)
            doc = inspect.getdoc(method) or ""

            # 提取描述和参数文档
            desc_lines: list[str] = []
            param_docs: dict[str, str] = {}
            for line in doc.split("\n"):
                m = re.match(r"\s*:param\s+(\w+):\s*(.*)", line)
                if m:
                    param_docs[m.group(1)] = m.group(2)
                else:
                    desc_lines.append(line)
            description = "\n".join(desc_lines).strip()

            params: list[ToolParameter] = []
            for param_name, param in sig.parameters.items():
                if param_name == "self":
                    continue
                params.append(ToolParameter(
                    name=param_name,
                    type="string",
                    description=param_docs.get(param_name, ""),
                    required=param.default is inspect.Parameter.empty,
                    default=(
                        param.default
                        if param.default is not inspect.Parameter.empty
                        else None
                    ),
                ))

            tool_defs.append(ToolDefinition(
                name=method_name,
                description=description,
                parameters=params,
                config=skill_config,
                timeout=120,
            ))

        return tool_defs

    async def execute(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        context: PluginContext,
    ) -> dict[str, Any] | str:
        """执行 CRUD Toolkit 工具调用"""
        import json
        from app.plugins.crud_generator.codegen.crud_form_toolkit import Tools

        instance = Tools()
        method = getattr(instance, tool_name, None)
        if not method:
            return json.dumps({"error": f"Unknown tool: {tool_name}"})

        try:
            result = method(**arguments)
            return result
        except Exception as exc:
            return json.dumps({"error": f"Tool execution failed: {exc}"})
