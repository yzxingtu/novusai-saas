"""
智能体 Service
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.schemas.common.query import QuerySpec

from app.configs.service import ConfigService
from app.core.base_service import GlobalService, TenantService
from app.core.i18n import _
from app.core.logging import LogManager
from app.enums.agent import AccessTypeEnum, AgentStatusEnum, AgentVisibilityEnum
from app.exceptions import BusinessException, NotFoundException
from app.models.ai.agent import Agent
from app.repositories.ai.agent_access_repository import AgentAccessRepository
from app.repositories.ai.agent_memory_override_repository import (
    AgentMemoryOverrideRepository,
)
from app.repositories.ai.agent_repository import AdminAgentRepository, AgentRepository
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
    "context_config",
    "output_schema",
    # NOTE: tool_bindings / knowledge_base_ids / rag_config removed —
    # replaced by AgentSkillBinding architecture (SkillPackage-based)
]


class AgentService(TenantService[Agent, AgentRepository]):
    """
    智能体 Service

    提供智能体的创建、更新、发布、回滚等业务逻辑
    """

    model = Agent
    repository_class = AgentRepository

    def _get_version_repo(self) -> AgentVersionRepository:
        """获取版本 Repository"""
        return AgentVersionRepository(self.db, self.tenant_id)

    async def _snapshot_skill_bindings(self, agent_id: int) -> list[dict[str, Any]]:
        """快照当前 Agent 的技能绑定列表（用于版本发布）"""
        from sqlalchemy import select

        from app.models.ai.agent_skill_binding import AgentSkillBinding

        result = await self.db.execute(
            select(AgentSkillBinding).where(
                AgentSkillBinding.agent_id == agent_id,
                AgentSkillBinding.is_deleted.is_(False),
            ).order_by(AgentSkillBinding.sort_order),
        )
        bindings = result.scalars().all()

        return [
            {
                "package_id": b.package_id,
                "package_name": b.package.name if b.package else None,
                "enabled": b.enabled,
                "consent_mode": b.consent_mode,
                "skill_consent_overrides": b.skill_consent_overrides,
                "sort_order": b.sort_order,
                "config_override": b.config_override,
            }
            for b in bindings
        ]

    async def _restore_skill_bindings(
        self,
        agent_id: int,
        bindings_snapshot: list[dict[str, Any]] | None,
    ) -> None:
        """从版本快照恢复技能绑定（用于版本回滚）"""
        if bindings_snapshot is None:
            return

        from app.services.ai.agent_skill_binding_service import AgentSkillBindingService
        binding_svc = AgentSkillBindingService(self.db, self.tenant_id)

        # 删除当前所有绑定
        await binding_svc.delete_all_for_agent(agent_id)

        # 从快照重建绑定（跳过已删除的技能包）
        from app.models.ai.skill_package import SkillPackage
        for item in bindings_snapshot:
            pkg_id = item.get("package_id")
            if not pkg_id:
                continue
            pkg = await self.db.get(SkillPackage, pkg_id)
            if not pkg or pkg.is_deleted:
                logger.warning(
                    "Skipping deleted package %d during rollback for agent %d",
                    pkg_id, agent_id,
                )
                continue

            await binding_svc.create({
                "agent_id": agent_id,
                "package_id": pkg_id,
                "tenant_id": self.tenant_id,
                "enabled": item.get("enabled", True),
                "consent_mode": item.get("consent_mode", "auto"),
                "skill_consent_overrides": item.get("skill_consent_overrides"),
                "sort_order": item.get("sort_order", 0),
                "config_override": item.get("config_override"),
            })

    def _get_access_repo(self) -> AgentAccessRepository:
        """获取访问权限 Repository"""
        return AgentAccessRepository(self.db, self.tenant_id)

    def _get_memory_override_repo(self) -> AgentMemoryOverrideRepository:
        """获取租户记忆开关覆盖 Repository"""
        return AgentMemoryOverrideRepository(self.db, self.tenant_id)

    async def _get_platform_default_memory_enabled(self) -> bool:
        """获取平台默认记忆开关（默认 True）"""
        config_service = ConfigService(self.db)
        value = await config_service.get_platform_config(
            "platform_default_memory_enabled",
            default=True,
        )
        return bool(value)

    async def resolve_memory_effective_config(self, agent_id: int) -> dict[str, bool]:
        """
        计算智能体记忆最终生效状态（租户侧）

        规则：
            effective = platform_default_memory_enabled
                        AND admin_agent_memory_enabled
                        AND (NOT tenant_agent_memory_disabled)
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
        获取租户侧智能体记忆配置状态
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
        设置租户侧“关闭记忆”覆盖（仅支持关闭/恢复默认）
        """
        agent = await self.repo.get_by_id(agent_id)
        if not agent:
            raise NotFoundException(message=_("agent.error.not_found"))

        # 租户端仅允许操作自有 agent；全局/系统 agent 不允许覆盖
        if agent.tenant_id != self.tenant_id:
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
        """创建前校验：名称唯一性 + 插件钩子"""
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

        name = data.get("name")
        if name:
            existing = await self.repo.get_by_name(name)
            if existing:
                raise BusinessException(message=_("agent.error.name_exists"))

    async def _after_create(self, instance: Agent) -> None:
        """创建后：触发插件钩子"""
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
        """更新前校验：名称唯一性、系统智能体保护 + 插件钩子"""
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

        # 租户端只能修改自有智能体（即 tenant_id 与当前租户匹配）
        if agent.tenant_id != self.tenant_id:
            raise BusinessException(message=_("agent.error.system_protected"))

        if agent.is_system:
            protected = {"is_system", "status", "scope", "execution_mode"}
            if protected & set(data.keys()):
                raise BusinessException(message=_("agent.error.system_protected"))

        name = data.get("name")
        if name:
            existing = await self.repo.get_by_name(name, exclude_id=id)
            if existing:
                raise BusinessException(message=_("agent.error.name_exists"))

    async def _after_update(self, instance: Agent) -> None:
        """更新后：触发插件钩子"""
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
        """删除前校验：系统智能体不可删除，级联软删除对话 + 插件钩子"""
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

        # 租户端只能删除自有智能体（即 tenant_id 与当前租户匹配）
        if agent.tenant_id != self.tenant_id:
            raise BusinessException(message=_("agent.error.system_protected"))

        if agent.is_system:
            raise BusinessException(message=_("agent.error.system_protected"))

        # 级联软删除智能体的对话记录
        await self.repo.cascade_soft_delete_conversations(id, self._default_delete_level)

    async def _after_delete(self, instance: Agent) -> None:
        """删除后：触发插件钩子"""
        await super()._after_delete(instance)
        from app.ai.events.hooks import HookPoint, get_hook_registry
        hook_registry = get_hook_registry()
        if hook_registry.has_hooks(HookPoint.AFTER_AGENT_DELETE):
            await hook_registry.trigger(
                HookPoint.AFTER_AGENT_DELETE,
                tenant_id=self.tenant_id,
                agent_id=instance.id,
            )

    async def escalate_delete(self, id: int) -> Agent | None:
        """升级删除层级，级联升级对话记录"""
        instance = await self.repo.escalate_delete_by_id(id)
        if instance is None:
            return None

        await self.repo.cascade_escalate_conversations(id)
        return instance

    async def _after_restore(self, instance: Agent) -> None:
        """恢复后：级联恢复对话记录"""
        await self.repo.cascade_restore_conversations(instance.id)

    async def get_agent_detail(self, agent_id: int) -> dict[str, Any]:
        """
        获取智能体详情（含关联模型信息）

        Args:
            agent_id: 智能体 ID

        Returns:
            包含模型名称/代码的智能体字典
        """
        agent = await self.repo.get_by_id(agent_id)
        if not agent:
            raise NotFoundException(message=_("agent.error.not_found"))

        # 构建响应字典
        result = agent.to_dict()
        result["model_name"] = None
        result["model_code"] = None

        try:
            model_obj = getattr(agent, "model", None)
            if model_obj is not None:
                result["model_name"] = model_obj.name
                result["model_code"] = model_obj.code
        except AttributeError:
            pass

        # 附加记忆开关计算结果（租户服务）
        resolved = await self.resolve_memory_effective_config(agent_id)
        result["memory_enabled"] = bool(getattr(agent, "memory_enabled", True))
        result["effective_memory_enabled"] = resolved["effective_memory_enabled"]
        result["memory_disabled_by_tenant"] = resolved["tenant_agent_memory_disabled"]

        return result

    # ========================================
    # 版本管理
    # ========================================

    async def publish_agent(
        self,
        agent_id: int,
        change_log: str | None = None,
        created_by: int | None = None,
    ) -> Agent:
        """
        发布智能体

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

        # 计算新版本号
        version_repo = self._get_version_repo()
        latest_version = await version_repo.get_latest_version_number(agent_id)
        new_version = latest_version + 1

        # 创建版本快照
        version_data: dict[str, Any] = {
            "agent_id": agent_id,
            "version": new_version,
            "tenant_id": self.tenant_id,
            "change_log": change_log,
            "created_by": created_by,
        }
        for field_name in _VERSION_SNAPSHOT_FIELDS:
            version_data[field_name] = getattr(agent, field_name)

        # 快照包含技能绑定信息
        version_data["tool_bindings"] = await self._snapshot_skill_bindings(agent_id)

        await version_repo.create(version_data)

        # 更新 Agent 状态
        updated = await self.repo.update(agent_id, {
            "status": AgentStatusEnum.PUBLISHED.value,
            "published_version": new_version,
        })

        logger.info(
            "Agent published: agent_id=%s tenant_id=%s version=%s",
            agent_id, self.tenant_id, new_version,
        )

        return updated

    async def rollback_agent(
        self,
        agent_id: int,
        version: int,
    ) -> Agent:
        """
        回滚智能体到指定版本

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

        # 恢复技能绑定
        await self._restore_skill_bindings(
            agent_id, version_record.tool_bindings,
        )

        logger.info(
            "Agent rolled back: agent_id=%s tenant_id=%s version=%s",
            agent_id, self.tenant_id, version,
        )

        return updated

    async def get_versions(
        self,
        agent_id: int,
    ) -> list[dict[str, Any]]:
        """
        获取智能体版本历史列表

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
        获取智能体版本详情

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
        对比两个版本的字段差异

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

        # 对比快照字段
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
    # 访问权限管理
    # ========================================

    async def get_access_config(self, agent_id: int) -> dict[str, Any]:
        """
        获取智能体访问权限配置

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
            "visibility": agent.visibility or AgentVisibilityEnum.PUBLIC.value,
            "access_type": access.access_type if access else AccessTypeEnum.ALL_USERS.value,
            "org_node_ids": access.org_node_ids if access else None,
            "user_ids": access.user_ids if access else None,
        }

    async def update_access_config(
        self,
        agent_id: int,
        visibility: str,
        access_type: str,
        org_node_ids: list[int] | None = None,
        user_ids: list[int] | None = None,
    ) -> dict[str, Any]:
        """
        更新智能体访问权限配置

        同时更新 Agent.visibility 和 AgentAccess 记录。

        Args:
            agent_id: 智能体 ID
            visibility: 可见性（public / private）
            access_type: 访问类型
            org_node_ids: 组织节点 ID 列表
            user_ids: 用户 ID 列表

        Returns:
            更新后的访问权限配置字典
        """
        agent = await self.repo.get_by_id(agent_id)
        if not agent:
            raise NotFoundException(message=_("agent.error.not_found"))

        # 更新 Agent.visibility
        await self.repo.update(agent_id, {"visibility": visibility})

        # Upsert AgentAccess
        access_repo = self._get_access_repo()
        access = await access_repo.upsert(agent_id, {
            "access_type": access_type,
            "org_node_ids": org_node_ids,
            "user_ids": user_ids,
        })

        logger.info(
            "Agent access updated: agent_id=%s tenant_id=%s visibility=%s access_type=%s",
            agent_id, self.tenant_id, visibility, access_type,
        )

        return {
            "agent_id": agent_id,
            "visibility": visibility,
            "access_type": access.access_type,
            "org_node_ids": access.org_node_ids,
            "user_ids": access.user_ids,
        }

    async def check_user_access(
        self,
        agent_id: int,
        user_id: int,
        user_org_node_ids: list[int] | None = None,
    ) -> bool:
        """
        检查用户是否有权访问指定智能体

        规则:
        - visibility=public → 所有人可访问
        - visibility=private + access_type=all_users → 所有登录用户可访问
        - visibility=private + access_type=org_node → 用户所属组织节点匹配
        - visibility=private + access_type=specific_users → 用户 ID 在列表中
        - visibility=private + access_type=api_only → 仅 API 调用可访问，用户不可

        Args:
            agent_id: 智能体 ID
            user_id: 当前用户 ID
            user_org_node_ids: 用户所属组织节点 ID 列表

        Returns:
            是否有访问权限
        """
        agent = await self.repo.get_by_id(agent_id)
        if not agent:
            raise NotFoundException(message=_("agent.error.not_found"))

        # 公开智能体，所有人可访问
        if agent.visibility != AgentVisibilityEnum.PRIVATE.value:
            return True

        access_repo = self._get_access_repo()
        access = await access_repo.get_by_agent_id(agent_id)
        if not access:
            # 无 access 记录时，默认 all_users
            return True

        access_type = access.access_type

        if access_type == AccessTypeEnum.ALL_USERS.value:
            return True

        if access_type == AccessTypeEnum.ORG_NODE.value:
            if not access.org_node_ids or not user_org_node_ids:
                return False
            return bool(set(user_org_node_ids) & set(access.org_node_ids))

        if access_type == AccessTypeEnum.SPECIFIC_USERS.value:
            if not access.user_ids:
                return False
            return user_id in access.user_ids

        if access_type == AccessTypeEnum.API_ONLY.value:
            return False

        return False

    async def list_user_accessible_agents(
        self,
        user_id: int,
        spec: "QuerySpec",
    ) -> tuple[list[Agent], int]:
        """
        获取终端用户可访问的智能体列表

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
        )


