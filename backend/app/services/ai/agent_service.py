"""
智能体 Service / Agent Service
"""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.schemas.common.query import QuerySpec

from app.configs.service import PLATFORM_TENANT_ID
from app.configs.service import ConfigService
from app.core.base_model import utc_now
from app.core.base_service import GlobalService, TenantService
from app.core.i18n import _
from app.core.logging import LogManager
from app.enums.agent import (
    AgentPublicationAccessTypeEnum,
    AgentStatusEnum,
)
from app.enums.ai import CallAccessChannelEnum
from app.enums.common import ResourceScopeEnum, UserRoleEnum
from app.enums.knowledge_base import RewriteStrategyEnum, SearchModeEnum
from app.exceptions import BusinessException, NotFoundException
from app.models.ai.agent import Agent
from app.repositories.ai import AIModelRepository
from app.repositories.ai.agent_access_repository import AgentAccessRepository
from app.repositories.ai.agent_memory_override_repository import (
    AgentMemoryOverrideRepository,
)
from app.repositories.ai.agent_repository import AdminAgentRepository, AgentRepository
from app.repositories.ai.tenant_agent_publication_repository import (
    TenantAgentPublicationRepository,
)
from app.repositories.ai.agent_version_repository import AgentVersionRepository

logger = LogManager.get_logger("ai.agent_service")

# 版本快照字段：从 Agent 复制到 AgentVersion 的字段列表
_VERSION_SNAPSHOT_FIELDS = [
    "system_prompt",
    "model_id",
    "temperature",
    "max_tokens",
    "top_p",
    "execution_mode",
    "input_variables",
    "welcome_message",
    "suggested_questions",
    "quota_config",
    "rag_config",
    "context_config",
    "output_schema",
    # NOTE: tool_bindings / knowledge_base_ids removed —
    # replaced by direct AgentSkillGrant + AgentKnowledgeBaseBinding architecture / 已由 AgentSkillGrant 等替代 / replaced by grants
]


def _normalize_agent_rag_config(raw: Any) -> dict[str, Any] | None:
    """Validate mutable Agent.rag_config fields / 校验并归一化可写的 Agent.rag_config 字段。"""
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise BusinessException(message=_("agent.error.invalid_rag_config"))

    normalized = dict(raw)

    def _raise_invalid(field: str) -> None:
        raise BusinessException(
            message=_("agent.error.invalid_rag_config_field").format(field=field)
        )

    search_mode = raw.get("search_mode")
    if search_mode is not None:
        allowed_search_modes = {item.value for item in SearchModeEnum}
        if search_mode not in allowed_search_modes:
            _raise_invalid("search_mode")

    rewrite_strategy = raw.get("rewrite_strategy")
    if rewrite_strategy is not None:
        allowed_rewrite_strategies = {item.value for item in RewriteStrategyEnum}
        if rewrite_strategy not in allowed_rewrite_strategies:
            _raise_invalid("rewrite_strategy")

    if "top_k" in raw and raw.get("top_k") is not None:
        top_k = raw.get("top_k")
        if isinstance(top_k, bool) or not isinstance(top_k, int) or not (1 <= top_k <= 20):
            _raise_invalid("top_k")
        normalized["top_k"] = top_k

    if "score_threshold" in raw and raw.get("score_threshold") is not None:
        score_threshold = raw.get("score_threshold")
        if isinstance(score_threshold, bool) or not isinstance(score_threshold, (float, int)):
            _raise_invalid("score_threshold")
        score_threshold = float(score_threshold)
        if not (0.0 <= score_threshold <= 1.0):
            _raise_invalid("score_threshold")
        normalized["score_threshold"] = score_threshold

    if "reranker_enabled" in raw and raw.get("reranker_enabled") is not None:
        reranker_enabled = raw.get("reranker_enabled")
        if not isinstance(reranker_enabled, bool):
            _raise_invalid("reranker_enabled")
        normalized["reranker_enabled"] = reranker_enabled

    if "context_token_ratio" in raw and raw.get("context_token_ratio") is not None:
        context_token_ratio = raw.get("context_token_ratio")
        if isinstance(context_token_ratio, bool) or not isinstance(context_token_ratio, (float, int)):
            _raise_invalid("context_token_ratio")
        context_token_ratio = float(context_token_ratio)
        if not (0.1 <= context_token_ratio <= 0.9):
            _raise_invalid("context_token_ratio")
        normalized["context_token_ratio"] = context_token_ratio

    return normalized


def _role_ids_allow(role_ids: list[int] | None, user_role_id: int | None) -> bool:
    """Resolve internal role restriction semantics / 解析端内角色限制语义."""
    if role_ids is None:
        return True
    if not role_ids:
        return False
    if user_role_id is None:
        return False
    return user_role_id in role_ids


async def _validate_agent_max_tokens_against_model(
    db: Any,
    *,
    model_id: int | None,
    max_tokens: int | None,
) -> None:
    """Ensure agent max_tokens does not exceed model max_output_tokens / 校验智能体 max_tokens 不超过模型 max_output_tokens."""
    if model_id is None or max_tokens is None:
        return

    model_repo = AIModelRepository(db)
    model = await model_repo.get_by_id(model_id)
    if not model:
        return

    model_limit = getattr(model, "max_output_tokens", None)
    if model_limit is None or max_tokens <= model_limit:
        return

    raise BusinessException(
        message=_("agent.error.max_tokens_exceeds_model_limit").format(
            max_tokens=max_tokens,
            model_limit=model_limit,
            model_name=getattr(model, "name", model_id),
        ),
    )


async def _clear_cascaded_conversation_memories(
    targets: list[tuple[int, int]],
) -> int:
    """Best-effort clear session memories for cascaded conversation deletes / 级联删除会话后的记忆最佳努力清理。"""
    if not targets:
        return 0

    from app.services.ai.session_memory_service import SessionMemoryService

    grouped: dict[int, list[int]] = defaultdict(list)
    for tenant_id, conversation_id in targets:
        grouped[int(tenant_id)].append(int(conversation_id))

    total_deleted = 0
    for tenant_id, conversation_ids in grouped.items():
        try:
            total_deleted += await SessionMemoryService(tenant_id).clear_conversation_memories(
                conversation_ids,
            )
        except Exception as exc:
            logger.warning(
                "Cascade conversation memory cleanup failed: tenant={} count={} err={}",
                tenant_id,
                len(conversation_ids),
                str(exc),
            )
    return total_deleted


