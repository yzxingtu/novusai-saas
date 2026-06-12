"""
System agent seed service.

Implements the admin bootstrap/status flow for built-in Copilot agents.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import text

from app.core.i18n import _
from app.enums.agent import (
    AgentExecutionModeEnum,
    AgentStatusEnum,
    AgentVisibilityEnum,
    ToolConsentModeEnum,
)
from app.enums.common import ResourceScopeEnum
from app.enums.skill import SkillSourceTypeEnum, SkillStatusEnum
from app.exceptions import BusinessException
from app.models.ai import (
    Agent,
    AgentSkillGrant,
    AIModel,
    AIProvider,
    Skill,
    SkillPackage,
)
from app.models.system.agent_assignment import SystemAgentAssignment
from app.repositories.system.system_agent_seed_repository import (
    SystemAgentSeedRepository,
)

SKILL_PACKAGE_NAME = "运营 Copilot 技能包"
SKILL_KEY = "internal_operations"
SKILL_NAME = "内部操作元工具"

CONTEXT_SKILL_PACKAGE_NAME = "智能体上下文技能包（内置）"
CONTEXT_KB_SKILL_KEY = "agent_context_knowledge_search"
CONTEXT_KB_SKILL_NAME = "知识库检索工具"
CONTEXT_MEMORY_SKILL_KEY = "agent_context_memory_tools"
CONTEXT_MEMORY_SKILL_NAME = "长期记忆读写工具"

ADMIN_COPILOT_NAME = "平台运营 Copilot"
TENANT_COPILOT_NAME = "企业运营 Copilot"

ADMIN_COPILOT_FEATURE = "admin_copilot"
TENANT_COPILOT_FEATURE = "tenant_copilot"

SYSTEM_AGENT_SEED_LOCK_KEY = 804_251_008_008

COPILOT_SYSTEM_PROMPT = """\
你是 NovusAI 平台的运营 Copilot，能够代表当前用户执行后台管理操作。

## 可用工具

你拥有三个元工具，可以发现并调用本系统的全部后台操作：
1. `list_internal_operations` — 按关键词搜索当前用户可用的后台操作目录
2. `describe_internal_operation` — 查看某个操作的完整参数规格
3. `invoke_internal_operation` — 以当前用户的身份执行操作

## 工作流程（必须遵守）

1. 理解用户意图后，先用 `list_internal_operations` 搜索相关操作；关键词可以是中文或英文，匹配路径、模块、摘要和权限码。
2. 找到候选操作后，调用 `describe_internal_operation` 查看参数规格，严格按 schema 构造参数。
3. 调用 `invoke_internal_operation` 执行：
   - 查询（GET）操作会立即执行；
   - 写操作（POST/PUT/PATCH/DELETE）会先返回确认预览，由用户在界面上确认后才真正执行。在确认结果返回前，绝不能声称操作已完成。
4. 把执行结果用简洁的中文向用户汇报，重要数据用表格或列表呈现。

## 安全规则

- 你的权限与当前用户完全一致：返回 403 表示用户本人无此权限，应如实告知，不要重试。
- 绝不虚构 operation_id 或参数；不确定时先搜索、先查看规格。
- 写操作前应向用户复述将要执行的内容；用户明确拒绝时立即终止。
- 涉及删除等高危操作时，提醒用户操作后果。

## 回复风格

