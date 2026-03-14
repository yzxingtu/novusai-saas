"""
Skill Resolver
Skill 解析器

Converts Skill models to ToolDefinition lists.
将 Skill 模型转换为 ToolDefinition 列表。

Conversion rules / 转换规则：
- data_intelligence → 1~4 ToolDefinitions (data_query + CRUD)
- toolkit → N ToolDefinitions (one per public method of Tools class)
- builtin → 1 ToolDefinition (or N, via config.tools list)

Knowledge base bindings have been migrated to AgentKnowledgeBaseBinding,
no longer resolved through Skill.
知识库绑定已迁移至 AgentKnowledgeBaseBinding 中间表，不再通过 Skill 解析。

Unknown types fall through to plugin resolver path.
未知类型走插件解析路径。
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from app.ai.events.hooks import HookPoint, get_hook_registry
from app.ai.tools.types import ToolDefinition, ToolParameter
from app.core.logging import LogManager
from app.enums.agent import SkillTypeEnum, ToolTypeEnum
from app.enums.common import AudienceEnum, ResourceScopeEnum, UserRoleEnum

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.models.ai.skill import Skill

logger = LogManager.get_logger("ai.skill.resolver")


@dataclass
class SkillResolveResult:
    """
    Skill resolve result.
    Skill 解析结果。

    Attributes:
        tools: ToolDefinition list for LLM / 面向 LLM 的 ToolDefinition 列表
    """

    tools: list[ToolDefinition] = field(default_factory=list)
    tool_consent_modes: dict[str, str] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


class SkillResolver:
    """
    Skill → ToolDefinition converter.
    Skill → ToolDefinition 转换器。

    Dispatches to corresponding conversion method by Skill type.
    A single Skill may produce 0~N ToolDefinitions.
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
        Batch resolve Skill list.
        批量解析 Skill 列表。

        Args:
            skills: Skill model list (sorted by sort_order) / Skill 模型列表（已按 sort_order 排序）
            config_overrides: Config override per Skill (key=skill.id) / 每个 Skill 的配置覆盖（key=skill.id）

        Returns:
            SkillResolveResult
        """
        result = SkillResolveResult()
        overrides = config_overrides or {}

        # Pre-load source_plugin for all skill packages (batch query)
        # 预加载所有技能所属技能包的 source_plugin（批量查询）
        plugin_map = await self._load_source_plugins(skills)

        for skill in skills:
            if not skill.is_active:
                continue

            # Merge config: Skill.config + binding.config_override
            # 合并配置：Skill.config + binding.config_override
            merged_config = dict(skill.config or {})
            if skill.id in overrides and overrides[skill.id]:
                merged_config.update(overrides[skill.id])

            source_plugin = plugin_map.get(skill.package_id)

            try:
                await self._resolve_one(skill, merged_config, result, source_plugin)
            except Exception as exc:
                warning_msg = f"Skill '{skill.name}' (id={skill.id}) failed to load: {str(exc)}"
                result.warnings.append(warning_msg)
                logger.warning(
                    "Failed to resolve skill %d (%s): %s",
                    skill.id, skill.name, str(exc),
                )

        # Prevent tool name duplicates causing execution and consent attribution mismatch
        # 避免工具重名导致执行与 consent 归因错配
        self._ensure_unique_tool_names(result.tools)

        logger.info(
            "Resolved %d skills → %d tools",
            len(skills), len(result.tools),
        )
        return result

    async def _load_source_plugins(
        self, skills: list[Skill],
    ) -> dict[int, str]:
        """
        Batch query source_plugin field for skill packages.
        批量查询技能包的 source_plugin 字段。

        Returns:
            {package_id: source_plugin_name} only includes records with source_plugin /
            仅包含有 source_plugin 的记录
        """
        if not self.db or not skills:
            return {}

        package_ids = list({s.package_id for s in skills if s.package_id})
        if not package_ids:
            return {}

        from sqlalchemy import select

        from app.models.ai.skill_package import SkillPackage

        stmt = select(
            SkillPackage.id, SkillPackage.source_plugin,
        ).where(
            SkillPackage.id.in_(package_ids),
            SkillPackage.source_plugin.isnot(None),
        )
        rows = await self.db.execute(stmt)
        return {row.id: row.source_plugin for row in rows}

    async def _resolve_one(
        self,
        skill: Skill,
        config: dict[str, Any],
        result: SkillResolveResult,
        source_plugin: str | None = None,
    ) -> None:
        """
        Dispatch to corresponding conversion method by type.
        按类型分发到对应的转换方法。

        Plugin skills (source_plugin has value) take priority for plugin resolver,
        regardless of their type (can be toolkit or other standard types).
        插件技能（source_plugin 有值）优先走插件 resolver，
        不论其 type 是什么（可以是 toolkit 等标准类型）。

        Skills with config.internal=true are for internal system dispatch
        (e.g., llm_chat, llm_embedding), not resolved as function calling tools.
        config.internal=true 的技能为系统内部调度用途（如 llm_chat、
        llm_embedding），不解析为 function calling 工具。
        """
        # Skip internal dispatch skills (not exposed to LLM as function calling tools)
        # 跳过内部调度技能（不暴露给 LLM 作为 function calling 工具）
        if config.get("internal"):
            return

        # Plugin skills take priority for plugin resolver
        # 插件技能优先走插件 resolver
        if source_plugin:
            await self._resolve_plugin_skill(skill, config, result, source_plugin)
            return

        skill_type = skill.type

        if skill_type == SkillTypeEnum.DATA_INTELLIGENCE.value:
            await self._resolve_data_intelligence(skill, config, result)
        elif skill_type == SkillTypeEnum.TOOLKIT.value:
            self._resolve_toolkit(skill, config, result)
        elif skill_type == SkillTypeEnum.BUILTIN.value:
            self._resolve_builtin(skill, config, result)
        elif skill_type == SkillTypeEnum.HTTP.value:
            self._resolve_http(skill, config, result)
        elif skill_type == SkillTypeEnum.EMAIL.value:
            self._resolve_email(skill, config, result)
        elif skill_type == SkillTypeEnum.CODE_EXECUTION.value:
            self._resolve_code_execution(skill, config, result)
        else:
            logger.warning(
                "Unknown skill type: %s (skill=%d), no resolver available",
                skill_type, skill.id,
            )

    # ========================================
    # Data Intelligence Skill / 数据智能 Skill
    # ========================================

    async def _resolve_data_intelligence(
        self,
        skill: Skill,
        config: dict[str, Any],
        result: SkillResolveResult,
    ) -> None:
        """
        Data Intelligence Skill → 1~4 ToolDefinitions.
        数据智能 Skill → 1~4 个 ToolDefinition。

        - data_query is always generated (as long as there are accessible tables)
        - data_query 始终生成（只要有可访问的表）
        - data_create / data_update / data_delete controlled by Table Policy's
          per-table allow_create / allow_update / allow_delete switches
        - data_create / data_update / data_delete 由 Table Policy 的
          allow_create / allow_update / allow_delete 每表开关控制

        The sole control source for CRUD permissions is the /admin/ai/table-policies page.
        CRUD 权限的唯一控制源是 /admin/ai/table-policies 页面。

        Skill.config structure / Skill.config 结构：
        {
            "table_policy_ids": [1, 5, 12],
            "timeout": 60
        }
        """
        # Extract table_policy_ids from Skill.config (which table policies to use for Agent)
        # 从 Skill.config 提取 table_policy_ids（选择哪些表策略给 Agent 用）
        table_policy_ids: list[int] | None = config.get("table_policy_ids")

        # Load table descriptions and CRUD permissions from SchemaProvider (controlled by Table Policy)
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

        # data_query tool (always generated) / data_query 工具（始终生成）
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

        # CRUD tools — directly controlled by Table Policy's per-table allow_create/update/delete
        # CRUD 工具 — 直接由 Table Policy 的每表 allow_create/update/delete 控制
        create_tables = crud_allowed_tables.get("create", [])
        if create_tables:
            create_list = ", ".join(
                f"{table_name}({labels})" for table_name, labels in create_tables
            )
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
            update_list = ", ".join(
                f"{table_name}({labels})" for table_name, labels in update_tables
            )
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
            delete_list = ", ".join(
                f"{table_name}({labels})" for table_name, labels in delete_tables
            )
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
        Toolkit Skill → N ToolDefinitions.
        Toolkit Skill → N 个 ToolDefinition。

        Parses Toolkit Python source, generates one ToolDefinition per public method of Tools class.
        Valves config is read from config and injected into each tool's config.
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

        # Valves config obtained from binding config_override or skill config
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
        Builtin Skill → ToolDefinition.

        Supports two modes / 支持两种模式：
        1. Multi-tool mode: config.tools list → N ToolDefinitions
           多工具模式：config.tools 列表 → N 个 ToolDefinition
        2. Single-tool mode (default): skill itself is one tool
           单工具模式（默认）：skill 本身即为一个工具
        """
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
    # HTTP/Webhook Skill
    # ========================================

    def _resolve_http(
        self,
        skill: Skill,
        config: dict[str, Any],
        result: SkillResolveResult,
    ) -> None:
        """
        HTTP/Webhook Skill → 1 ToolDefinition.

        Declarative HTTP calls: users only need to fill in URL / Method / Headers / Body template,
        no code required to integrate external APIs.
        声明式 HTTP 调用：用户只需填写 URL / Method / Headers / Body 模板，
        无需编写代码即可集成外部 API。

        Skill.config structure / Skill.config 结构：
        {
            "url": "https://api.example.com/v1/data",
            "method": "POST",
            "headers": {"Authorization": "Bearer {{api_key}}"},
            "body_template": "{\"query\": \"{{question}}\"}",
            "query_params": {"format": "json"},
            "auth_type": "none|bearer|api_key|basic",
            "auth_config": {"token": "xxx"} | {"key_name": "X-API-Key", "key_value": "xxx"} | {"username": "x", "password": "y"},
            "response_path": "$.data.result",
            "timeout": 30
        }
        """
        url = config.get("url", "")
        if not url:
            logger.warning(
                "HTTP skill %d (%s) has no URL configured",
                skill.id, skill.name,
            )
            return

        method = (config.get("method", "GET") or "GET").upper()
        body_template = config.get("body_template", "")
        response_path = config.get("response_path", "")

        # Extract {{variable}} placeholders from body_template as LLM parameters
        # 从 body_template 提取 {{variable}} 占位符作为 LLM 参数
        import re
        template_vars = re.findall(r"\{\{(\w+)\}\}", body_template or "")
        # Also extract variables from URL and query_params
        # 也从 URL 和 query_params 提取变量
        url_vars = re.findall(r"\{\{(\w+)\}\}", url)
        query_params = config.get("query_params", {}) or {}
        qp_vars = []
        for v in query_params.values():
            if isinstance(v, str):
                qp_vars.extend(re.findall(r"\{\{(\w+)\}\}", v))

        all_vars = list(dict.fromkeys(url_vars + template_vars + qp_vars))

        params: list[ToolParameter] = []
        for var_name in all_vars:
            params.append(ToolParameter(
                name=var_name,
                type="string",
                description=f"Value for {{{{{var_name}}}}}",
                required=True,
            ))

        # If no template variables but has body, add generic input parameter
        # 如果没有模板变量但有 body，添加通用 input 参数
        if not params and method in ("POST", "PUT", "PATCH"):
            params.append(ToolParameter(
                name="input",
                type="string",
                description="Request body or input data",
                required=True,
            ))

        description = skill.description or f"Call {method} {url}"

        result.tools.append(ToolDefinition(
            name=skill.name.lower().replace(" ", "_"),
            description=description,
            tool_type=ToolTypeEnum.HTTP.value,
            parameters=params,
            config={
                "_http_url": url,
                "_http_method": method,
                "_http_headers": config.get("headers", {}),
                "_http_body_template": body_template,
                "_http_query_params": query_params,
                "_http_auth_type": config.get("auth_type", "none"),
                "_http_auth_config": config.get("auth_config", {}),
                "_http_response_path": response_path,
            },
            enabled=True,
            timeout=config.get("timeout", skill.timeout),
            source_skill_id=skill.id,
            source_skill_name=skill.name,
            source_skill_type=skill.type,
        ))

        logger.debug(
            "HTTP skill '%s' resolved: %s %s (%d params)",
            skill.name, method, url, len(params),
        )

    # ========================================
    # Email Skill
    # ========================================

    def _resolve_email(
        self,
        skill: Skill,
        config: dict[str, Any],
        result: SkillResolveResult,
    ) -> None:
        """
        Email Skill → 1 ToolDefinition (send_email).

        Leverages existing EmailService to send emails. Default consent_mode=ask
        (sending emails requires user confirmation).
        利用已有的 EmailService 发送邮件。默认 consent_mode=ask（发邮件需用户确认）。

        Skill.config structure / Skill.config 结构：
        {
            "subject_prefix": "[NovusAI]",
            "allowed_domains": ["example.com"],
            "max_recipients": 5,
            "require_confirmation": true,
            "allow_cc": true,
            "allow_attachments": false
        }
        """
        max_recipients = config.get("max_recipients", 5)
        allow_cc = config.get("allow_cc", True)

        description = (
            "Send an email to specified recipients. "
            f"Maximum {max_recipients} recipients allowed."
        )
        if skill.description:
            description = skill.description

        params: list[ToolParameter] = [
            ToolParameter(
                name="to",
                type="string",
                description="Recipient email address(es), comma-separated for multiple",
                required=True,
            ),
            ToolParameter(
                name="subject",
                type="string",
                description="Email subject line",
                required=True,
            ),
            ToolParameter(
                name="body",
                type="string",
                description="Email body content (supports HTML)",
                required=True,
            ),
        ]

        if allow_cc:
            params.append(ToolParameter(
                name="cc",
                type="string",
                description="CC email address(es), comma-separated (optional)",
                required=False,
            ))

        result.tools.append(ToolDefinition(
            name="send_email",
            description=description,
            tool_type=ToolTypeEnum.EMAIL.value,
            parameters=params,
            config={
                "_email_subject_prefix": config.get("subject_prefix", ""),
                "_email_allowed_domains": config.get("allowed_domains", []),
                "_email_max_recipients": max_recipients,
                "_email_require_confirmation": config.get("require_confirmation", True),
                "_email_allow_cc": allow_cc,
                "_email_allow_attachments": config.get("allow_attachments", False),
            },
            enabled=True,
            timeout=config.get("timeout", skill.timeout),
            source_skill_id=skill.id,
            source_skill_name=skill.name,
            source_skill_type=skill.type,
        ))

        logger.debug("Email skill '%s' resolved", skill.name)

    # ========================================
    # Code Execution Skill
    # ========================================

    def _resolve_code_execution(
        self,
        skill: Skill,
        config: dict[str, Any],
        result: SkillResolveResult,
    ) -> None:
        """
        Code Execution Skill → 1 ToolDefinition (execute_code).

        Executes user-provided code in a secure sandbox.
        在安全沙箱中执行用户提供的代码。

        Skill.config structure / Skill.config 结构：
        {
            "language": "python",
            "timeout": 30,
            "memory_limit_mb": 256,
            "allowed_modules": ["math", "json", "datetime", "re", "collections"]
        }
        """
        language = config.get("language", "python")
        allowed_modules = config.get("allowed_modules", [
            "math", "json", "datetime", "re", "collections",
            "itertools", "functools", "statistics", "decimal",
            "fractions", "random", "string", "textwrap",
        ])

        description = (
            f"Execute {language} code in a secure sandbox. "
            f"Allowed modules: {', '.join(allowed_modules[:10])}. "
            "Use this for calculations, data processing, or text manipulation. "
            "The code must print its output to stdout."
        )
        if skill.description:
            description = skill.description

        result.tools.append(ToolDefinition(
            name="execute_code",
            description=description,
            tool_type=ToolTypeEnum.CODE_EXECUTION.value,
            parameters=[
                ToolParameter(
                    name="code",
                    type="string",
                    description=f"The {language} code to execute. Must use print() to output results.",
                    required=True,
                ),
            ],
            config={
                "_code_language": language,
                "_code_timeout": config.get("timeout", skill.timeout),
                "_code_memory_limit_mb": config.get("memory_limit_mb", 256),
                "_code_allowed_modules": allowed_modules,
            },
            enabled=True,
            timeout=config.get("timeout", skill.timeout),
            source_skill_id=skill.id,
            source_skill_name=skill.name,
            source_skill_type=skill.type,
        ))

        logger.debug(
            "Code execution skill '%s' resolved: lang=%s",
            skill.name, language,
        )

    # ========================================
    # Plugin Skill / 插件 Skill
    # ========================================

    async def _resolve_plugin_skill(
        self,
        skill: Skill,
        config: dict[str, Any],
        result: SkillResolveResult,
        source_plugin: str = "",
    ) -> None:
        """
        Plugin skill resolution — query ExtensionRegistry by plugin_name to get plugin resolver.
        插件技能解析 — 按 plugin_name 查询 ExtensionRegistry 获取插件 resolver。

        Plugins register resolver functions via ExtensionRegistry.register_skill(plugin_name, ...)
        during enable; here we look up and call by source_plugin (plugin name).
        插件在 enable 时通过 ExtensionRegistry.register_skill(plugin_name, ...)
        注册了 resolver 函数，此处按 source_plugin（插件名）查找并调用。
        """
        from app.plugins.registry import ExtensionRegistry

        registry = ExtensionRegistry.get_instance()
        resolver_func = registry.get_plugin_skill_resolver(source_plugin)

        if resolver_func is None:
            logger.warning(
                "No plugin resolver for plugin '%s' (skill=%d, type=%s)",
                source_plugin, skill.id, skill.type,
            )
            return

        try:
            tool_defs = await resolver_func(skill, config) if asyncio.iscoroutinefunction(resolver_func) else resolver_func(skill, config)
            if isinstance(tool_defs, list):
                for td in tool_defs:
                    td.source_skill_id = skill.id
                    td.source_skill_name = skill.name
                    td.source_skill_type = skill.type
                    td.source_plugin = source_plugin
                    result.tools.append(td)
                logger.info(
                    "Plugin '%s' skill '%s' resolved %d tools",
                    source_plugin, skill.name, len(tool_defs),
                )
        except Exception as exc:
            logger.error(
                "Plugin skill resolver failed for '%s' (plugin=%s): %s",
                skill.name, source_plugin, exc,
            )

    # ========================================
    # Helper Methods / 辅助方法
    # ========================================

    @staticmethod
    def _build_unique_tool_name(
        base_name: str,
        suffix: str,
        used_names: set[str],
    ) -> str:
        """Build unique and length-controlled (OpenAI function name <= 64) tool name. / 构建唯一且长度可控（OpenAI function name <= 64）的工具名。"""
        max_len = 64
        available = max_len - len(suffix)
        short_base = base_name[:available] if available > 0 else ""
        candidate = f"{short_base}{suffix}" if short_base else suffix.strip("_")
        if not candidate:
            candidate = "tool"

        unique_name = candidate
        idx = 1
        while unique_name in used_names:
            extra = f"_{idx}"
            keep = max_len - len(extra)
            unique_name = f"{candidate[:keep]}{extra}" if keep > 0 else candidate
            idx += 1
        return unique_name

    @classmethod
    def _ensure_unique_tool_names(cls, tools: list[ToolDefinition]) -> None:
        """Deduplicate tool names to avoid parsing/authorization/attribution conflicts. / 去重工具名，避免同名工具导致解析/授权/归因冲突。"""
        used_names: set[str] = set()
        duplicate_counts: dict[str, int] = {}

        for td in tools:
            name = td.name
            if name not in used_names:
                used_names.add(name)
                duplicate_counts.setdefault(name, 1)
                continue

            duplicate_counts[name] = duplicate_counts.get(name, 1) + 1
            serial = duplicate_counts[name]
            suffix = (
                f"__s{td.source_skill_id}"
                if td.source_skill_id is not None
                else f"__dup{serial}"
            )
            unique_name = cls._build_unique_tool_name(name, suffix, used_names)
            logger.warning(
                "Duplicate tool name '%s' detected, renamed to '%s' (skill_id=%s)",
                name,
                unique_name,
                td.source_skill_id,
            )
            td.name = unique_name
            used_names.add(unique_name)

    @staticmethod
    def _build_params_from_schema(
        input_schema: dict[str, Any] | None,
    ) -> list[ToolParameter]:
        """
        Build ToolParameter list from JSON Schema.
        从 JSON Schema 构建 ToolParameter 列表。

        input_schema format / input_schema 格式：
        {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "City name / 城市名"},
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


def _audience_allows_role(target_audience: str, user_role: str | None) -> bool:
    """
    Check if the given target_audience allows access for the user_role.
    判断给定的 target_audience 是否允许该 user_role 访问。

    Args:
        target_audience: AudienceEnum value (all / admin_only / admin_tenant) /
                         AudienceEnum 值（all / admin_only / admin_tenant）
        user_role: UserRoleEnum value (platform_admin / tenant_admin / tenant_user) or None /
                   UserRoleEnum 值（platform_admin / tenant_admin / tenant_user）或 None

    Returns:
        True means access allowed, False means filtered out /
        True 表示允许访问，False 表示过滤掉
    """
    # No user_role passed (e.g., admin direct call) → allow (backward compatible)
    # 未传 user_role（如 admin 端直调）→ 允许通过（兼容旧路径）
    if user_role is None:
        return True

    if target_audience == AudienceEnum.ALL.value:
        return True

    if target_audience == AudienceEnum.ADMIN_TENANT.value:
        return user_role in (
            UserRoleEnum.PLATFORM_ADMIN.value,
            UserRoleEnum.TENANT_ADMIN.value,
        )

    if target_audience == AudienceEnum.ADMIN_ONLY.value:
        return user_role == UserRoleEnum.PLATFORM_ADMIN.value

    # Unknown value fallback: allow through / 未知值兖底：允许通过
    logger.warning("Unknown target_audience value: %s", target_audience)
    return True


async def _load_auto_bind_packages(
    db: AsyncSession,
    agent_scope: str,
    tenant_id: int | None,
    user_role: str | None = None,
) -> list:
    """
    Load bind_mode=auto skill packages filtered by target_audience.
    加载 bind_mode=auto 的自动绑定技能包，按 target_audience 过滤。

    Rules / 规则:
    - Admin call (tenant_id=None): load all auto packages (any target_audience)
      管理端调用：加载所有 auto 包
    - Tenant call: exclude target_audience=admin_only packages
      企业端调用：排除 admin_only 受众的包
    - user_role filter: further filter by target_audience (three-endpoint isolation)
      user_role 过滤：按三端隔离进一步筛选
    """
    from sqlalchemy import and_, select

    from app.enums.common import SkillBindModeEnum
    from app.models.ai.skill_package import SkillPackage

    base_conditions = [
        SkillPackage.bind_mode == SkillBindModeEnum.AUTO.value,
        SkillPackage.is_active.is_(True),
        SkillPackage.is_deleted.is_(False),
        SkillPackage.tenant_id.is_(None),
    ]

    if tenant_id is not None:
        if agent_scope == ResourceScopeEnum.ADMIN_ONLY.value:
            return []
        base_conditions.append(
            SkillPackage.target_audience != AudienceEnum.ADMIN_ONLY.value,
        )

    stmt = (
        select(SkillPackage)
        .where(and_(*base_conditions))
        .order_by(SkillPackage.sort_order)
    )

    result = await db.execute(stmt)
    packages = list(result.scalars().all())

    if user_role is not None:
        packages = [
            pkg for pkg in packages
            if _audience_allows_role(
                getattr(pkg, "target_audience", AudienceEnum.ALL.value),
                user_role,
            )
        ]

    return packages


async def resolve_for_agent(
    db: AsyncSession,
    agent: Any,
    tenant_id: int | None = None,
    user_role: str | None = None,
) -> SkillResolveResult | None:
    """
    Load and resolve all Skills bound to an Agent from AgentSkillBinding.

    Independent Skill resolution entry point for Dispatcher / Service layer.
    Engine no longer directly accesses AgentSkillBinding or Skill models.

    Error handling strategy:
    - DB connection / SQL errors → re-raise (caller can show "skill loading failed")
    - DB 连接 / SQL 错误 → 上抛（调用方可向用户显示“技能加载失败”）
    - Single Skill resolution error → degrade (skip that Skill, record in result.warnings)
    - 单个 Skill 解析错误 → 降级（跳过该 Skill，记录到 result.warnings）

    Args:
        db: Database session / 数据库会话
        agent: Agent model instance / Agent 模型实例
        tenant_id: Tenant ID (can be None for admin-level Agent) /
                   企业 ID（admin 级 Agent 可为 None）
        user_role: Caller role (UserRoleEnum value, for target_audience three-endpoint filtering).
                   Pass None to skip filtering (backward compatible, admin direct call).
                   调用方角色（UserRoleEnum 值，用于 target_audience 三端过滤）。
                   传 None 则跳过过滤（兼容旧路径，admin 端直调）。

    Returns:
        SkillResolveResult or None (when no bindings) /
        SkillResolveResult 或 None（无绑定时）

    Raises:
        sqlalchemy.exc.SQLAlchemyError: DB connection/query exception (no longer silently swallowed) /
        DB 连接/查询异常（不再静默吞掉）
    """
    from sqlalchemy import and_, select
    from sqlalchemy.exc import SQLAlchemyError

    from app.models.ai.agent_skill_binding import AgentSkillBinding
    from app.models.ai.skill import Skill as SkillModel
    from app.models.ai.skill_package import SkillPackage

    agent_tenant_id = tenant_id or getattr(agent, "tenant_id", None)
    agent_scope = getattr(agent, "scope", "all_tenants")

    # ── Phase 0 (NEW): Load auto-bind skill packages (bind_mode=auto) ──
    # 加载自动绑定技能包（bind_mode=auto）
    auto_packages: list[SkillPackage] = []
    try:
        auto_packages = await _load_auto_bind_packages(
            db, agent_scope, agent_tenant_id, user_role=user_role,
        )
    except SQLAlchemyError as exc:
        logger.warning(
            "Failed to load auto-bind packages for agent %d: %s",
            agent.id, str(exc),
        )
        # Degrade: auto-bind load failure doesn't block, continue with explicit bindings
        # 降级：auto-bind 加载失败不阻塞，继续使用 explicit bindings

    if auto_packages:
        logger.info(
            "Auto-bind: %d packages for agent=%s (scope=%s)",
            len(auto_packages),
            agent.name if agent else "?",
            agent_scope,
        )

    # ── Phase 1: Load explicit binding data (DB errors re-raised directly) ──
    # 绑定记录的 tenant_id 跟随 agent.tenant_id，而非调用方的 tenant_id
    # Binding tenant_id follows agent.tenant_id, not the caller's tenant_id
    binding_owner_tid = getattr(agent, "tenant_id", None)
    if binding_owner_tid is not None:
        binding_tenant_condition = AgentSkillBinding.tenant_id == binding_owner_tid
    else:
        binding_tenant_condition = AgentSkillBinding.tenant_id.is_(None)

    binding_stmt = (
        select(AgentSkillBinding)
        .where(
            and_(
                AgentSkillBinding.agent_id == agent.id,
                binding_tenant_condition,
                AgentSkillBinding.enabled.is_(True),
                AgentSkillBinding.is_deleted.is_(False),
            )
        )
        .order_by(AgentSkillBinding.sort_order)
    )

    try:
        binding_result = await db.execute(binding_stmt)
        bindings = list(binding_result.scalars().all())
    except SQLAlchemyError as exc:
        logger.error(
            "DB error loading skill bindings for agent %d: %s",
            agent.id, str(exc),
        )
        raise

    # ── Phase 1.5: Merge auto + explicit, deduplicate (explicit takes priority) ──
    # 合并 auto + explicit，去重（explicit 优先）
    # Explicit binding package_ids take priority (filtered by target_audience)
    # explicit binding 的 package_ids 优先（按 target_audience 过滤）
    explicit_package_ids: set[int] = set()
    for binding in bindings:
        if binding.package and binding.package.is_active and not binding.package.is_deleted:
            pkg_audience = getattr(
                binding.package, "target_audience", AudienceEnum.ALL.value
            )
            if not _audience_allows_role(pkg_audience, user_role):
                continue
            explicit_package_ids.add(binding.package.id)

    # If no explicit and no auto, return None
    # 如果没有 explicit 也没有 auto，返回 None
    if not bindings and not auto_packages:
        return None

    package_ids: list[int] = []
    config_overrides: dict[int, dict[str, Any]] = {}
    consent_by_package: dict[int, str] = {}

    # Add auto packages first (those not in explicit)
    # 先添加 auto 包（不在 explicit 中的）
    for pkg in auto_packages:
        if pkg.id not in explicit_package_ids:
            package_ids.append(pkg.id)
            consent_by_package[pkg.id] = "auto"  # auto 包默认 consent_mode=auto

    # Then add explicit packages / 再添加 explicit 包
    for binding in bindings:
        if binding.package and binding.package.is_active and not binding.package.is_deleted:
            package_ids.append(binding.package.id)
            if binding.config_override:
                config_overrides[binding.package.id] = binding.config_override
            consent_by_package[binding.package.id] = getattr(
                binding, "consent_mode", "auto"
            )

    if not package_ids:
        return None

    try:
        stmt = (
            select(SkillModel)
            .where(
                and_(
                    SkillModel.package_id.in_(package_ids),
                    SkillModel.is_active.is_(True),
                    SkillModel.is_deleted.is_(False),
                )
            )
            .order_by(SkillModel.sort_order)
        )
        result = await db.execute(stmt)
        skills = list(result.scalars().all())
    except SQLAlchemyError as exc:
        logger.error(
            "DB error loading skills for agent %d: %s",
            agent.id, str(exc),
        )
        raise

    if not skills:
        return None

    # ── Hook: BEFORE_SKILL_RESOLVE — plugins can inject/modify skills list ──
    # 插件可注入/修改 skills 列表
    hook_registry = get_hook_registry()
    if hook_registry.has_hooks(HookPoint.BEFORE_SKILL_RESOLVE):
        hook_ctx = await hook_registry.trigger(
            HookPoint.BEFORE_SKILL_RESOLVE,
            tenant_id=agent_tenant_id,
            agent_id=agent.id,
            skills=skills,
            skill_packages=package_ids,
        )
        skills = hook_ctx.get("skills", skills)

    # ── Phase 2: Resolve Skill → ToolDefinition (single failure degrades) ──
    # 解析 Skill → ToolDefinition（单个失败降级）
    skill_config_overrides: dict[int, dict[str, Any]] = {}
    pkg_valves: dict[int, dict[str, Any]] = {}
    # Load valves from auto-bind packages first
    for pkg in auto_packages:
        if pkg.id not in explicit_package_ids and getattr(pkg, "valves_config", None):
            pkg_valves[pkg.id] = pkg.valves_config
    # Then from explicit bindings (explicit overrides auto)
    for binding in bindings:
        if binding.package and binding.package.valves_config:
            pkg_valves[binding.package.id] = binding.package.valves_config

    for skill in skills:
        merged: dict[str, Any] = {}
        pkg_vc = pkg_valves.get(skill.package_id)
        if pkg_vc:
            merged["valves"] = pkg_vc
        pkg_override = config_overrides.get(skill.package_id)
        if pkg_override:
            merged.update(pkg_override)
        if merged:
            skill_config_overrides[skill.id] = merged

    resolver = SkillResolver(db=db)
    resolve_result = await resolver.resolve(skills, skill_config_overrides)
    # Note: resolver.resolve() internally catches per-skill errors and logs warnings.
    # Any warnings from individual skill resolution are already in resolve_result.warnings
    # via the try/except in SkillResolver._resolve_one → logged by resolver.

    # ── Phase 3: Map consent_mode and package_name (pure memory ops, should not fail) ──
    # 映射 consent_mode 和 package_name（纯内存操作，不应失败）
    # Build per-skill consent overrides from bindings
    skill_overrides_by_package: dict[int, dict[str, str]] = {}
    for binding in bindings:
        overrides = getattr(binding, "skill_consent_overrides", None)
        if overrides and isinstance(overrides, dict) and binding.package:
            skill_overrides_by_package[binding.package.id] = overrides

    consent_by_skill: dict[int, str] = {}
    package_name_by_skill: dict[int, str] = {}

    # Build package name lookup from both auto-bind and explicit sources
    _pkg_name_map: dict[int, str] = {}
    for pkg in auto_packages:
        if pkg.id not in explicit_package_ids:
            _pkg_name_map[pkg.id] = pkg.name
    for binding in bindings:
        if binding.package:
            _pkg_name_map[binding.package.id] = binding.package.name

    for skill in skills:
        # Default: package-level consent_mode
        pkg_consent = consent_by_package.get(skill.package_id, "auto")
        # Override: per-skill consent from skill_consent_overrides
        pkg_overrides = skill_overrides_by_package.get(skill.package_id, {})
        consent_by_skill[skill.id] = pkg_overrides.get(
            str(skill.id), pkg_consent
        )
        if skill.package_id in _pkg_name_map:
            package_name_by_skill[skill.id] = _pkg_name_map[skill.package_id]
    for tool in resolve_result.tools:
        if tool.source_skill_id and tool.source_skill_id in consent_by_skill:
            resolve_result.tool_consent_modes[tool.name] = consent_by_skill[
                tool.source_skill_id
            ]
        if tool.source_skill_id and tool.source_skill_id in package_name_by_skill:
            tool.source_package_name = package_name_by_skill[tool.source_skill_id]

    # ── Hook: AFTER_SKILL_RESOLVE — plugins can modify tool_definitions ──
    # 插件可修改 tool_definitions
    if hook_registry.has_hooks(HookPoint.AFTER_SKILL_RESOLVE):
        hook_ctx = await hook_registry.trigger(
            HookPoint.AFTER_SKILL_RESOLVE,
            tenant_id=agent_tenant_id,
            agent_id=agent.id,
            tool_definitions=resolve_result.tools,
        )
        resolve_result.tools = hook_ctx.get("tool_definitions", resolve_result.tools)

    logger.info(
        "Resolved skills for agent=%s: packages=%s, tools=%s, warnings=%d",
        agent.name if agent else "?",
        package_ids,
        [t.name for t in resolve_result.tools],
        len(resolve_result.warnings),
    )
    return resolve_result


__all__ = ["SkillResolver", "SkillResolveResult", "resolve_for_agent", "_audience_allows_role"]