class AgentService(TenantService[Agent, AgentRepository]):
    """
    智能体 Service / Agent service.

    提供智能体的创建、更新、发布、回滚等业务逻辑
    """

    model = Agent
    repository_class = AgentRepository

    def _get_version_repo(self) -> AgentVersionRepository:
        """获取版本 Repository / Get version repository."""
        return AgentVersionRepository(self.db, self.tenant_id)

    async def _snapshot_skill_grants(self, agent_id: int) -> list[dict[str, Any]]:
        """快照当前 Agent 的技能授权列表（用于版本发布） / Snapshot agent skill grants (for version publish)."""
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload

        from app.models.ai.agent_skill_grant import AgentSkillGrant
        from app.models.ai.skill import Skill

        result = await self.db.execute(
            select(AgentSkillGrant)
            .options(selectinload(AgentSkillGrant.skill).selectinload(Skill.package))
            .where(
                AgentSkillGrant.agent_id == agent_id,
                AgentSkillGrant.is_deleted.is_(False),
            )
            .order_by(AgentSkillGrant.sort_order),
        )
        grants = result.scalars().all()

        return [
            {
                "skill_id": grant.skill_id,
                "skill_name": grant.skill.name if grant.skill else None,
                "package_id": grant.skill.package_id if grant.skill else None,
                "package_name": (
                    grant.skill.package.name
                    if grant.skill and grant.skill.package
                    else None
                ),
                "enabled": grant.enabled,
                "default_consent_mode": grant.default_consent_mode,
                "capability_consent_overrides": grant.capability_consent_overrides,
                "sort_order": grant.sort_order,
                "config_override": grant.config_override,
            }
            for grant in grants
        ]

    async def _restore_skill_grants(
        self,
        agent_id: int,
        grants_snapshot: list[dict[str, Any]] | None,
    ) -> None:
        """从版本快照恢复技能授权（用于版本回滚） / Restore skill grants from snapshot (for rollback)."""
        if grants_snapshot is None:
            return

        from app.services.ai.agent_skill_grant_service import AgentSkillGrantService

        grant_svc = AgentSkillGrantService(self.db, self.tenant_id)

        from app.models.ai.skill import Skill

        valid_items: list[dict[str, Any]] = []
        default_consent_modes: dict[str, str] = {}

        for item in grants_snapshot:
            skill_id = item.get("skill_id")
            if not skill_id:
                continue
            skill = await self.db.get(Skill, skill_id)
            if not skill or skill.is_deleted:
                logger.warning(
                    "Skipping deleted skill {} during rollback for agent {}",
                    skill_id, agent_id,
                )
                continue

            valid_items.append(item)
            default_consent_modes[str(skill_id)] = item.get(
                "default_consent_mode", "auto",
            )

        if not valid_items:
            await grant_svc.delete_all_for_agent(agent_id)
            return

        grants = await grant_svc.batch_bind(
            agent_id=agent_id,
            skill_ids=[int(item["skill_id"]) for item in valid_items],
            default_consent_modes=default_consent_modes,
        )
        grant_map = {grant.skill_id: grant for grant in grants}

        for item in valid_items:
            skill_id = int(item["skill_id"])
            grant = grant_map.get(skill_id)
            if not grant:
                continue

            await grant_svc.update_grant(grant.id, {
                "enabled": item.get("enabled", True),
                "default_consent_mode": item.get("default_consent_mode", "auto"),
                "capability_consent_overrides": item.get("capability_consent_overrides"),
                "sort_order": item.get("sort_order", 0),
                "config_override": item.get("config_override"),
            })

    def _get_access_repo(self) -> AgentAccessRepository:
        """获取访问权限 Repository / Get access repository."""
        return AgentAccessRepository(self.db, self.tenant_id)

    def _get_publication_repo(self) -> TenantAgentPublicationRepository:
        """获取企业智能体用户发布 Repository / Get tenant agent publication repository."""
        return TenantAgentPublicationRepository(self.db, self.tenant_id)

    def _get_memory_override_repo(self) -> AgentMemoryOverrideRepository:
        """获取企业记忆开关覆盖 Repository / Get memory override repository."""
        return AgentMemoryOverrideRepository(self.db, self.tenant_id)

    async def _get_platform_default_memory_enabled(self) -> bool:
        """获取平台默认记忆开关（默认 True） / Get platform default memory enabled (default True)."""
        config_service = ConfigService(self.db)
        value = await config_service.get_platform_config(
            "platform_default_memory_enabled",
            default=True,
        )
        return bool(value)

    async def resolve_memory_effective_config(self, agent_id: int) -> dict[str, bool]:
        """
        计算智能体记忆最终生效状态（企业侧） / Resolve effective memory config (tenant side).
        规则：effective = platform AND admin_agent AND (NOT tenant_disabled).
        """
        agent = await self.repo.get_by_id(agent_id)
        if not agent:
            raise NotFoundException(message=_("agent.error.not_found"))

        platform_enabled = await self._get_platform_default_memory_enabled()
        admin_agent_enabled = bool(getattr(agent, "memory_enabled", True))

        override_repo = self._get_memory_override_repo()
        override = await override_repo.get_by_agent_id(agent_id)
        tenant_disabled = bool(override and override.disabled)

        effective = platform_enabled and admin_agent_enabled and (not tenant_disabled)

        return {
            "platform_default_memory_enabled": platform_enabled,
            "admin_agent_memory_enabled": admin_agent_enabled,
            "tenant_agent_memory_disabled": tenant_disabled,
            "effective_memory_enabled": effective,
        }

    async def get_memory_config(self, agent_id: int) -> dict[str, Any]:
        """
        获取企业侧智能体记忆配置状态 / Get tenant-side agent memory config.
        """
        await self.get_agent_detail(agent_id)
        resolved = await self.resolve_memory_effective_config(agent_id)
        return {
            "agent_id": agent_id,
            **resolved,
        }

    async def set_memory_disabled(
        self,
        agent_id: int,
        disabled: bool,
    ) -> dict[str, Any]:
        """
        设置企业侧“关闭记忆”覆盖（仅支持关闭/恢复默认） / Set tenant memory-disabled override (disable or restore default).
        """
        agent = await self.repo.get_by_id(agent_id)
        if not agent:
            raise NotFoundException(message=_("agent.error.not_found"))

        # 企业端仅允许操作自有 agent；全局/系统 agent 不允许覆盖
        if agent.owner_tenant_id != self.tenant_id:
            raise BusinessException(message=_("agent.error.system_protected"))

        override_repo = self._get_memory_override_repo()
        existing = await override_repo.get_by_agent_id(agent_id)

        if disabled:
            if existing:
                await override_repo.update(existing.id, {"disabled": True})
            else:
                await override_repo.create({
                    "tenant_id": self.tenant_id,
                    "agent_id": agent_id,
                    "disabled": True,
                })
        else:
            if existing:
                await override_repo.delete(existing.id, soft=False)

        return await self.get_memory_config(agent_id)

    async def _before_create(self, data: dict[str, Any]) -> None:
        """创建前校验：名称唯一性 + 插件钩子 / Before create: name uniqueness + plugin hooks."""
        await super()._before_create(data)

        from app.ai.events.hooks import HookPoint, get_hook_registry
        hook_registry = get_hook_registry()
        if hook_registry.has_hooks(HookPoint.BEFORE_AGENT_CREATE):
            ctx = await hook_registry.trigger(
                HookPoint.BEFORE_AGENT_CREATE,
                tenant_id=self.tenant_id,
                agent_data=data,
            )
            if ctx.get("blocked"):
                raise BusinessException(message=ctx.get("block_reason", _("agent.error.blocked_by_hook")))
            data.update(ctx.get("agent_data", data))

        data["owner_tenant_id"] = self.tenant_id
        for rejected in ("owner_type", "distribution_mode"):
            if rejected in data:
                raise BusinessException(message=_("agent.error.rejected_legacy_field").format(field=rejected))
        data.pop("tenant_id", None)
        scope_val = data.get("scope") or ResourceScopeEnum.ALL_TENANTS.value
        if scope_val not in {e.value for e in ResourceScopeEnum}:
            raise BusinessException(message=_("agent.error.invalid_scope"))
        data["scope"] = scope_val
        if "rag_config" in data:
            data["rag_config"] = _normalize_agent_rag_config(data.get("rag_config"))

        name = data.get("name")
        if name:
            existing = await self.repo.get_by_name(name)
            if existing:
                raise BusinessException(message=_("agent.error.name_exists"))

        await _validate_agent_max_tokens_against_model(
            self.db,
            model_id=data.get("model_id"),
            max_tokens=data.get("max_tokens"),
        )

    async def _after_create(self, instance: Agent) -> None:
        """创建后：触发插件钩子 / After create: trigger plugin hooks."""
        await super()._after_create(instance)
        from app.ai.events.hooks import HookPoint, get_hook_registry
        hook_registry = get_hook_registry()
        if hook_registry.has_hooks(HookPoint.AFTER_AGENT_CREATE):
            await hook_registry.trigger(
                HookPoint.AFTER_AGENT_CREATE,
                tenant_id=self.tenant_id,
                agent_id=instance.id,
                agent_data=instance.to_dict() if hasattr(instance, "to_dict") else {},
            )

    async def _before_update(self, id: int, data: dict[str, Any]) -> None:
        """更新前校验：名称唯一性、系统智能体保护 + 插件钩子 / Before update: name uniqueness, system agent protection, plugin hooks."""
        await super()._before_update(id, data)

        from app.ai.events.hooks import HookPoint, get_hook_registry
        hook_registry = get_hook_registry()
        if hook_registry.has_hooks(HookPoint.BEFORE_AGENT_UPDATE):
            ctx = await hook_registry.trigger(
                HookPoint.BEFORE_AGENT_UPDATE,
                tenant_id=self.tenant_id,
                agent_id=id,
                updates=data,
            )
            if ctx.get("blocked"):
                raise BusinessException(message=ctx.get("block_reason", _("agent.error.blocked_by_hook")))
            data.update(ctx.get("updates", data))

        agent = await self.repo.get_by_id(id)
        if not agent:
            raise NotFoundException(message=_("agent.error.not_found"))

        # 企业端只能修改自有智能体（即 tenant_id 与当前企业匹配）
        if agent.owner_tenant_id != self.tenant_id:
            raise BusinessException(message=_("agent.error.system_protected"))

        for rejected in ("owner_type", "distribution_mode"):
            if rejected in data:
                raise BusinessException(message=_("agent.error.rejected_legacy_field").format(field=rejected))
        data.pop("tenant_id", None)
        data.pop("owner_tenant_id", None)
        if "scope" in data and data["scope"] is not None:
            if data["scope"] not in {e.value for e in ResourceScopeEnum}:
                raise BusinessException(message=_("agent.error.invalid_scope"))
        if "rag_config" in data:
            data["rag_config"] = _normalize_agent_rag_config(data.get("rag_config"))

        if agent.is_system:
            protected = {"is_system", "status", "execution_mode"}
            if protected & set(data.keys()):
                raise BusinessException(message=_("agent.error.system_protected"))

        name = data.get("name")
        if name:
            existing = await self.repo.get_by_name(name, exclude_id=id)
            if existing:
                raise BusinessException(message=_("agent.error.name_exists"))

        await _validate_agent_max_tokens_against_model(
            self.db,
            model_id=data.get("model_id", agent.model_id),
            max_tokens=data.get("max_tokens", agent.max_tokens),
        )

    async def _after_update(self, instance: Agent) -> None:
        """更新后：触发插件钩子 / After update: trigger plugin hooks."""
        await super()._after_update(instance)
        from app.ai.events.hooks import HookPoint, get_hook_registry
        hook_registry = get_hook_registry()
        if hook_registry.has_hooks(HookPoint.AFTER_AGENT_UPDATE):
            await hook_registry.trigger(
                HookPoint.AFTER_AGENT_UPDATE,
                tenant_id=self.tenant_id,
                agent_id=instance.id,
                updates=instance.to_dict() if hasattr(instance, "to_dict") else {},
            )

    async def _before_delete(self, id: int) -> None:
        """删除前校验：系统智能体不可删除，级联软删除对话 + 插件钩子 / Before delete: system protected, cascade soft-delete conversations, plugin hooks."""
        await super()._before_delete(id)

        from app.ai.events.hooks import HookPoint, get_hook_registry
        hook_registry = get_hook_registry()
        if hook_registry.has_hooks(HookPoint.BEFORE_AGENT_DELETE):
            ctx = await hook_registry.trigger(
                HookPoint.BEFORE_AGENT_DELETE,
                tenant_id=self.tenant_id,
                agent_id=id,
            )
            if ctx.get("blocked"):
                raise BusinessException(message=ctx.get("block_reason", _("agent.error.blocked_by_hook")))

        agent = await self.repo.get_by_id(id)
        if not agent:
            raise NotFoundException(message=_("agent.error.not_found"))

        # 企业端只能删除自有智能体（即 tenant_id 与当前企业匹配）
        if agent.owner_tenant_id != self.tenant_id:
            raise BusinessException(message=_("agent.error.system_protected"))

        if agent.is_system:
            raise BusinessException(message=_("agent.error.system_protected"))

        conversation_targets = await self.repo.list_conversation_memory_cleanup_targets(
            id,
        )
        # 级联软删除智能体的对话记录 / Cascade soft-delete agent conversations
        await self.repo.cascade_soft_delete_conversations(id, self._default_delete_level)
        deleted_keys = await _clear_cascaded_conversation_memories(conversation_targets)
        if conversation_targets:
            logger.info(
                "Cascade conversation cleanup finished: agent_id={} conversations={} deleted_keys={}",
                id,
                len(conversation_targets),
                deleted_keys,
            )

    async def _after_delete(self, instance: Agent) -> None:
        """删除后：触发插件钩子 / After delete: trigger plugin hooks."""
        await super()._after_delete(instance)
        from app.ai.events.hooks import HookPoint, get_hook_registry
        hook_registry = get_hook_registry()
        if hook_registry.has_hooks(HookPoint.AFTER_AGENT_DELETE):
            await hook_registry.trigger(
                HookPoint.AFTER_AGENT_DELETE,
                tenant_id=self.tenant_id,
                agent_id=instance.id,
            )

    async def promote_to_global(self, id: int) -> Agent | None:
        """推进到总回收站，级联推进对话记录 / Promote to global recycle bin and cascade conversations."""
        instance = await self.repo.promote_to_global_by_id(
            id,
            delete_level=self._default_delete_level,
        )
        if instance is None:
            return None

        await self.repo.cascade_promote_conversations(id)
        return instance

    async def _after_restore(self, instance: Agent) -> None:
        """恢复后：级联恢复对话记录 / After restore: cascade restore conversations."""
        await self.repo.cascade_restore_conversations(instance.id)

    async def get_agent_detail(self, agent_id: int) -> dict[str, Any]:
        """
        获取智能体详情（含关联模型信息） / Get agent detail (with model info).

        Args:
            agent_id: 智能体 ID / Agent ID.

        Returns:
            包含模型名称/代码的智能体字典 / Agent dict with model name/code.
        """
        agent = await self.repo.get_by_id(agent_id)
        if not agent:
            raise NotFoundException(message=_("agent.error.not_found"))

        # 构建响应字典 / Build response dict
        result = agent.to_dict()
        result["owner_tenant_id"] = agent.owner_tenant_id
        result["tenant_id"] = agent.owner_tenant_id
        result["owner_type"] = (
            "tenant" if agent.owner_tenant_id is not None else "platform"
        )
        result["scope"] = getattr(agent, "scope", None)
        result["model_name"] = None
        result["model_code"] = None

        try:
            model_obj = getattr(agent, "model", None)
            if model_obj is not None:
                result["model_name"] = model_obj.name
                result["model_code"] = model_obj.code
        except AttributeError:
            pass

        # 附加记忆开关计算结果（企业服务） / Attach computed memory toggle (tenant service)
        resolved = await self.resolve_memory_effective_config(agent_id)
        result["memory_enabled"] = bool(getattr(agent, "memory_enabled", True))
        result["effective_memory_enabled"] = resolved["effective_memory_enabled"]
        result["memory_disabled_by_tenant"] = resolved["tenant_agent_memory_disabled"]

        return result

    # ========================================
    # 版本管理 / Version management
    # ========================================

    async def publish_agent(
        self,
        agent_id: int,
        change_log: str | None = None,
        created_by: int | None = None,
    ) -> Agent:
        """
        发布智能体 / Publish agent.

        将当前配置冻结为新版本快照，更新 published_version，设置 status=published

        Args:
            agent_id: 智能体 ID
            change_log: 变更说明
            created_by: 发布人 ID

        Returns:
            更新后的 Agent 实例
        """
        agent = await self.repo.get_by_id(agent_id)
        if not agent:
            raise NotFoundException(message=_("agent.error.not_found"))

        # 计算新版本号 / Compute new version number
        version_repo = self._get_version_repo()
        latest_version = await version_repo.get_latest_version_number(agent_id)
        new_version = latest_version + 1

        # 创建版本快照 / Create version snapshot
        version_data: dict[str, Any] = {
            "agent_id": agent_id,
            "version": new_version,
            "tenant_id": self.tenant_id,
            "change_log": change_log,
            "created_by": created_by,
        }
        for field_name in _VERSION_SNAPSHOT_FIELDS:
            version_data[field_name] = getattr(agent, field_name)

        # 快照包含技能绑定信息 / Snapshot includes skill bindings
        version_data["tool_bindings"] = await self._snapshot_skill_grants(agent_id)

        await version_repo.create(version_data)

        # 更新 Agent 状态
        updated = await self.repo.update(agent_id, {
            "status": AgentStatusEnum.PUBLISHED.value,
            "published_version": new_version,
        })

        logger.info(
            "Agent published: agent_id={} tenant_id={} version={}",
            agent_id, self.tenant_id, new_version,
        )

        return updated

    async def rollback_agent(
        self,
        agent_id: int,
        version: int,
    ) -> Agent:
        """
        回滚智能体到指定版本 / Rollback agent to given version.

        将指定版本的配置回写到 Agent 主记录，设置 status=draft。
        published_version 保持不变（仍指向最后一次发布的版本号）。

        Args:
            agent_id: 智能体 ID
            version: 目标版本号

        Returns:
            更新后的 Agent 实例
        """
        agent = await self.repo.get_by_id(agent_id)
        if not agent:
            raise NotFoundException(message=_("agent.error.not_found"))

        version_repo = self._get_version_repo()
        version_record = await version_repo.get_by_agent_and_version(agent_id, version)
        if not version_record:
            raise NotFoundException(message=_("agent.version.error.not_found"))

        # 将版本配置回写到 Agent
        rollback_data: dict[str, Any] = {
            "status": AgentStatusEnum.DRAFT.value,
        }
        for field_name in _VERSION_SNAPSHOT_FIELDS:
            rollback_data[field_name] = getattr(version_record, field_name)

        updated = await self.repo.update(agent_id, rollback_data)

        # 恢复技能绑定 / Restore skill bindings
        await self._restore_skill_grants(
            agent_id, version_record.tool_bindings,
        )

        logger.info(
            "Agent rolled back: agent_id={} tenant_id={} version={}",
            agent_id, self.tenant_id, version,
        )

        return updated

    async def get_versions(
        self,
        agent_id: int,
    ) -> list[dict[str, Any]]:
        """
        获取智能体版本历史列表 / Get agent version history list.

        Args:
            agent_id: 智能体 ID

        Returns:
            版本列表（降序）
        """
        agent = await self.repo.get_by_id(agent_id)
        if not agent:
            raise NotFoundException(message=_("agent.error.not_found"))

        version_repo = self._get_version_repo()
        versions = await version_repo.get_versions_by_agent(agent_id)
        return [v.to_dict() for v in versions]

    async def get_version_detail(
        self,
        agent_id: int,
        version: int,
    ) -> dict[str, Any]:
        """
        获取智能体版本详情 / Get agent version detail.

        Args:
            agent_id: 智能体 ID
            version: 版本号

        Returns:
            版本详情字典
        """
        version_repo = self._get_version_repo()
        version_record = await version_repo.get_by_agent_and_version(agent_id, version)
        if not version_record:
            raise NotFoundException(message=_("agent.version.error.not_found"))

        return version_record.to_dict()

    async def diff_versions(
        self,
        agent_id: int,
        v1: int,
        v2: int,
    ) -> dict[str, Any]:
        """
        对比两个版本的字段差异 / Diff two versions by fields.

        Args:
            agent_id: 智能体 ID
            v1: 版本号 1
            v2: 版本号 2

        Returns:
            差异字典 {field: {"v1": ..., "v2": ...}, ...}
        """
        version_repo = self._get_version_repo()

        record_v1 = await version_repo.get_by_agent_and_version(agent_id, v1)
        if not record_v1:
            raise NotFoundException(
                message=_("agent.version.error.version_not_found_n", version=v1)
            )

        record_v2 = await version_repo.get_by_agent_and_version(agent_id, v2)
        if not record_v2:
            raise NotFoundException(
                message=_("agent.version.error.version_not_found_n", version=v2)
            )

        # 对比快照字段 / Compare snapshot fields
        diff: dict[str, Any] = {}
        for field_name in _VERSION_SNAPSHOT_FIELDS:
            val1 = getattr(record_v1, field_name)
            val2 = getattr(record_v2, field_name)
            if val1 != val2:
                diff[field_name] = {"v1": val1, "v2": val2}

        return {
            "agent_id": agent_id,
            "v1": v1,
            "v2": v2,
            "changes": diff,
        }


    # ========================================
    # 访问权限管理 / Access control management
    # ========================================

    async def get_access_config(self, agent_id: int) -> dict[str, Any]:
        """
        获取智能体访问权限配置（仅角色 ID 列表）/ Get agent access config (role ID lists only).

        Args:
            agent_id: 智能体 ID

        Returns:
            访问权限配置字典
        """
        agent = await self.repo.get_by_id(agent_id)
        if not agent:
            raise NotFoundException(message=_("agent.error.not_found"))

        access_repo = self._get_access_repo()
        access = await access_repo.get_by_agent_id(agent_id)

        return {
            "agent_id": agent_id,
            "admin_role_ids": getattr(access, "admin_role_ids", None) if access else None,
            "tenant_role_ids": getattr(access, "tenant_role_ids", None) if access else None,
        }

    async def update_access_config(
        self,
        agent_id: int,
        patch: dict[str, Any],
    ) -> dict[str, Any]:
        """
        更新智能体访问权限配置（仅角色 ID 列表）/ Update agent access config (role ID lists only).

        使用 patch 中**显式传入**的字段做部分更新（建议由 Pydantic model_dump(exclude_unset=True) 生成），
        避免企业端只改 tenant_role_ids 时把 admin_role_ids 误写成 NULL。
        Partial update: only keys present in patch are applied.

        Args:
            agent_id: 智能体 ID
            patch: 允许 admin_role_ids、tenant_role_ids

        Returns:
            更新后的访问权限配置字典
        """
        agent = await self.repo.get_by_id(agent_id)
        if not agent:
            raise NotFoundException(message=_("agent.error.not_found"))

        allowed = frozenset({"admin_role_ids", "tenant_role_ids"})
        data = {k: v for k, v in patch.items() if k in allowed}

        # Upsert AgentAccess / 插入或更新访问记录 / upsert access row
        access_repo = self._get_access_repo()
        access = await access_repo.upsert(agent_id, data)

        logger.info(
            "Agent access updated: agent_id={} tenant_id={}",
            agent_id, self.tenant_id,
        )

        return {
            "agent_id": agent_id,
            "admin_role_ids": getattr(access, "admin_role_ids", None),
            "tenant_role_ids": getattr(access, "tenant_role_ids", None),
        }

    async def get_publication_config(self, agent_id: int) -> dict[str, Any]:
        """获取企业用户发布配置 / Get tenant-user publication config."""
        agent = await self.repo.get_by_id(agent_id)
        if not agent:
            raise NotFoundException(message=_("agent.error.not_found"))

        publication_repo = self._get_publication_repo()
        publication = await publication_repo.get_by_agent_id(agent_id)

        return {
            "agent_id": agent_id,
            "publication_id": getattr(publication, "id", None),
            "enabled_for_users": bool(getattr(publication, "enabled_for_users", False)),
            "access_type": getattr(
                publication,
                "access_type",
                AgentPublicationAccessTypeEnum.ALL_USERS.value,
            ),
            "tenant_user_role_ids": getattr(publication, "tenant_user_role_ids", None),
            "tenant_user_ids": getattr(publication, "tenant_user_ids", None),
            "org_node_ids": getattr(publication, "org_node_ids", None),
            "published_at": (
                publication.published_at.isoformat()
                if publication and publication.published_at
                else None
            ),
            "published_by": getattr(publication, "published_by", None),
        }

    async def update_publication_config(
        self,
        agent_id: int,
        *,
        enabled_for_users: bool,
        access_type: str,
        tenant_user_role_ids: list[int] | None = None,
        tenant_user_ids: list[int] | None = None,
        org_node_ids: list[int] | None = None,
        published_by: int | None = None,
    ) -> dict[str, Any]:
        """更新企业用户发布配置 / Update tenant-user publication config."""
        agent = await self.repo.get_by_id(agent_id)
        if not agent:
            raise NotFoundException(message=_("agent.error.not_found"))

        if (
            bool(enabled_for_users)
            and access_type == AgentPublicationAccessTypeEnum.ORG_NODE.value
        ):
            raise BusinessException(
                message=_("agent.error.publication_org_node_not_supported"),
            )

        publication_repo = self._get_publication_repo()
        await publication_repo.upsert(
            agent_id,
            {
                "enabled_for_users": bool(enabled_for_users),
                "access_type": access_type,
                "tenant_user_role_ids": tenant_user_role_ids,
                "tenant_user_ids": tenant_user_ids,
                "org_node_ids": org_node_ids,
                "published_at": utc_now() if enabled_for_users else None,
                "published_by": published_by if enabled_for_users else None,
            },
        )

        return await self.get_publication_config(agent_id)

    def _publication_allows_user(
        self,
        publication: Any | None,
        *,
        user_id: int,
        user_role_id: int | None = None,
    ) -> bool:
        """判断企业用户发布规则是否允许当前用户 / Check whether publication allows current tenant user."""
        if not publication or not getattr(publication, "enabled_for_users", False):
            return False

        access_type = getattr(
            publication,
            "access_type",
            AgentPublicationAccessTypeEnum.ALL_USERS.value,
        )
        if access_type == AgentPublicationAccessTypeEnum.ALL_USERS.value:
            return True
        if access_type == AgentPublicationAccessTypeEnum.SPECIFIC_USERS.value:
            return user_id in (getattr(publication, "tenant_user_ids", None) or [])
        if access_type == AgentPublicationAccessTypeEnum.TENANT_USER_ROLES.value:
            return _role_ids_allow(
                getattr(publication, "tenant_user_role_ids", None),
                user_role_id,
            )
        if access_type == AgentPublicationAccessTypeEnum.ORG_NODE.value:
            # 当前企业用户模型暂未提供可直接复用的组织节点关联，因此先严格拒绝， / Tenant user model has no reusable org-node link yet; reject strictly for now,
            # 避免出现“配置了组织节点但实际放行全部用户”的错误语义。 / Avoid wrong semantics: org node configured but all users allowed
            return False
        return False

    async def check_user_access(
        self,
        agent_id: int,
        user_id: int,
        user_role: str = UserRoleEnum.TENANT_USER.value,
        user_role_id: int | None = None,
    ) -> bool:
        """
        检查用户是否有权访问指定智能体 / Check if user can access agent.

        访问语义：
        1. 平台管理员：仅检查 admin_role_ids
        2. 企业管理员：仅检查 tenant_role_ids
        3. 企业用户：必须存在启用中的 TenantAgentPublication，并通过发布规则校验

        Args:
            agent_id: 智能体 ID
            user_id: 当前用户 ID
            user_role: 调用方角色（UserRoleEnum 值）
            user_role_id: 用户的角色 ID（用于 *_role_ids 校验，None 则跳过角色过滤）

        Returns:
            是否有访问权限
        """
        agent = await self.repo.get_by_id(agent_id)
        if not agent:
            raise NotFoundException(message=_("agent.error.not_found"))

        if user_role == UserRoleEnum.PLATFORM_ADMIN.value:
            access = await self._get_access_repo().get_by_agent_id(agent_id)
            return _role_ids_allow(
                getattr(access, "admin_role_ids", None) if access else None,
                user_role_id,
            )

        if user_role == UserRoleEnum.TENANT_ADMIN.value:
            access = await self._get_access_repo().get_by_agent_id(agent_id)
            return _role_ids_allow(
                getattr(access, "tenant_role_ids", None) if access else None,
                user_role_id,
            )

        publication = await self._get_publication_repo().get_by_agent_id(agent_id)
        return self._publication_allows_user(
            publication,
            user_id=user_id,
            user_role_id=user_role_id,
        )

    async def list_user_accessible_agents(
        self,
        user_id: int,
        user_role_id: int | None,
        spec: "QuerySpec",
    ) -> tuple[list[Agent], int]:
        """
        获取终端用户可访问的智能体列表 / List agents accessible to end user.

        在 SQL 层完成全部过滤（status/execution_mode/visibility/access_type），
        保证分页和 total 计数的正确性。

        Args:
            user_id: 当前终端用户 ID
            spec: JSON:API 查询参数

        Returns:
            (items, total)
        """
        return await self.repo.query_user_accessible_list(
            spec=spec,
            user_id=user_id,
            user_role_id=user_role_id,
        )

    async def build_usage_attribution_context(
        self,
        *,
        agent: Agent,
        user_id: int | None,
        user_role: str,
        user_role_id: int | None = None,
    ) -> dict[str, Any]:
        """构建调用时不可变计费归属上下文 / Build immutable billing attribution context at call time."""
        publication = None
        billing_tenant_id = None
        access_channel = None

        if user_role == UserRoleEnum.TENANT_ADMIN.value:
            billing_tenant_id = self.tenant_id
            access_channel = CallAccessChannelEnum.TENANT_ADMIN.value
        elif user_role == UserRoleEnum.TENANT_USER.value:
            billing_tenant_id = self.tenant_id
            access_channel = CallAccessChannelEnum.TENANT_USER.value
            publication = await self._get_publication_repo().get_by_agent_id(agent.id)
            if not self._publication_allows_user(
                publication,
                user_id=user_id or 0,
                user_role_id=user_role_id,
            ):
                raise BusinessException(message=_("agent.access.error.no_permission"))
        else:
            access_channel = CallAccessChannelEnum.ADMIN_INTERNAL.value

        from sqlalchemy import select

        from app.models.tenant.tenant import Tenant

        billing_tenant_name_snapshot = None
        if billing_tenant_id is not None:
            row = await self.db.execute(
                select(Tenant.name).where(Tenant.id == billing_tenant_id).limit(1),
            )
            billing_tenant_name_snapshot = row.scalar_one_or_none()

        _own_tid = getattr(agent, "owner_tenant_id", None)
        return {
            "billing_tenant_id": billing_tenant_id,
            "actor_user_id": user_id,
            "actor_user_type": user_role,
            "access_channel": access_channel,
            "agent_owner_type": ("platform" if _own_tid is None else "tenant"),
            "agent_owner_tenant_id": _own_tid,
            "agent_resource_scope": getattr(agent, "scope", None),
            "tenant_publication_id": getattr(publication, "id", None) if publication else None,
            "publication_enabled_snapshot": (
                bool(getattr(publication, "enabled_for_users", False))
                if publication is not None
                else None
            ),
            "publication_access_type_snapshot": (
                getattr(publication, "access_type", None)
                if publication is not None
                else None
            ),
            "agent_id_snapshot": agent.id,
            "agent_name_snapshot": getattr(agent, "name", None),
            "billing_tenant_name_snapshot": billing_tenant_name_snapshot,
        }


