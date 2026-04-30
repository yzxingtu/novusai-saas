"""
Skill Resolver
Skill 解析器

Converts Skill models to ToolDefinition lists.
将 Skill 模型转换为 ToolDefinition 列表。

Conversion rules / 转换规则：
- toolkit → N ToolDefinitions (one per public method of Tools class)
- builtin → 1 ToolDefinition (or N, via config.tools list)

Knowledge base bindings have been migrated to AgentKnowledgeBaseBinding,
no longer resolved through Skill.
知识库绑定已迁移至 AgentKnowledgeBaseBinding 中间表，不再通过 Skill 解析。

Unknown types fall through to plugin resolver path.
未知类型走插件解析路径。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from app.ai.events.hooks import HookPoint, get_hook_registry
from app.ai.runtime.types import CapabilityDescriptor, collect_selected_skill_names
from app.ai.skills import resolver_parts as parts
from app.ai.skills.activation import TurnSkillActivation
from app.ai.tools.semantic_defaults import (
    is_retired_page_tool_name,
    tool_family_from_name,
)
from app.ai.tools.types import ToolDefinition, ToolParameter
from app.core.logging import LogManager

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.models.ai.skill import Skill

logger = LogManager.get_logger("ai.skill.resolver")

_BASELINE_RUNTIME_BUILTINS = parts.BASELINE_RUNTIME_BUILTINS
_WEB_RESEARCH_HINT_TOKENS = frozenset(
    {"research", "search", "web", "fetch", "url", "crawl", "browse"}
)
_RUNTIME_BUILTIN_TOOL_NAMES = frozenset(_BASELINE_RUNTIME_BUILTINS)


def _stable_unique_texts(values: list[Any]) -> list[str]:
    normalized: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if text and text not in normalized:
            normalized.append(text)
    return normalized


def _normalized_match_text(value: Any) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _remove_retired_page_tools(result: Any) -> None:
    tools = list(getattr(result, "tools", []) or [])
    result.tools = [
        tool
        for tool in tools
        if not is_retired_page_tool_name(getattr(tool, "name", None))
    ]
    if hasattr(result, "tool_consent_modes"):
        result.tool_consent_modes = {
            name: mode
            for name, mode in dict(
                getattr(result, "tool_consent_modes", {}) or {}
            ).items()
            if not is_retired_page_tool_name(name)
        }


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
    capability_descriptors: list[CapabilityDescriptor] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    turn_activation: TurnSkillActivation | None = None
    inventory_selected_tool_names_override: list[str] | None = None
    inventory_selected_skill_names_override: list[str] | None = None

    @property
    def inventory_selected_tool_names(self) -> list[str]:
        if self.inventory_selected_tool_names_override is not None:
            return list(self.inventory_selected_tool_names_override)
        return [
            str(getattr(tool, "name", "") or "").strip()
            for tool in self.tools
            if str(getattr(tool, "name", "") or "").strip()
        ]

    @property
    def inventory_selected_skill_names(self) -> list[str]:
        if self.inventory_selected_skill_names_override is not None:
            return list(self.inventory_selected_skill_names_override)
        return collect_selected_skill_names(
            descriptors=self.capability_descriptors,
            tools=self.tools,
        )

    @property
    def selected_skill_names(self) -> list[str]:
        activation = self.turn_activation
        if activation is not None and activation.applied:
            return list(activation.activated_skill_names or [])
        return self.inventory_selected_skill_names

    @property
    def selected_tool_names(self) -> list[str]:
        activation = self.turn_activation
        if activation is not None and activation.applied:
            return list(activation.activated_tool_names or [])
        return self.inventory_selected_tool_names


@dataclass(frozen=True)
class SkillGrantPreview:
    grant: Any
    skill: Any
    merged_config: dict[str, Any]
    package_name: str
    source_plugin: str
    preview_tool_names: list[str] = field(default_factory=list)
    preview_semantic_families: list[str] = field(default_factory=list)


def build_skill_capability_descriptors(skills: list[Any]) -> list[CapabilityDescriptor]:
    return parts.build_skill_capability_descriptors(skills)


def enrich_skill_capability_descriptors_with_tools(
    *,
    descriptors: list[CapabilityDescriptor],
    tools: list[ToolDefinition],
) -> None:
    parts.enrich_skill_capability_descriptors_with_tools(
        descriptors=descriptors,
        tools=tools,
    )


def _is_runtime_eligible_skill(skill: Any) -> bool:
    return parts.is_runtime_eligible_skill(skill)


def _build_time_only_runtime_result() -> SkillResolveResult:
    return parts.build_time_only_runtime_result(
        result_factory=SkillResolveResult,
        apply_tool_semantics=SkillResolver._apply_tool_semantics,
    )


def _merged_grant_skill_config(grant: Any) -> dict[str, Any]:
    skill = getattr(grant, "skill", None)
    if skill is None:
        return {}

    merged_config = dict(getattr(skill, "config", None) or {})
    package = getattr(skill, "package", None)
    if package is not None and getattr(package, "valves_config", None):
        merged_config["valves"] = package.valves_config
    if getattr(grant, "config_override", None):
        merged_config.update(grant.config_override)
    return merged_config


def _preview_tool_names_for_skill(
    *,
    skill: Any,
    config: dict[str, Any],
    source_plugin: str,
) -> list[str]:
    if bool(config.get("internal")):
        return []
    if source_plugin:
        return []

    skill_type = str(getattr(skill, "type", "") or "").strip()
    if skill_type == "toolkit":
        toolkit_content = str(getattr(skill, "toolkit_content", "") or "").strip()
        if not toolkit_content:
            return []
        try:
            from app.ai.skills.toolkit_parser import parse_toolkit

            meta = parse_toolkit(toolkit_content)
        except Exception as exc:  # pragma: no cover - defensive degradation
            logger.warning(
                "Startup skill preview degraded for toolkit skill {} ({}): {}",
                getattr(skill, "id", None),
                getattr(skill, "name", None),
                str(exc),
            )
            return []
        return [
            str(getattr(tool_meta, "name", "") or "").strip()
            for tool_meta in list(getattr(meta, "tools", []) or [])
            if str(getattr(tool_meta, "name", "") or "").strip()
        ]
    if skill_type == "builtin":
        tools_config = config.get("tools")
        if isinstance(tools_config, list):
            return [
                str((tool_cfg or {}).get("name") or "").strip()
                for tool_cfg in tools_config
                if str((tool_cfg or {}).get("name") or "").strip()
                and str((tool_cfg or {}).get("name") or "").strip()
                not in _RUNTIME_BUILTIN_TOOL_NAMES
            ]
        tool_name = str(getattr(skill, "name", "") or "").strip()
        if tool_name in _RUNTIME_BUILTIN_TOOL_NAMES:
            return []
        return [tool_name] if tool_name else []
    if skill_type == "http":
        tool_name = str(getattr(skill, "name", "") or "").strip().lower()
        tool_name = tool_name.replace(" ", "_")
        return [tool_name] if tool_name else []
    if skill_type == "email":
        return ["send_email"]
    if skill_type == "code_execution":
        return ["execute_code"]
    return []


def _semantic_hint_tokens(*values: Any) -> set[str]:
    tokens: set[str] = set()
    for value in values:
        normalized = re.sub(r"[^a-z0-9]+", " ", str(value or "").lower())
        tokens.update(token for token in normalized.split() if token)
    return tokens


def _preview_semantic_families_for_skill(
    *,
    skill: Any,
    package_name: str,
    source_plugin: str,
    preview_tool_names: list[str],
    preview_semantic_families: list[str] | None = None,
    extra_hint_values: list[str] | None = None,
) -> list[str]:
    families = [
        family
        for family in _stable_unique_texts(list(preview_semantic_families or []))
        if family != "page_ops"
    ]
    for tool_name in preview_tool_names:
        family = tool_family_from_name(str(tool_name or "").strip())
        if family != "none" and family not in families:
            families.append(family)

    hint_tokens = _semantic_hint_tokens(
        getattr(skill, "name", None),
        package_name,
        source_plugin,
        *(extra_hint_values or []),
    )
    if hint_tokens & _WEB_RESEARCH_HINT_TOKENS and "web_research" not in families:
        families.append("web_research")
    return families


def _match_plugin_startup_preview(
    *,
    skill: Any,
    plugin_skill_previews: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    previews = list(plugin_skill_previews or [])
    if not previews:
        return {}

    skill_name = _normalized_match_text(getattr(skill, "name", None))
    skill_type = str(getattr(skill, "type", "") or "").strip()

    named_same_type = [
        preview
        for preview in previews
        if skill_name
        and skill_name
        in {
            _normalized_match_text(candidate)
            for candidate in list(preview.get("candidate_names") or [])
        }
        and str(preview.get("type") or "").strip() == skill_type
    ]
    if len(named_same_type) == 1:
        return named_same_type[0]

    named_matches = [
        preview
        for preview in previews
        if skill_name
        and skill_name
        in {
            _normalized_match_text(candidate)
            for candidate in list(preview.get("candidate_names") or [])
        }
    ]
    if len(named_matches) == 1:
        return named_matches[0]

    same_type = [
        preview
        for preview in previews
        if str(preview.get("type") or "").strip() == skill_type
    ]
    if len(same_type) == 1:
        return same_type[0]

    if len(previews) == 1:
        return previews[0]
    return {}


def _build_skill_grant_previews(
    grants: list[Any],
    *,
    plugin_skill_previews_by_plugin: dict[str, list[dict[str, Any]]] | None = None,
) -> list[SkillGrantPreview]:
    previews: list[SkillGrantPreview] = []
    for grant in grants:
        skill = getattr(grant, "skill", None)
        if not _is_runtime_eligible_skill(skill):
            continue
        merged_config = _merged_grant_skill_config(grant)
        package = getattr(skill, "package", None)
        package_name = str(getattr(package, "name", "") or "").strip()
        source_plugin = str(getattr(package, "source_plugin", "") or "").strip()
        manifest_preview = _match_plugin_startup_preview(
            skill=skill,
            plugin_skill_previews=(plugin_skill_previews_by_plugin or {}).get(
                source_plugin, []
            ),
        )
        preview_tool_names = _stable_unique_texts(
            list(manifest_preview.get("preview_tool_names") or [])
            + _preview_tool_names_for_skill(
                skill=skill,
                config=merged_config,
                source_plugin=source_plugin,
            )
        )
        preview_semantic_families = _preview_semantic_families_for_skill(
            skill=skill,
            package_name=package_name,
            source_plugin=source_plugin,
            preview_tool_names=preview_tool_names,
            preview_semantic_families=list(
                manifest_preview.get("preview_semantic_families") or []
            ),
            extra_hint_values=_stable_unique_texts(
                list(manifest_preview.get("candidate_names") or [])
                + [
                    manifest_preview.get("entry_point"),
                    manifest_preview.get("description"),
                ]
            ),
        )
        previews.append(
            SkillGrantPreview(
                grant=grant,
                skill=skill,
                merged_config=merged_config,
                package_name=package_name,
                source_plugin=source_plugin,
                preview_tool_names=preview_tool_names,
                preview_semantic_families=preview_semantic_families,
            )
        )
    return previews


def _build_startup_preview_result(
    grant_previews: list[SkillGrantPreview],
) -> SkillResolveResult:
    preview_tools: list[ToolDefinition] = []
    for preview in grant_previews:
        for tool_name in preview.preview_tool_names:
            preview_tools.append(
                ToolDefinition(
                    name=tool_name,
                    source_skill_id=getattr(preview.skill, "id", None),
                    source_skill_name=str(
                        getattr(preview.skill, "name", "") or ""
                    ).strip()
                    or None,
                    source_skill_type=getattr(preview.skill, "type", None),
                    source_package_name=preview.package_name or None,
                    source_plugin=preview.source_plugin or None,
                )
            )
    preview_descriptors = build_skill_capability_descriptors(
        [preview.skill for preview in grant_previews]
    )
    enrich_skill_capability_descriptors_with_tools(
        descriptors=preview_descriptors,
        tools=preview_tools,
    )
    preview_families_by_skill_id = {
        getattr(preview.skill, "id", None): list(
            preview.preview_semantic_families or []
        )
        for preview in grant_previews
    }
    for descriptor in preview_descriptors:
        metadata = dict(getattr(descriptor, "metadata", {}) or {})
        preview_families = preview_families_by_skill_id.get(
            metadata.get("skill_id"), []
        )
        if not preview_families:
            continue
        descriptor.metadata = {
            **metadata,
            "preview_semantic_families": list(preview_families),
        }
    return SkillResolveResult(
        tools=preview_tools,
        capability_descriptors=preview_descriptors,
    )


def _apply_catalog_preview_metadata(
    *,
    descriptors: list[CapabilityDescriptor],
    grant_previews: list[SkillGrantPreview],
) -> None:
    preview_by_skill_id = {
        getattr(preview.skill, "id", None): preview for preview in grant_previews
    }
    for descriptor in descriptors:
        metadata = dict(getattr(descriptor, "metadata", {}) or {})
        preview = preview_by_skill_id.get(metadata.get("skill_id"))
        if preview is None:
            continue

        preview_tool_names = _stable_unique_texts(
            list(preview.preview_tool_names or [])
        )
        preview_semantic_families = _stable_unique_texts(
            list(preview.preview_semantic_families or [])
        )
        if not preview_tool_names and not preview_semantic_families:
            continue

        descriptor.metadata = {
            **metadata,
            "startup_preview_tool_names": preview_tool_names,
            "startup_preview_semantic_families": preview_semantic_families,
        }


def _filter_grant_previews_for_turn_startup(
    grant_previews: list[SkillGrantPreview],
    *,
    request: Any | None,
) -> list[SkillGrantPreview]:
    if request is None or not grant_previews:
        return grant_previews

    from app.ai.skills.activation import (
        apply_turn_skill_activation,
        resolve_startup_intent_flags,
    )

    preview_result = _build_startup_preview_result(grant_previews)
    startup_intent_flags = resolve_startup_intent_flags(request)
    apply_turn_skill_activation(
        skill_result=preview_result,
        request=request,
        intent_flags=startup_intent_flags,
        allow_catalog_skill_activation=True,
    )
    activation = getattr(preview_result, "turn_activation", None)
    if activation is None or not activation.applied:
        return grant_previews
    if activation.reason in {"capability_reporting_query", "no_turn_skill_activation"}:
        return grant_previews

    activated_skill_names = {
        str(name or "").strip()
        for name in activation.activated_skill_names or []
        if str(name or "").strip()
    }
    activated_tool_names = {
        str(name or "").strip()
        for name in activation.activated_tool_names or []
        if str(name or "").strip()
    }
    if not activated_skill_names and not activated_tool_names:
        return grant_previews

    filtered = [
        preview
        for preview in grant_previews
        if str(getattr(preview.skill, "name", "") or "").strip()
        in activated_skill_names
        or bool(activated_tool_names & set(preview.preview_tool_names or []))
    ]
    return filtered or grant_previews


class SkillResolver:
    """
    Skill → ToolDefinition converter / Skill → ToolDefinition 转换器。

    Dispatches to corresponding conversion method by Skill type.
    A single Skill may produce 0~N ToolDefinitions.
    按 Skill 类型分发到对应的转换方法。
    一个 Skill 可能产生 0~N 个 ToolDefinition。
    """

    def __init__(self, db: AsyncSession | None = None):
        self.db = db

    @staticmethod
    def _semantic_tags(*values: str) -> list[str]:
        return parts.semantic_tags(*values)

    @classmethod
    def _apply_tool_semantics(
        cls,
        tool: ToolDefinition,
    ) -> None:
        parts.apply_tool_semantics(tool)

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
            if not _is_runtime_eligible_skill(skill):
                continue

            # Skip DB-based builtin skills that duplicate baseline runtime builtins
            # 跳过与基线运行时内置工具重复的数据库内置技能
            if (
                str(getattr(skill, "type", "") or "").strip() == "builtin"
                and str(getattr(skill, "name", "") or "").strip()
                in _RUNTIME_BUILTIN_TOOL_NAMES
            ):
                logger.debug(
                    "Skipping DB builtin skill '{}' (id={}) — covered by runtime builtins",
                    skill.name,
                    skill.id,
                )
                continue

            # Merge config: Skill.config + binding.config_override
            # 合并配置：Skill.config + binding.config_override
            merged_config = dict(skill.config or {})
            if skill.id in overrides and overrides[skill.id]:
                merged_config.update(overrides[skill.id])

            source_plugin = plugin_map.get(skill.package_id)
            before_count = len(result.tools)

            try:
                await self._resolve_one(skill, merged_config, result, source_plugin)
                for tool in result.tools[before_count:]:
                    self._apply_tool_semantics(tool)
            except Exception as exc:
                warning_msg = (
                    f"Skill '{skill.name}' (id={skill.id}) failed to load: {str(exc)}"
                )
                result.warnings.append(warning_msg)
                logger.warning(
                    "Failed to resolve skill {} ({}): {}",
                    skill.id,
                    skill.name,
                    str(exc),
                )

        # Prevent tool name duplicates causing execution and consent attribution mismatch
        # 避免工具重名导致执行与 consent 归因错配
        self._ensure_unique_tool_names(result.tools)
        _remove_retired_page_tools(result)

        logger.info(
            "Resolved {} skills → {} tools",
            len(skills),
            len(result.tools),
        )
        return result

    async def _load_source_plugins(
        self,
        skills: list[Skill],
    ) -> dict[int, str]:
        return await parts.load_source_plugins(db=self.db, skills=skills)

    async def _resolve_one(
        self,
        skill: Skill,
        config: dict[str, Any],
        result: SkillResolveResult,
        source_plugin: str | None = None,
    ) -> None:
        await parts.resolve_one_skill(
            skill=skill,
            config=config,
            result=result,
            source_plugin=source_plugin,
            resolve_toolkit=self._resolve_toolkit,
            resolve_builtin=self._resolve_builtin,
            resolve_http=self._resolve_http,
            resolve_email=self._resolve_email,
            resolve_code_execution=self._resolve_code_execution,
            resolve_plugin=self._resolve_plugin_skill,
        )

    # ============================================
    # Toolkit Skill / Toolkit 技能
    # ============================================

    def _resolve_toolkit(
        self,
        skill: Skill,
        config: dict[str, Any],
        result: SkillResolveResult,
    ) -> None:
        parts.resolve_toolkit_skill(
            skill=skill,
            config=config,
            result=result,
        )

    # ============================================
    # Builtin Skill / 内置技能
    # ============================================

    @staticmethod
    def _augment_builtin_tool_description(
        tool_name: str,
        description: str,
    ) -> str:
        return parts.augment_builtin_tool_description(tool_name, description)

    @classmethod
    def _build_baseline_builtin_tool(
        cls,
        tool_name: str,
    ) -> ToolDefinition | None:
        return parts.build_baseline_builtin_tool(
            tool_name=tool_name,
            apply_tool_semantics=cls._apply_tool_semantics,
        )

    @classmethod
    def _inject_baseline_runtime_builtins(
        cls,
        result: SkillResolveResult,
    ) -> None:
        parts.inject_baseline_runtime_builtins(
            result=result,
            apply_tool_semantics=cls._apply_tool_semantics,
        )

    @classmethod
    def _build_time_only_runtime_result(cls) -> SkillResolveResult:
        return _build_time_only_runtime_result()

    def _resolve_builtin(
        self,
        skill: Skill,
        config: dict[str, Any],
        result: SkillResolveResult,
    ) -> None:
        parts.resolve_builtin(
            skill=skill,
            config=config,
            result=result,
            build_params_from_schema=self._build_params_from_schema,
        )

    # ============================================
    # HTTP/Webhook Skill / HTTP 与 Webhook 技能
    # ============================================

    def _resolve_http(
        self,
        skill: Skill,
        config: dict[str, Any],
        result: SkillResolveResult,
    ) -> None:
        parts.resolve_http_skill(
            skill=skill,
            config=config,
            result=result,
        )

    # ============================================
    # Email Skill / 邮件技能
    # ============================================

    def _resolve_email(
        self,
        skill: Skill,
        config: dict[str, Any],
        result: SkillResolveResult,
    ) -> None:
        parts.resolve_email_skill(
            skill=skill,
            config=config,
            result=result,
        )

    # ============================================
    # Code Execution Skill / 代码执行技能
    # ============================================

    def _resolve_code_execution(
        self,
        skill: Skill,
        config: dict[str, Any],
        result: SkillResolveResult,
    ) -> None:
        parts.resolve_code_execution_skill(
            skill=skill,
            config=config,
            result=result,
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
    ) -> bool:
        return await parts.resolve_plugin_skill(
            skill=skill,
            config=config,
            result=result,
            source_plugin=source_plugin,
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
        return parts.build_unique_tool_name(base_name, suffix, used_names)

    @classmethod
    def _ensure_unique_tool_names(cls, tools: list[ToolDefinition]) -> None:
        parts.ensure_unique_tool_names(tools)

    @staticmethod
    def _build_params_from_schema(
        input_schema: dict[str, Any] | None,
    ) -> list[ToolParameter]:
        return parts.build_params_from_schema(input_schema)


async def resolve_for_agent(
    db: AsyncSession,
    agent: Any,
    tenant_id: int | None = None,
    user_role: str | None = None,
    request: Any | None = None,
) -> SkillResolveResult | None:
    """
    Load and resolve all Skills granted to an Agent from AgentSkillGrant.

    Independent Skill resolution entry point for Dispatcher / Service layer.

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
        user_role: Reserved caller role context (kept for compatibility).
                   预留的调用方角色上下文（为兼容性保留）。

    Returns:
        SkillResolveResult or None (when bindings are filtered out as ineligible) /
        SkillResolveResult 或 None（绑定被过滤为运行时不可用时）

    Raises:
        sqlalchemy.exc.SQLAlchemyError: DB connection/query exception (no longer silently swallowed) /
        DB 连接/查询异常（不再静默吞掉）
    """
    from sqlalchemy import and_, select
    from sqlalchemy.exc import SQLAlchemyError
    from sqlalchemy.orm import selectinload

    from app.models.ai.agent_skill_grant import AgentSkillGrant
    from app.models.ai.skill import Skill as SkillModel

    del user_role

    # tenant_id may be PLATFORM_TENANT_ID (0); must not treat 0 as falsy / 0 为合法平台租户 ID，不可当假值
    if tenant_id is not None:
        agent_tenant_id: int | None = tenant_id
    else:
        agent_tenant_id = getattr(agent, "owner_tenant_id", None)

    grant_owner_tid = getattr(agent, "owner_tenant_id", None)
    if grant_owner_tid is not None:
        grant_tenant_condition = AgentSkillGrant.tenant_id == grant_owner_tid
    else:
        grant_tenant_condition = AgentSkillGrant.tenant_id.is_(None)

    grant_stmt = (
        select(AgentSkillGrant)
        .options(
            selectinload(AgentSkillGrant.skill).selectinload(SkillModel.package),
        )
        .where(
            and_(
                AgentSkillGrant.agent_id == agent.id,
                grant_tenant_condition,
                AgentSkillGrant.enabled.is_(True),
                AgentSkillGrant.is_deleted.is_(False),
            )
        )
        .order_by(AgentSkillGrant.sort_order)
    )

    try:
        grant_result = await db.execute(grant_stmt)
        grants = list(grant_result.scalars().all())
    except SQLAlchemyError as exc:
        logger.error(
            "DB error loading skill grants for agent {}: {}",
            agent.id,
            str(exc),
        )
        raise

    if not grants:
        return _build_time_only_runtime_result()

    plugin_skill_previews_by_plugin = await parts.load_plugin_skill_startup_previews(
        db=db,
        source_plugins=[
            str(
                getattr(getattr(grant.skill, "package", None), "source_plugin", "")
                or ""
            ).strip()
            for grant in grants
            if str(
                getattr(getattr(grant.skill, "package", None), "source_plugin", "")
                or ""
            ).strip()
        ],
    )
    grant_previews = _build_skill_grant_previews(
        grants,
        plugin_skill_previews_by_plugin=plugin_skill_previews_by_plugin,
    )
    startup_grant_previews = _filter_grant_previews_for_turn_startup(
        grant_previews,
        request=request,
    )
    if startup_grant_previews is not grant_previews:
        logger.info(
            "Startup skill prefilter applied for agent={}: grants={} -> {}",
            getattr(agent, "id", None),
            len(grant_previews),
            len(startup_grant_previews),
        )

    skills: list[SkillModel] = []
    skill_config_overrides: dict[int, dict[str, Any]] = {}
    package_name_by_skill: dict[int, str] = {}

    for preview in startup_grant_previews:
        skill = preview.skill
        skills.append(skill)
        if preview.package_name:
            package_name_by_skill[skill.id] = preview.package_name
        if preview.merged_config:
            skill_config_overrides[skill.id] = dict(preview.merged_config)

    if not skills:
        return _build_time_only_runtime_result()

    hook_registry = get_hook_registry()
    if hook_registry.has_hooks(HookPoint.BEFORE_SKILL_RESOLVE):
        hook_ctx = await hook_registry.trigger(
            HookPoint.BEFORE_SKILL_RESOLVE,
            tenant_id=agent_tenant_id,
            agent_id=agent.id,
            skills=skills,
            skill_ids=[skill.id for skill in skills],
            skill_packages=[skill.package_id for skill in skills if skill.package_id],
        )
        skills = hook_ctx.get("skills", skills)

    resolver = SkillResolver(db=db)
    resolve_result = await resolver.resolve(skills, skill_config_overrides)
    resolve_result.capability_descriptors = build_skill_capability_descriptors(skills)
    _apply_catalog_preview_metadata(
        descriptors=resolve_result.capability_descriptors,
        grant_previews=startup_grant_previews,
    )

    for tool in resolve_result.tools:
        skill_id = tool.source_skill_id
        if not skill_id:
            continue
        resolve_result.tool_consent_modes[tool.name] = "auto"
        if skill_id in package_name_by_skill:
            tool.source_package_name = package_name_by_skill[skill_id]

    resolver._inject_baseline_runtime_builtins(resolve_result)

    if hook_registry.has_hooks(HookPoint.AFTER_SKILL_RESOLVE):
        hook_ctx = await hook_registry.trigger(
            HookPoint.AFTER_SKILL_RESOLVE,
            tenant_id=agent_tenant_id,
            agent_id=agent.id,
            tool_definitions=resolve_result.tools,
        )
        resolve_result.tools = hook_ctx.get("tool_definitions", resolve_result.tools)
    _remove_retired_page_tools(resolve_result)
    enrich_skill_capability_descriptors_with_tools(
        descriptors=resolve_result.capability_descriptors,
        tools=resolve_result.tools,
    )

    logger.info(
        "Resolved skills for agent={}: skill_ids={}, tools={}, warnings={}",
        getattr(agent, "name", None) or "?",
        [skill.id for skill in skills],
        [t.name for t in resolve_result.tools],
        len(resolve_result.warnings),
    )
    return resolve_result


__all__ = [
    "SkillResolver",
    "SkillResolveResult",
    "build_skill_capability_descriptors",
    "enrich_skill_capability_descriptors_with_tools",
    "resolve_for_agent",
]