- 始终使用简体中文。
- 简明扼要，先给结论再给细节。
- 操作失败时解释原因并给出下一步建议。\
"""

ADMIN_COPILOT_DESCRIPTION = (
    "平台运营 Copilot — 通过对话完成平台后台的查询与管理操作"
    "（租户、套餐、用户、权限、配置、日志等）"
)
TENANT_COPILOT_DESCRIPTION = (
    "企业运营 Copilot — 通过对话完成企业后台的查询与管理操作"
    "（成员、组织、角色、智能体、知识库等）"
)


@dataclass(frozen=True)
class SystemAgentSeedFeature:
    feature_code: str
    feature_name: str
    required_scope: str
    agent_name: str
    agent_description: str


SYSTEM_AGENT_FEATURES: tuple[SystemAgentSeedFeature, ...] = (
    SystemAgentSeedFeature(
        feature_code=ADMIN_COPILOT_FEATURE,
        feature_name="平台运营 Copilot",
        required_scope=ResourceScopeEnum.ADMIN_ONLY.value,
        agent_name=ADMIN_COPILOT_NAME,
        agent_description=ADMIN_COPILOT_DESCRIPTION,
    ),
    SystemAgentSeedFeature(
        feature_code=TENANT_COPILOT_FEATURE,
        feature_name="企业运营 Copilot",
        required_scope=ResourceScopeEnum.ALL_TENANTS.value,
        agent_name=TENANT_COPILOT_NAME,
        agent_description=TENANT_COPILOT_DESCRIPTION,
    ),
)


class SystemAgentSeedService:
    """Service that reports and repairs the built-in Copilot bootstrap state."""

    def __init__(self, db):
        self.db = db
        self.repo = SystemAgentSeedRepository(db)

    def _serialize_provider(self, provider: AIProvider | None) -> dict[str, Any] | None:
        if provider is None:
            return None
        return {
            "id": provider.id,
            "name": provider.name,
            "code": provider.code,
            "is_active": provider.is_active,
            "sort_order": provider.sort_order,
        }

    def _serialize_model(self, model: AIModel | None) -> dict[str, Any] | None:
        if model is None:
            return None
        provider = getattr(model, "provider", None)
        return {
            "id": model.id,
            "name": model.name,
            "code": model.code,
            "type": model.type,
            "provider_id": model.provider_id,
            "provider_name": getattr(provider, "name", None),
            "provider_code": getattr(provider, "code", None),
            "is_active": model.is_active,
            "status": "ready" if model.is_active and not model.is_deleted else "inactive",
        }

    def _serialize_agent(self, agent: Agent | None) -> dict[str, Any] | None:
        if agent is None:
            return None
        return {
            "id": agent.id,
            "name": agent.name,
            "scope": agent.scope,
            "status": agent.status,
            "owner_tenant_id": agent.owner_tenant_id,
            "is_system": agent.is_system,
            "is_deleted": agent.is_deleted,
            "model_id": agent.model_id,
        }

    async def _is_agent_runtime_ready(self, agent: Agent | None) -> bool:
        if agent is None:
            return False
        model_id = getattr(agent, "model_id", None)
        if model_id is None:
            return False
        model = await self.repo.get_ready_chat_model_with_active_provider(model_id)
        return model is not None

    async def _serialize_assignment(
        self,
        feature: SystemAgentSeedFeature,
        assignment: SystemAgentAssignment | None,
    ) -> dict[str, Any]:
        if assignment is None:
            return {
                "feature_code": feature.feature_code,
                "feature_name": feature.feature_name,
                "required_scope": feature.required_scope,
                "assignment_exists": False,
                "assignment_id": None,
                "assignment_active": False,
                "assignment_deleted": False,
                "agent_id": None,
                "agent_name": None,
                "agent_scope": None,
                "agent_status": None,
                "agent_is_system": None,
                "state": "missing_assignment",
                "repairable": True,
                "preserve_custom_assignment": False,
            }

        agent = getattr(assignment, "agent", None)
        agent_exists = agent is not None and not getattr(agent, "is_deleted", False)
        agent_scope = getattr(agent, "scope", None)
        agent_status = getattr(agent, "status", None)
        agent_is_system = getattr(agent, "is_system", None)
        assignment_active = bool(getattr(assignment, "is_active", False))
        assignment_deleted = bool(getattr(assignment, "is_deleted", False))
        agent_runtime_ready = await self._is_agent_runtime_ready(agent)

        target_valid = (
            agent_exists
            and getattr(agent, "owner_tenant_id", None) is None
            and agent_status == AgentStatusEnum.PUBLISHED.value
            and agent_scope == feature.required_scope
            and agent_runtime_ready
        )

        preserve_custom_assignment = (
            target_valid
            and not bool(agent_is_system)
            and assignment_active
            and not assignment_deleted
        )

        if assignment_deleted:
            state = "inactive_assignment"
            repairable = True
        elif not getattr(assignment, "agent_id", None):
            state = "missing_agent"
            repairable = True
        elif not target_valid:
            state = "bad_agent"
            repairable = True
        elif not assignment_active:
            state = "inactive_assignment"
            repairable = True
        elif bool(agent_is_system):
            state = "ready"
            repairable = False
        else:
            state = "custom_ready"
            repairable = False

        return {
            "feature_code": feature.feature_code,
            "feature_name": feature.feature_name,
            "required_scope": feature.required_scope,
            "assignment_exists": True,
            "assignment_id": assignment.id,
            "assignment_active": assignment_active,
            "assignment_deleted": assignment_deleted,
            "agent_id": getattr(assignment, "agent_id", None),
            "agent_name": getattr(agent, "name", None),
            "agent_scope": agent_scope,
            "agent_status": agent_status,
            "agent_is_system": agent_is_system,
            "state": state,
            "repairable": repairable,
            "preserve_custom_assignment": preserve_custom_assignment,
        }

    async def _ensure_skill_package(self) -> SkillPackage:
        package = await self.repo.get_platform_system_skill_package_by_name(
            SKILL_PACKAGE_NAME,
            include_deleted=True,
        )
        if package is None:
            package = await self.repo.create_skill_package(
                {
                    "tenant_id": None,
                    "name": SKILL_PACKAGE_NAME,
                    "description": "内置运营 Copilot 的内部操作元工具（list/describe/invoke）",
                    "avatar": None,
                    "is_recommended": False,
                    "source_plugin": None,
                    "is_system": True,
                    "valves_schema": None,
                    "valves_config": None,
                    "is_active": True,
                    "sort_order": 0,
                }
            )
            return package

        if package.is_deleted:
            package.restore()
        package.tenant_id = None
        package.name = SKILL_PACKAGE_NAME
        package.description = "内置运营 Copilot 的内部操作元工具（list/describe/invoke）"
        package.avatar = None
        package.is_recommended = False
        package.source_plugin = None
        package.is_system = True
        package.valves_schema = None
        package.valves_config = None
        package.is_active = True
        package.sort_order = 0
        await self.db.flush()
        await self.db.refresh(package)
        return package

    async def _ensure_skill(self, package: SkillPackage) -> Skill:
        skill = await self.repo.get_platform_system_skill_by_key(
            SKILL_KEY,
            include_deleted=True,
        )
        if skill is None:
            conflicting_skill = await self.repo.get_any_skill_by_key(
                SKILL_KEY,
                include_deleted=True,
            )
            if conflicting_skill is not None:
                raise BusinessException(
                    message=_("agent.error.system_skill_key_conflict").format(
                        key=SKILL_KEY,
                    )
                )
            skill = await self.repo.create_skill(
                {
                    "tenant_id": None,
                    "package_id": package.id,
                    "name": SKILL_NAME,
                    "key": SKILL_KEY,
                    "description": (
                        "运营 Copilot 元工具：搜索操作目录、查看参数规格、以用户身份执行内部 API。"
                        "工具 schema 由代码定义。"
                    ),
                    "avatar": None,
                    "type": "builtin",
                    "source_type": SkillSourceTypeEnum.PLATFORM_BUILTIN.value,
                    "source_ref": None,
                    "skill_md": None,
                    "version": "1.0.0",
                    "status": SkillStatusEnum.ACTIVE.value,
                    "is_readonly": True,
                    "config": {"builtin_type": "internal_ops"},
                    "toolkit_content": None,
                    "toolkit_meta": None,
                    "input_schema": None,
                    "output_schema": None,
                    "is_system": True,
                    "is_active": True,
                    "sort_order": 0,
                    "timeout": 60,
                }
            )
            return skill

        if skill.is_deleted:
            skill.restore()
        skill.tenant_id = None
        skill.package_id = package.id
        skill.name = SKILL_NAME
        skill.key = SKILL_KEY
        skill.description = (
            "运营 Copilot 元工具：搜索操作目录、查看参数规格、以用户身份执行内部 API。"
            "工具 schema 由代码定义。"
        )
        skill.avatar = None
        skill.type = "builtin"
        skill.source_type = SkillSourceTypeEnum.PLATFORM_BUILTIN.value
        skill.source_ref = None
        skill.skill_md = None
        skill.version = "1.0.0"
        skill.status = SkillStatusEnum.ACTIVE.value
        skill.is_readonly = True
        skill.config = {"builtin_type": "internal_ops"}
        skill.toolkit_content = None
        skill.toolkit_meta = None
        skill.input_schema = None
        skill.output_schema = None
        skill.is_system = True
        skill.is_active = True
        skill.sort_order = 0
        skill.timeout = 60
        await self.db.flush()
        await self.db.refresh(skill)
        return skill

    async def _ensure_context_tools_skill_package(self) -> SkillPackage:
        package = await self.repo.get_platform_system_skill_package_by_name(
            CONTEXT_SKILL_PACKAGE_NAME,
            include_deleted=True,
        )
        payload = {
            "tenant_id": None,
            "name": CONTEXT_SKILL_PACKAGE_NAME,
            "description": "内置智能体上下文工具：知识库检索与长期记忆读写。",
            "avatar": None,
            "is_recommended": False,
            "source_plugin": None,
            "is_system": True,
            "valves_schema": None,
            "valves_config": None,
            "is_active": True,
            "sort_order": 10,
        }
        if package is None:
            return await self.repo.create_skill_package(payload)

        if package.is_deleted:
            package.restore()
        for key, value in payload.items():
            setattr(package, key, value)
        await self.db.flush()
        await self.db.refresh(package)
        return package

    async def _ensure_context_tool_skill(
        self,
        *,
        package: SkillPackage,
        key: str,
        name: str,
        description: str,
        tools: list[str],
        timeout: int,
        sort_order: int,
    ) -> Skill:
        skill = await self.repo.get_platform_system_skill_by_key(
            key,
            include_deleted=True,
        )
        if skill is None:
            conflicting_skill = await self.repo.get_any_skill_by_key(
                key,
                include_deleted=True,
            )
            if conflicting_skill is not None:
                raise BusinessException(
                    message=_("agent.error.system_skill_key_conflict").format(
                        key=key,
                    )
                )
            return await self.repo.create_skill(
                {
                    "tenant_id": None,
                    "package_id": package.id,
                    "name": name,
                    "key": key,
                    "description": description,
                    "avatar": None,
                    "type": "builtin",
                    "source_type": SkillSourceTypeEnum.PLATFORM_BUILTIN.value,
                    "source_ref": None,
                    "skill_md": None,
                    "version": "1.0.0",
                    "status": SkillStatusEnum.ACTIVE.value,
                    "is_readonly": True,
                    "config": {"builtin_type": "context_tools", "tools": tools},
                    "toolkit_content": None,
                    "toolkit_meta": None,
                    "input_schema": None,
                    "output_schema": None,
                    "is_system": True,
                    "is_active": True,
                    "sort_order": sort_order,
                    "timeout": timeout,
                }
            )

        if skill.is_deleted:
            skill.restore()
        skill.tenant_id = None
        skill.package_id = package.id
        skill.name = name
        skill.key = key
        skill.description = description
        skill.avatar = None
        skill.type = "builtin"
        skill.source_type = SkillSourceTypeEnum.PLATFORM_BUILTIN.value
        skill.source_ref = None
        skill.skill_md = None
        skill.version = "1.0.0"
        skill.status = SkillStatusEnum.ACTIVE.value
        skill.is_readonly = True
        skill.config = {"builtin_type": "context_tools", "tools": tools}
        skill.toolkit_content = None
        skill.toolkit_meta = None
        skill.input_schema = None
        skill.output_schema = None
        skill.is_system = True
        skill.is_active = True
        skill.sort_order = sort_order
        skill.timeout = timeout
        await self.db.flush()
        await self.db.refresh(skill)
        return skill

    async def _ensure_context_tool_skills(self) -> tuple[SkillPackage, list[Skill]]:
        package = await self._ensure_context_tools_skill_package()
        kb_skill = await self._ensure_context_tool_skill(
            package=package,
            key=CONTEXT_KB_SKILL_KEY,
            name=CONTEXT_KB_SKILL_NAME,
            description=(
                "检索当前智能体绑定的知识库，返回片段、来源与引用线索。"
                "工具 schema 由代码定义。"
            ),
            tools=["search_agent_knowledge_base"],
            timeout=45,
            sort_order=0,
        )
        memory_skill = await self._ensure_context_tool_skill(
            package=package,
            key=CONTEXT_MEMORY_SKILL_KEY,
            name=CONTEXT_MEMORY_SKILL_NAME,
            description=(
                "保存与召回当前用户在当前智能体下的长期记忆。"
                "工具 schema 由代码定义。"
            ),
            tools=["save_long_term_memory", "recall_long_term_memory"],
            timeout=30,
            sort_order=1,
        )
        return package, [kb_skill, memory_skill]

    async def _ensure_agent(
        self,
        feature: SystemAgentSeedFeature,
        *,
        model: AIModel,
    ) -> Agent:
        agent = await self.repo.get_platform_system_agent_by_name(
            feature.agent_name,
            include_deleted=True,
        )

        payload = {
            "owner_tenant_id": None,
            "name": feature.agent_name,
            "description": feature.agent_description,
            "scope": feature.required_scope,
            "source_plugin": None,
            "avatar": None,
            "model_id": model.id,
            "system_prompt": COPILOT_SYSTEM_PROMPT,
            "temperature": 0.3,
            "max_tokens": None,
            "top_p": None,
            "status": AgentStatusEnum.PUBLISHED.value,
            "execution_mode": AgentExecutionModeEnum.CONVERSATION.value,
            "published_version": None,
            "visibility": AgentVisibilityEnum.PUBLIC.value,
            "quota_config": None,
            "routing_config": None,
            "memory_enabled": True,
            "input_variables": [],
            "rag_config": None,
            "context_config": None,
            "output_schema": None,
            "is_system": True,
            "welcome_message": None,
            "suggested_questions": None,
        }

        if agent is None:
            return await self.repo.create_agent(payload)

        if agent.is_deleted:
            agent.restore()
        agent.owner_tenant_id = None
        agent.name = feature.agent_name
        agent.description = feature.agent_description
        agent.scope = feature.required_scope
        agent.source_plugin = None
        agent.avatar = None
        agent.model_id = model.id
        agent.system_prompt = COPILOT_SYSTEM_PROMPT
        agent.temperature = 0.3
        agent.max_tokens = None
        agent.top_p = None
        agent.status = AgentStatusEnum.PUBLISHED.value
        agent.execution_mode = AgentExecutionModeEnum.CONVERSATION.value
        agent.published_version = None
        agent.visibility = AgentVisibilityEnum.PUBLIC.value
        agent.quota_config = None
        agent.routing_config = None
        agent.memory_enabled = True
        agent.input_variables = []
        agent.rag_config = None
        agent.context_config = None
        agent.output_schema = None
        agent.is_system = True
        agent.welcome_message = None
        agent.suggested_questions = None
        await self.db.flush()
        await self.db.refresh(agent)
        return agent

    async def _ensure_grant(self, agent: Agent, skill: Skill) -> AgentSkillGrant:
        grant = await self.repo.get_agent_skill_grant(
            agent_id=agent.id,
            skill_id=skill.id,
            include_deleted=True,
        )
        if grant is None:
            return await self.repo.create_agent_skill_grant(
                {
                    "tenant_id": None,
                    "agent_id": agent.id,
                    "skill_id": skill.id,
                    "enabled": True,
                    "config_override": None,
                    "sort_order": 0,
                    "default_consent_mode": ToolConsentModeEnum.AUTO.value,
                    "capability_consent_overrides": None,
                }
            )

        if grant.is_deleted:
            grant.restore()
        grant.tenant_id = None
        grant.agent_id = agent.id
        grant.skill_id = skill.id
        grant.enabled = True
        grant.config_override = None
        grant.sort_order = 0
        grant.default_consent_mode = ToolConsentModeEnum.AUTO.value
        grant.capability_consent_overrides = None
        await self.db.flush()
        await self.db.refresh(grant)
        return grant

    async def _ensure_assignment(
        self,
        feature: SystemAgentSeedFeature,
        *,
        agent: Agent,
    ) -> tuple[SystemAgentAssignment, bool]:
        assignment = await self.repo.get_global_assignment(
            feature.feature_code,
            include_deleted=True,
        )
        if assignment is None:
            return (
                await self.repo.create_assignment(
                    {
                        "feature_code": feature.feature_code,
                        "feature_name": feature.feature_name,
                        "description": (
                            f"{feature.feature_name} 入口绑定的智能体"
                        ),
                        "tenant_id": None,
                        "agent_id": agent.id,
                        "config": None,
                        "is_active": True,
                    }
                ),
                True,
            )

        if assignment.is_deleted:
            assignment.restore()

        target = getattr(assignment, "agent", None)
        target_runtime_ready = await self._is_agent_runtime_ready(target)
        target_valid = (
            target is not None
            and not getattr(target, "is_deleted", False)
            and getattr(target, "owner_tenant_id", None) is None
            and getattr(target, "status", None) == AgentStatusEnum.PUBLISHED.value
            and getattr(target, "scope", None) == feature.required_scope
            and target_runtime_ready
        )

        preserve_custom = (
            target_valid
            and assignment.is_active
            and not bool(getattr(target, "is_system", False))
        )
        if preserve_custom:
            assignment.feature_code = feature.feature_code
            assignment.feature_name = feature.feature_name
            assignment.description = f"{feature.feature_name} 入口绑定的智能体"
            assignment.tenant_id = None
            await self.db.flush()
            await self.db.refresh(assignment)
            return assignment, False

        assignment.feature_code = feature.feature_code
        assignment.feature_name = feature.feature_name
        assignment.description = f"{feature.feature_name} 入口绑定的智能体"
        assignment.tenant_id = None
        assignment.agent_id = agent.id
        assignment.config = None
        assignment.is_active = True
        await self.db.flush()
        await self.db.refresh(assignment)
        return assignment, True

    async def get_bootstrap_status(self) -> dict[str, Any]:
        provider = await self.repo.get_first_active_provider()
        model = await self.repo.get_first_active_chat_model()

        system_assignments: list[dict[str, Any]] = []
        for feature in SYSTEM_AGENT_FEATURES:
            assignment = await self.repo.get_global_assignment(
                feature.feature_code,
                include_deleted=True,
            )
            system_assignments.append(
                await self._serialize_assignment(feature, assignment)
            )

        has_active_provider = provider is not None
        has_active_chat_model = model is not None
        system_agents_ready = all(
            item["state"] in {"ready", "custom_ready"} for item in system_assignments
        )

        if not has_active_provider:
            bootstrap_state = "missing_provider"
        elif not has_active_chat_model:
            bootstrap_state = "missing_model"
        elif not system_agents_ready:
            bootstrap_state = "seed_system"
        else:
            bootstrap_state = "ready"

        return {
            "bootstrap_state": bootstrap_state,
            "runtime_ready": has_active_provider and has_active_chat_model,
            "has_active_provider": has_active_provider,
            "has_active_chat_model": has_active_chat_model,
            "active_provider": self._serialize_provider(provider),
            "active_chat_model": self._serialize_model(model),
            "system_agents_ready": system_agents_ready,
            "needs_seed": bootstrap_state == "seed_system",
            "system_assignments": system_assignments,
        }

    async def seed_system_agents(self) -> dict[str, Any]:
        provider = await self.repo.get_first_active_provider()
        if provider is None:
            raise BusinessException(message=_("agent.error.no_active_provider"))

        model = await self.repo.get_first_active_chat_model()
        if model is None:
            raise BusinessException(message=_("agent.error.no_active_chat_model"))

        await self.db.execute(
            text("SELECT pg_advisory_xact_lock(:lock_key)"),
            {"lock_key": SYSTEM_AGENT_SEED_LOCK_KEY},
        )

        package = await self._ensure_skill_package()
        skill = await self._ensure_skill(package)
        context_package, context_skills = await self._ensure_context_tool_skills()
        del context_package

        created_agents = 0
        updated_agents = 0
        created_grants = 0
        updated_grants = 0
        created_assignments = 0
        repaired_assignments = 0
        preserved_assignments = 0

        for feature in SYSTEM_AGENT_FEATURES:
            agent_before = await self.repo.get_platform_system_agent_by_name(
                feature.agent_name,
                include_deleted=True,
            )
            agent = await self._ensure_agent(feature, model=model)
            if agent_before is None:
                created_agents += 1
            else:
                updated_agents += 1

            for grant_skill in [skill, *context_skills]:
                grant_before = await self.repo.get_agent_skill_grant(
                    agent_id=agent.id,
                    skill_id=grant_skill.id,
                    include_deleted=True,
                )
                grant_was_deleted = bool(getattr(grant_before, "is_deleted", False))
                await self._ensure_grant(agent, grant_skill)
                if grant_before is None or grant_was_deleted:
                    created_grants += 1
                else:
                    updated_grants += 1

            assignment_before = await self.repo.get_global_assignment(
                feature.feature_code,
                include_deleted=True,
            )
            assignment_was_deleted = bool(
                getattr(assignment_before, "is_deleted", False)
            )
            assignment_result, repaired = await self._ensure_assignment(
                feature,
                agent=agent,
            )
            del assignment_result
            if assignment_before is None:
                created_assignments += 1
            elif repaired or assignment_was_deleted:
                repaired_assignments += 1
            else:
                preserved_assignments += 1

        await self.db.flush()
        status = await self.get_bootstrap_status()
        status["seed_summary"] = {
            "created_agents": created_agents,
            "updated_agents": updated_agents,
            "created_grants": created_grants,
            "updated_grants": updated_grants,
            "created_assignments": created_assignments,
            "repaired_assignments": repaired_assignments,
            "preserved_assignments": preserved_assignments,
        }
        return status


__all__ = [
    "SystemAgentSeedService",
]