class AdminAgentService(GlobalService[Agent, AdminAgentRepository]):
    """
    平台管理端智能体 Service / Admin agent service.

    提供跨企业的智能体列表查询、CRUD 和状态管理
    """

    model = Agent
    repository_class = AdminAgentRepository

    @staticmethod
    def _validate_resource_scope(scope: str | None) -> str:
        allowed = {e.value for e in ResourceScopeEnum}
        val = scope or ResourceScopeEnum.GLOBAL_SHARED.value
        if val not in allowed:
            raise BusinessException(message=_("agent.error.invalid_scope"))
        return val

    async def _get_platform_default_memory_enabled(self) -> bool:
        """获取平台默认记忆开关（默认 True） / Get platform default memory enabled (default True)."""
        config_service = ConfigService(self.db)
        value = await config_service.get_platform_config(
            "platform_default_memory_enabled",
            default=True,
        )
        return bool(value)

    async def get_memory_config(self, agent_id: int) -> dict[str, Any]:
        """
        获取管理端智能体记忆配置状态 / Get admin-side agent memory config.
        """
        agent = await self.repo.get_by_id(agent_id)
        if not agent:
            raise NotFoundException(message=_("agent.error.not_found"))

        platform_enabled = await self._get_platform_default_memory_enabled()
        admin_agent_enabled = bool(getattr(agent, "memory_enabled", True))
        effective = platform_enabled and admin_agent_enabled

        return {
            "agent_id": agent_id,
            "platform_default_memory_enabled": platform_enabled,
            "admin_agent_memory_enabled": admin_agent_enabled,
            "tenant_agent_memory_disabled": False,
            "effective_memory_enabled": effective,
        }

    async def set_memory_enabled(
        self,
        agent_id: int,
        enabled: bool,
    ) -> dict[str, Any]:
        """
        设置管理端 Agent 级记忆开关 / Set admin-side agent-level memory toggle.
        """
        agent = await self.repo.get_by_id(agent_id)
        if not agent:
            raise NotFoundException(message=_("agent.error.not_found"))

        await self.repo.update(agent_id, {"memory_enabled": bool(enabled)})
        return await self.get_memory_config(agent_id)

    async def _before_create(self, data: dict[str, Any]) -> None:
        """创建前校验：平台级资源 + 资源作用域 + 名称唯一性 / Before create: platform resource, scope, name uniqueness."""
        await super()._before_create(data)

        data["owner_tenant_id"] = None
        for rejected in ("owner_type", "distribution_mode"):
            if rejected in data:
                raise BusinessException(message=_("agent.error.rejected_legacy_field").format(field=rejected))
        data.pop("tenant_id", None)
        data["scope"] = self._validate_resource_scope(data.get("scope"))
        data.pop("tenant_ids", None)
        if "rag_config" in data:
            data["rag_config"] = _normalize_agent_rag_config(data.get("rag_config"))

        name = data.get("name")
        if name:
            existing = await self.repo.exists_by_name(
                name,
                owner_tenant_id=None,
            )
            if existing:
                raise BusinessException(message=_("agent.error.name_exists"))

        await _validate_agent_max_tokens_against_model(
            self.db,
            model_id=data.get("model_id"),
            max_tokens=data.get("max_tokens"),
        )

    async def _before_update(self, id: int, data: dict[str, Any]) -> None:
        """更新前校验：平台级资源 + 作用域 + 名称唯一性 + 系统保护 / Before update: platform resource, scope, name uniqueness, system protection."""
        await super()._before_update(id, data)

        agent = await self.repo.get_by_id(id)
        if not agent:
            raise NotFoundException(message=_("agent.error.not_found"))

        if agent.owner_tenant_id is not None:
            raise BusinessException(message=_("agent.error.system_protected"))

        # 系统智能体不允许修改关键字段 / System agents cannot change critical fields
        if agent.is_system:
            protected = {
                "is_system",
                "status",
                "execution_mode",
                "owner_type",
                "tenant_id",
                "owner_tenant_id",
            }
            if protected & set(data.keys()):
                raise BusinessException(message=_("agent.error.system_protected"))

        for rejected in ("owner_type", "distribution_mode"):
            if rejected in data:
                raise BusinessException(message=_("agent.error.rejected_legacy_field").format(field=rejected))
        data.pop("tenant_id", None)
        data.pop("owner_tenant_id", None)
        if "scope" in data and data["scope"] is not None:
            data["scope"] = self._validate_resource_scope(data["scope"])
        data.pop("tenant_ids", None)
        if "rag_config" in data:
            data["rag_config"] = _normalize_agent_rag_config(data.get("rag_config"))

        name = data.get("name")
        if name:
            existing = await self.repo.exists_by_name(
                name,
                owner_tenant_id=None,
                exclude_id=id,
            )
            if existing:
                raise BusinessException(message=_("agent.error.name_exists"))

        await _validate_agent_max_tokens_against_model(
            self.db,
            model_id=data.get("model_id", agent.model_id),
            max_tokens=data.get("max_tokens", agent.max_tokens),
        )

    async def query_list(self, query: QuerySpec) -> tuple[list[Agent], int]:
        """
        全企业智能体列表查询 / Query agent list (all tenants).

        Args:
            query: JSON:API QueryParams

        Returns:
            (items, total)
        """
        return await self.repo.query_list(query)

    async def _before_delete(self, id: int) -> None:
        """删除前校验：系统智能体不可删除，级联软删除对话，清理企业分配 / Before delete: system protected, cascade conversations, clear assignments."""
        await super()._before_delete(id)
        agent = await self.repo.get_by_id(id)
        if not agent:
            raise NotFoundException(message=_("agent.error.not_found"))
        if agent.is_system:
            raise BusinessException(message=_("agent.error.system_protected"))

        conversation_targets = await self.repo.list_conversation_memory_cleanup_targets(
            id,
        )
        # 级联软删除智能体的对话记录 / Cascade soft-delete agent conversations
        await self.repo.cascade_soft_delete_conversations(id, self._default_delete_level)
        deleted_keys = await _clear_cascaded_conversation_memories(conversation_targets)
        if conversation_targets:
            logger.info(
                "Admin cascade conversation cleanup finished: agent_id={} conversations={} deleted_keys={}",
                id,
                len(conversation_targets),
                deleted_keys,
            )

        # 清理 resource_tenant_assignments 残留记录
        from app.repositories.system.resource_tenant_assignment_repository import (
            ResourceTenantAssignmentRepository,
        )
        rta_repo = ResourceTenantAssignmentRepository(self.db)
        await rta_repo.delete_all_for_resource("agent", id)

    async def promote_to_global(self, id: int) -> Agent | None:
        """推进到总回收站，级联推进对话记录 / Promote to global recycle bin and cascade conversations."""
        instance = await self.repo.promote_to_global_by_id(
            id,
            delete_level=self._default_delete_level,
        )
        if instance is None:
            return None

        await self.repo.cascade_promote_conversations(id)
        return instance

    async def _after_restore(self, instance: Agent) -> None:
        """恢复后：级联恢复对话记录 / After restore: cascade restore conversations."""
        await self.repo.cascade_restore_conversations(instance.id)

    def _get_platform_access_repo(self) -> AgentAccessRepository:
        """平台侧访问配置 Repository（tenant_id=0）/ Platform access config repository (tenant_id=0)."""
        return AgentAccessRepository(self.db, PLATFORM_TENANT_ID)

    async def get_access_config(self, agent_id: int) -> dict[str, Any]:
        """获取平台侧访问配置（仅 admin 角色）/ Get platform-side access config (admin roles only)."""
        agent = await self.repo.get_by_id(agent_id)
        if not agent:
            raise NotFoundException(message=_("agent.error.not_found"))

        access = await self._get_platform_access_repo().get_by_agent_id(agent_id)
        return {
            "agent_id": agent_id,
            "admin_role_ids": getattr(access, "admin_role_ids", None) if access else None,
            "tenant_role_ids": None,
        }

    async def update_access_config(
        self,
        agent_id: int,
        patch: dict[str, Any],
    ) -> dict[str, Any]:
        """更新平台侧访问配置（仅 admin 角色）/ Update platform-side access config (admin roles only)."""
        agent = await self.repo.get_by_id(agent_id)
        if not agent:
            raise NotFoundException(message=_("agent.error.not_found"))

        if agent.owner_tenant_id is not None:
            raise BusinessException(message=_("agent.error.system_protected"))

        allowed = frozenset({"admin_role_ids", "tenant_role_ids"})
        body = {"tenant_role_ids": None, **{k: v for k, v in patch.items() if k in allowed}}
        access = await self._get_platform_access_repo().upsert(agent_id, body)
        return {
            "agent_id": agent_id,
            "admin_role_ids": getattr(access, "admin_role_ids", None),
            "tenant_role_ids": None,
        }

    async def build_usage_attribution_context(
        self,
        *,
        agent: Agent,
        user_id: int | None,
        user_role: str,
        user_role_id: int | None = None,
    ) -> dict[str, Any]:
        """构建平台管理端调用的计费归属上下文 / Build billing attribution context for platform-admin calls."""
        _ = user_role_id
        _own_tid = getattr(agent, "owner_tenant_id", None)
        return {
            "billing_tenant_id": None,
            "actor_user_id": user_id,
            "actor_user_type": user_role,
            "access_channel": CallAccessChannelEnum.ADMIN_INTERNAL.value,
            "agent_owner_type": ("platform" if _own_tid is None else "tenant"),
            "agent_owner_tenant_id": _own_tid,
            "agent_resource_scope": getattr(agent, "scope", None),
            "tenant_publication_id": None,
            "publication_enabled_snapshot": None,
            "publication_access_type_snapshot": None,
            "agent_id_snapshot": agent.id,
            "agent_name_snapshot": getattr(agent, "name", None),
            "billing_tenant_name_snapshot": None,
        }

    async def update_status(self, agent_id: int, status: str) -> Agent:
        """
        更新智能体状态（含状态机校验）/ Update agent status (with state machine check).

        Args:
            agent_id: 智能体 ID
            status: 目标状态

        Returns:
            更新后的 Agent 实例

        Raises:
            NotFoundException: 智能体不存在
            BusinessException: 无效状态
        """
        valid_statuses = {e.value for e in AgentStatusEnum}
        if status not in valid_statuses:
            raise BusinessException(message=_("agent.error.invalid_status"))

        agent = await self.repo.get_by_id(agent_id)
        if not agent:
            raise NotFoundException(message=_("agent.error.not_found"))

        if agent.is_system:
            raise BusinessException(message=_("agent.error.system_protected"))

        # 状态机校验：disabled 只能从 published 转入
        if (
            status == AgentStatusEnum.DISABLED.value
            and agent.status not in (
                AgentStatusEnum.PUBLISHED.value,
                AgentStatusEnum.DISABLED.value,
            )
        ):
            raise BusinessException(message=_("agent.error.invalid_status_transition"))

        updated = await self.repo.update(agent_id, {"status": status})

        logger.info(
            "Agent admin status updated: agent_id={} status={}",
            agent_id, status,
        )

        return updated


__all__ = ["AgentService", "AdminAgentService"]
