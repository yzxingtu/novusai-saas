"""
Skill 解析器

将 Skill 模型转换为 ToolDefinition 列表，同时提取知识库 IDs 等附加信息。

转换规则：
- knowledge_base → 0 个 ToolDefinition（通过 RAG 注入 system_prompt）
- data_intelligence → 1~4 个 ToolDefinition（data_query + CRUD）
- toolkit → N 个 ToolDefinition（Tools 类的每个公开方法一个）
- builtin → 1 个 ToolDefinition（或 N 个，如 crud_generator）

未知类型走插件解析路径。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, TYPE_CHECKING

from app.ai.tools.types import ToolDefinition, ToolParameter
from app.core.logging import LogManager
from app.enums.agent import SkillTypeEnum, ToolTypeEnum

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
    from app.models.ai.skill import Skill

logger = LogManager.get_logger("ai.skill.resolver")


@dataclass
class SkillResolveResult:
    """
    Skill 解析结果

    Attributes:
        tools: 面向 LLM 的 ToolDefinition 列表
        knowledge_base_ids: 从 knowledge_base 类型 Skill 提取的知识库 ID 列表
        rag_config: RAG 配置（合并所有 knowledge_base Skill 的配置）
    """

    tools: list[ToolDefinition] = field(default_factory=list)
    knowledge_base_ids: list[int] = field(default_factory=list)
    rag_config: dict[str, Any] = field(default_factory=dict)


class SkillResolver:
    """
    Skill → ToolDefinition 转换器

    按 Skill 类型分发到对应的转换方法。
    一个 Skill 可能产生 0~N 个 ToolDefinition。
    """

    def __init__(self, db: AsyncSession | None = None):
        self.db = db

    async def resolve(
        self,
        skills: list[Skill],
        config_overrides: dict[int, dict[str, Any]] | None = None,
    ) -> SkillResolveResult:
        """
        批量解析 Skill 列表

        Args:
            skills: Skill 模型列表（已按 sort_order 排序）
            config_overrides: 每个 Skill 的配置覆盖（key=skill.id）

        Returns:
            SkillResolveResult
        """
        result = SkillResolveResult()
        overrides = config_overrides or {}

        for skill in skills:
            if not skill.is_active:
                continue

            # 合并配置：Skill.config + binding.config_override
            merged_config = dict(skill.config or {})
            if skill.id in overrides and overrides[skill.id]:
                merged_config.update(overrides[skill.id])

            try:
                await self._resolve_one(skill, merged_config, result)
            except Exception as exc:
                logger.warning(
                    "Failed to resolve skill %d (%s): %s",
                    skill.id, skill.name, str(exc),
                )

        logger.info(
            "Resolved %d skills → %d tools, %d knowledge_bases",
            len(skills), len(result.tools), len(result.knowledge_base_ids),
        )
        return result

    async def _resolve_one(
        self,
        skill: Skill,
        config: dict[str, Any],
        result: SkillResolveResult,
    ) -> None:
        """按类型分发到对应的转换方法"""
        skill_type = skill.type

        if skill_type == SkillTypeEnum.KNOWLEDGE_BASE.value:
            self._resolve_knowledge_base(skill, config, result)
        elif skill_type == SkillTypeEnum.DATA_INTELLIGENCE.value:
            await self._resolve_data_intelligence(skill, config, result)
        elif skill_type == SkillTypeEnum.TOOLKIT.value:
            self._resolve_toolkit(skill, config, result)
        elif skill_type == SkillTypeEnum.BUILTIN.value:
            self._resolve_builtin(skill, config, result)
        else:
            await self._resolve_plugin_skill(skill, config, result)

    # ========================================
    # 知识库 Skill
    # ========================================

    def _resolve_knowledge_base(
        self,
        skill: Skill,
        config: dict[str, Any],
        result: SkillResolveResult,
    ) -> None:
        """
        知识库 Skill → 0 个 ToolDefinition

        不生成工具，而是提取 knowledge_base_ids 供 RAG 注入。
        """
        kb_ids = config.get("knowledge_base_ids", [])
        if isinstance(kb_ids, list):
            for kid in kb_ids:
                if isinstance(kid, int) and kid not in result.knowledge_base_ids:
                    result.knowledge_base_ids.append(kid)

        # 合并 RAG 配置（存储在 config.rag_config 子字典中）
        rag_cfg = config.get("rag_config", {})
        if isinstance(rag_cfg, dict):
            rag_keys = [
                "enabled", "top_k", "score_threshold", "search_mode",
                "rewrite_strategy", "reranker_enabled",
                "context_token_ratio",
            ]
            for key in rag_keys:
                if key in rag_cfg:
                    result.rag_config[key] = rag_cfg[key]

    # ========================================
    # 数据智能 Skill
    # ========================================

    async def _resolve_data_intelligence(
        self,
        skill: Skill,
        config: dict[str, Any],
        result: SkillResolveResult,
    ) -> None:
        """
        数据智能 Skill → 1~4 个 ToolDefinition

        - data_query 始终生成（只要有可访问的表）
        - data_create / data_update / data_delete 由 Table Policy 的
          allow_create / allow_update / allow_delete 每表开关控制

        CRUD 权限的唯一控制源是 /admin/ai/table-policies 页面。

        Skill.config 结构：
        {
            "table_policy_ids": [1, 5, 12],
            "timeout": 60
        }
        """
        # 从 Skill.config 提取 table_policy_ids（选择哪些表策略给 Agent 用）
        table_policy_ids: list[int] | None = config.get("table_policy_ids")

        # 从 SchemaProvider 加载表描述和 CRUD 权限（由 Table Policy 控制）
        table_descriptions: list[tuple[str, str]] = []
        crud_allowed_tables: dict[str, list[tuple[str, str]]] = {}

        if self.db:
            try:
                from app.ai.data_intelligence.schema_provider import SchemaProvider
                table_descriptions = await SchemaProvider.get_table_descriptions(
                    self.db, table_policy_ids=table_policy_ids,
                )
                crud_allowed_tables = await SchemaProvider.get_crud_allowed_tables(
                    self.db, table_policy_ids=table_policy_ids,
                )
            except Exception as exc:
                logger.warning("Failed to load table descriptions: %s", str(exc))

        # data_query 工具（始终生成）
        if table_descriptions:
            table_list = ", ".join(
                f"{name}({label})" for name, label in table_descriptions
            )
        else:
            table_list = "(no tables configured)"

        result.tools.append(ToolDefinition(
            name="data_query",
            description=(
                "Query the database using natural language. "
                "The system will automatically generate safe SQL and return results. "
                f"Available tables: {table_list}. "
                "IMPORTANT: You MUST use this tool for ANY question about data counts, "
                "totals, statistics, listings, or aggregations — including tenant counts, "
                "user counts, agent counts, conversation counts, usage stats, etc. "
                "Do NOT use other action tools for counting or statistical questions."
            ),
            tool_type=ToolTypeEnum.TEXT_TO_SQL.value,
            parameters=[
                ToolParameter(
                    name="question",
                    type="string",
                    description="The data question in natural language",
                    required=True,
                ),
            ],
            config={},
            enabled=True,
            timeout=config.get("timeout", 60),
            source_skill_id=skill.id,
            source_skill_name=skill.name,
            source_skill_type=skill.type,
        ))

        # CRUD 工具 — 直接由 Table Policy 的每表 allow_create/update/delete 控制
        create_tables = crud_allowed_tables.get("create", [])
        if create_tables:
            create_list = ", ".join(f"{n}({l})" for n, l in create_tables)
            result.tools.append(ToolDefinition(
                name="data_create",
                description=(
                    "Create a new record in a database table. "
                    "First call without 'confirmed' to get a preview; "
                    "then call again with confirmed=true after user approval. "
                    f"ONLY these tables allow creation: {create_list}. "
                    "Do NOT attempt to create records in any other table."
                ),
                tool_type=ToolTypeEnum.DATA_CREATE.value,
                parameters=[
                    ToolParameter(name="table_name", type="string",
                                  description="Target table name", required=True),
                    ToolParameter(name="data", type="object",
                                  description="Record data as {field: value}", required=True),
                    ToolParameter(name="confirmed", type="boolean",
                                  description="Set to true after user confirms"),
                ],
                config={},
                enabled=True,
                timeout=skill.timeout,
                source_skill_id=skill.id,
                source_skill_name=skill.name,
                source_skill_type=skill.type,
            ))

        update_tables = crud_allowed_tables.get("update", [])
        if update_tables:
            update_list = ", ".join(f"{n}({l})" for n, l in update_tables)
            result.tools.append(ToolDefinition(
                name="data_update",
                description=(
                    "Update an existing record in a database table. "
                    "First call without 'confirmed' to see a diff preview; "
                    "then call again with confirmed=true after user approval. "
                    f"ONLY these tables allow updates: {update_list}. "
                    "Do NOT attempt to update records in any other table."
                ),
                tool_type=ToolTypeEnum.DATA_UPDATE.value,
                parameters=[
                    ToolParameter(name="table_name", type="string",
                                  description="Target table name", required=True),
                    ToolParameter(name="id", type="integer",
                                  description="Record ID to update", required=True),
                    ToolParameter(name="data", type="object",
                                  description="Fields to update as {field: value}", required=True),
                    ToolParameter(name="confirmed", type="boolean",
                                  description="Set to true after user confirms"),
                ],
                config={},
                enabled=True,
                timeout=skill.timeout,
                source_skill_id=skill.id,
                source_skill_name=skill.name,
                source_skill_type=skill.type,
            ))

        delete_tables = crud_allowed_tables.get("delete", [])
        if delete_tables:
            delete_list = ", ".join(f"{n}({l})" for n, l in delete_tables)
            result.tools.append(ToolDefinition(
                name="data_delete",
                description=(
                    "Soft-delete a record from a database table. "
                    "First call without 'confirmed' to see record details; "
                    "then call again with confirmed=true after user explicitly confirms. "
                    f"ONLY these tables allow deletion: {delete_list}. "
                    "Do NOT attempt to delete records in any other table."
                ),
                tool_type=ToolTypeEnum.DATA_DELETE.value,
                parameters=[
                    ToolParameter(name="table_name", type="string",
                                  description="Target table name", required=True),
                    ToolParameter(name="id", type="integer",
                                  description="Record ID to delete", required=True),
                    ToolParameter(name="confirmed", type="boolean",
                                  description="Set to true after user confirms"),
                ],
                config={},
                enabled=True,
                timeout=skill.timeout,
                source_skill_id=skill.id,
                source_skill_name=skill.name,
                source_skill_type=skill.type,
            ))

    # ========================================
    # Toolkit Skill
    # ========================================

    def _resolve_toolkit(
        self,
        skill: Skill,
        config: dict[str, Any],
        result: SkillResolveResult,
    ) -> None:
        """
        Toolkit Skill → N 个 ToolDefinition

        解析 Toolkit Python 源码，每个 Tools 类的公开方法生成一个 ToolDefinition。
        Valves 配置从 config 中读取并注入到每个工具的 config 中。
        """
        toolkit_content = getattr(skill, "toolkit_content", None) or ""
        if not toolkit_content:
            logger.warning(
                "Toolkit skill %d (%s) has no toolkit_content",
                skill.id, skill.name,
            )
            return

        from app.ai.skills.toolkit_parser import (
            parse_toolkit,
            toolkit_tools_to_definitions,
        )

        meta = parse_toolkit(toolkit_content)
        tool_defs = toolkit_tools_to_definitions(meta)

        # Valves 配置从 binding config_override 或 skill config 中获取
        valves_config = config.get("valves", {})

        for td in tool_defs:
            td.tool_type = ToolTypeEnum.TOOLKIT.value
            td.config = {
                "_toolkit_content": toolkit_content,
                "_toolkit_method": td.name,
                "_toolkit_is_async": td.config.get("is_async", True),
                "_valves_config": valves_config,
                "_toolkit_trusted": bool(getattr(skill, "is_system", False)),
            }
            td.enabled = True
            td.timeout = skill.timeout
            td.source_skill_id = skill.id
            td.source_skill_name = skill.name
            td.source_skill_type = skill.type
            result.tools.append(td)

        logger.debug(
            "Toolkit skill '%s' resolved %d tools",
            skill.name, len(tool_defs),
        )

    # ========================================
    # Builtin Skill
    # ========================================

    def _resolve_builtin(
        self,
        skill: Skill,
        config: dict[str, Any],
        result: SkillResolveResult,
    ) -> None:
        """
        Builtin Skill → ToolDefinition

        支持三种模式：
        1. crud_generator 模式：builtin_type="crud_generator" → N 个 ToolDefinition
        2. 多工具模式：config.tools 列表 → N 个 ToolDefinition
        3. 单工具模式（默认）：skill 本身即为一个工具
        """
        builtin_type = config.get("builtin_type", "")
        if builtin_type == "crud_generator":
            self._resolve_crud_generator(skill, config, result)
            return

        tools_config = config.get("tools")
        tool_type_override = config.get("tool_type", ToolTypeEnum.BUILTIN.value)

        if tools_config and isinstance(tools_config, list):
            for tool_cfg in tools_config:
                tool_name = tool_cfg.get("name", "")
                if not tool_name:
                    continue
                tool_params = self._build_params_from_schema(
                    tool_cfg.get("parameters")
                )
                result.tools.append(ToolDefinition(
                    name=tool_name,
                    description=tool_cfg.get("description", ""),
                    tool_type=tool_type_override,
                    parameters=tool_params,
                    config=config,
                    enabled=True,
                    timeout=tool_cfg.get("timeout", skill.timeout),
                    source_skill_id=skill.id,
                    source_skill_name=skill.name,
                    source_skill_type=skill.type,
                ))
        else:
            params = self._build_params_from_schema(skill.input_schema)
            result.tools.append(ToolDefinition(
                name=skill.name,
                description=skill.description or "",
                tool_type=tool_type_override,
                parameters=params,
                config=config,
                enabled=True,
                timeout=skill.timeout,
                source_skill_id=skill.id,
                source_skill_name=skill.name,
                source_skill_type=skill.type,
            ))

    # ========================================
    # CRUD Generator (builtin 子类型)
    # ========================================

    def _resolve_crud_generator(
        self,
        skill: Skill,
        config: dict[str, Any],
        result: SkillResolveResult,
    ) -> None:
        """
        CRUD Generator → 8 个 ToolDefinition

        从 skill.input_schema 的 multi_tool 格式读取工具定义。
        dev_only 检查：当 config.dev_only=True 且 APP_ENV != development 时跳过。
        """
        import os

        if config.get("dev_only") and os.getenv("APP_ENV") != "development":
            logger.info(
                "Skipping crud_generator skill %d (dev_only, APP_ENV=%s)",
                skill.id, os.getenv("APP_ENV"),
            )
            return

        input_schema = skill.input_schema or {}
        tools_schema = input_schema.get("tools", {})

        if not tools_schema:
            logger.warning(
                "crud_generator skill %d has no tools in input_schema",
                skill.id,
            )
            return

        count = 0
        for tool_name, tool_spec in tools_schema.items():
            params = self._build_params_from_schema(
                tool_spec.get("parameters")
            )
            result.tools.append(ToolDefinition(
                name=tool_name,
                description=tool_spec.get("description", ""),
                tool_type=ToolTypeEnum.CRUD_GENERATOR.value,
                parameters=params,
                config=config,
                enabled=True,
                timeout=skill.timeout,
                source_skill_id=skill.id,
                source_skill_name=skill.name,
                source_skill_type=skill.type,
            ))
            count += 1

        logger.info(
            "crud_generator skill '%s' resolved %d tools",
            skill.name, count,
        )

    # ========================================
    # 插件 Skill
    # ========================================

    async def _resolve_plugin_skill(
        self,
        skill: Skill,
        config: dict[str, Any],
        result: SkillResolveResult,
    ) -> None:
        """
        插件注册的 Skill 类型 → 委托给 SkillPlugin.resolve()

        PluginManager 中已启用的 SkillPlugin 通过 get_skill_type() 注册了
        自定义 skill_type。此方法将 Skill 配置传给插件的 resolve() 方法，
        获取 ToolDefinition 列表，并强制设置 tool_type="plugin" 以便
        Sandbox 通过 PluginSkillExecutor 执行。
        """
        try:
            from app.plugins.manager import get_plugin_manager

            manager = get_plugin_manager()

            instance = manager.get_skill_plugin(skill.type)
            if not instance:
                logger.warning(
                    "Unknown skill type: %s (skill=%d)", skill.type, skill.id,
                )
                return

            tool_defs = instance.resolve(config)
            if not tool_defs:
                return

            from app.enums.agent import ToolTypeEnum

            for td in tool_defs:
                if isinstance(td.parameters, dict):
                    td.parameters = self._build_params_from_schema(td.parameters)
                td.tool_type = ToolTypeEnum.PLUGIN.value
                td.config = dict(td.config) if td.config else {}
                td.config["_plugin_name"] = instance.name
                td.config["_skill_type"] = skill.type
                td.source_skill_id = skill.id
                td.source_skill_name = skill.name
                td.source_skill_type = skill.type
                result.tools.append(td)

            logger.debug(
                "Plugin skill '%s' resolved %d tools via %s",
                skill.type, len(tool_defs), instance.name,
            )
        except Exception as exc:
            logger.warning(
                "Failed to resolve plugin skill %s (skill=%d): %s",
                skill.type, skill.id, str(exc),
            )

    # ========================================
    # 辅助方法
    # ========================================

    @staticmethod
    def _build_params_from_schema(
        input_schema: dict[str, Any] | None,
    ) -> list[ToolParameter]:
        """
        从 JSON Schema 构建 ToolParameter 列表

        input_schema 格式：
        {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "城市名"},
                "unit": {"type": "string", "enum": ["celsius", "fahrenheit"]}
            },
            "required": ["city"]
        }
        """
        if not input_schema:
            return []

        properties = input_schema.get("properties", {})
        required_set = set(input_schema.get("required", []))
        params: list[ToolParameter] = []

        for name, prop in properties.items():
            params.append(ToolParameter(
                name=name,
                type=prop.get("type", "string"),
                description=prop.get("description", ""),
                required=name in required_set,
                default=prop.get("default"),
                enum=prop.get("enum"),
            ))

        return params


__all__ = ["SkillResolver", "SkillResolveResult"]