class AdminAgentService(GlobalService[Agent, AdminAgentRepository]):
    """
    平台管理端智能体 Service

    提供跨租户的智能体列表查询、CRUD 和状态管理
    """

    model = Agent
    repository_class = AdminAgentRepository

    async def _get_platform_default_memory_enabled(self) -> bool:
        """获取平台默认记忆开关（默认 True）"""
        config_service = ConfigService(self.db)
        value = await config_service.get_platform_config(
            "platform_default_memory_enabled",
            default=True,
        )
        return bool(value)

    async def get_memory_config(self, agent_id: int) -> dict[str, Any]:
        """
        获取管理端智能体记忆配置状态
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
        设置管理端 Agent 级记忆开关
        """
        agent = await self.repo.get_by_id(agent_id)
        if not agent:
            raise NotFoundException(message=_("agent.error.not_found"))

        await self.repo.update(agent_id, {"memory_enabled": bool(enabled)})
        return await self.get_memory_config(agent_id)

    async def _before_create(self, data: dict[str, Any]) -> None:
        """创建前校验：scope + tenant_id 一致性、名称唯一性"""
        await super()._before_create(data)

        from app.enums.common import ResourceScopeEnum

        scope = data.get("scope", ResourceScopeEnum.ADMIN_AND_ALL.value)

        # all_tenants 现在表示对全部租户可见，无需指定具体租户
        data["tenant_id"] = None

        # tenant_ids 不是模型字段，由 Controller 通过 resource_tenant_assignments 处理
        data.pop("tenant_ids", None)

        name = data.get("name")
        if name:
            existing = await self.repo.exists_by_name(name, tenant_id=None, scope=scope)
            if existing:
                raise BusinessException(message=_("agent.error.name_exists"))

    async def _before_update(self, id: int, data: dict[str, Any]) -> None:
        """更新前校验：scope 变更时的一致性、名称唯一性、系统智能体保护"""
        await super()._before_update(id, data)

        agent = await self.repo.get_by_id(id)
        if not agent:
            raise NotFoundException(message=_("agent.error.not_found"))

        # 系统智能体不允许修改关键字段
        if agent.is_system:
            protected = {"is_system", "status", "scope", "execution_mode"}
            if protected & set(data.keys()):
                raise BusinessException(message=_("agent.error.system_protected"))

        scope = data.get("scope", agent.scope)

        # all_tenants 现在表示对全部租户可见，无需指定具体租户
        data["tenant_id"] = None

        # tenant_ids 不是模型字段，由 Controller 通过 resource_tenant_assignments 处理
        data.pop("tenant_ids", None)

        name = data.get("name")
        if name:
            existing = await self.repo.exists_by_name(name, tenant_id=None, scope=scope, exclude_id=id)
            if existing:
                raise BusinessException(message=_("agent.error.name_exists"))

    async def query_list(self, query: QuerySpec) -> tuple[list[Agent], int]:
        """
        全租户智能体列表查询

        Args:
            query: JSON:API QueryParams

        Returns:
            (items, total)
        """
        return await self.repo.query_list(query)

    async def _before_delete(self, id: int) -> None:
        """删除前校验：系统智能体不可删除，级联软删除对话，清理租户分配"""
        await super()._before_delete(id)
        agent = await self.repo.get_by_id(id)
        if not agent:
            raise NotFoundException(message=_("agent.error.not_found"))
        if agent.is_system:
            raise BusinessException(message=_("agent.error.system_protected"))

        # 级联软删除智能体的对话记录
        await self.repo.cascade_soft_delete_conversations(id, self._default_delete_level)

        # 清理 resource_tenant_assignments 残留记录
        from app.enums.common import ResourceScopeEnum
        if agent.scope in (
            ResourceScopeEnum.ASSIGNED_TENANTS.value,
            ResourceScopeEnum.ADMIN_AND_ASSIGNED.value,
        ):
            from app.repositories.system.resource_tenant_assignment_repository import (
                ResourceTenantAssignmentRepository,
            )
            rta_repo = ResourceTenantAssignmentRepository(self.db)
            await rta_repo.delete_all_for_resource("agent", id)

    async def update_status(self, agent_id: int, status: str) -> Agent:
        """
        更新智能体状态（含状态机校验）

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
            "Agent admin status updated: agent_id=%s status=%s",
            agent_id, status,
        )

        return updated


__all__ = ["AgentService", "AdminAgentService"]
