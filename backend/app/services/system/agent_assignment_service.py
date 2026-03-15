"""
系统智能体绑定服务 / System Agent Assignment Service

提供系统智能体绑定的业务逻辑
Provides system agent assignment business logic.
"""

from typing import Any

from sqlalchemy.exc import IntegrityError

from app.core.base_service import GlobalService
from app.core.i18n import _
from app.core.logging import LogManager
from app.exceptions import (
    AuthorizationException,
    ConflictException,
    NotFoundException,
    ValidationException,
)
from app.models.system.agent_assignment import SystemAgentAssignment
from app.repositories.system.agent_assignment_repository import (
    AgentAssignmentRepository,
)

logger = LogManager.get_logger("app")


class AgentAssignmentService(GlobalService[SystemAgentAssignment, AgentAssignmentRepository]):
    """
    系统智能体绑定服务 / System agent assignment service.
    """

    model = SystemAgentAssignment
    repository_class = AgentAssignmentRepository

    async def validate_agent_id(
        self, agent_id: int | None, tenant_id: int | None = None
    ) -> None:
        """
        校验 agent_id 有效性：存在 + 已发布 + 对企业可见 / Validate agent_id: exists, published, visible to tenant.

        Args:
            agent_id: 要校验的智能体 ID，None 时跳过（清除绑定）
            tenant_id: 企业 ID，None 表示 admin 端（不做 scope 校验）
        """
        if agent_id is None:
            return

        from sqlalchemy import select

        from app.enums.common import ResourceScopeEnum
        from app.models.ai.agent import Agent

        result = await self.repo.db.execute(
            select(Agent.id, Agent.status, Agent.scope, Agent.tenant_id, Agent.target_audience).where(
                Agent.id == agent_id,
                Agent.is_deleted.is_(False),
            )
        )
        agent = result.one_or_none()
        if not agent:
            raise ValidationException(
                message=_("system_agent_assignment.error.agent_not_found"),
            )

        from app.enums.agent import AgentStatusEnum

        if agent.status != AgentStatusEnum.PUBLISHED.value:
            raise ValidationException(
                message=_("system_agent_assignment.error.agent_not_published"),
            )

        # admin 端不做 scope / target_audience 校验
        if tenant_id is None:
            return

        # 企业端校验 target_audience：企业端不能绑定 admin_only 的智能体
        from app.enums.common import AudienceEnum
        target_audience = getattr(agent, "target_audience", AudienceEnum.ADMIN_TENANT.value)
        if target_audience == AudienceEnum.ADMIN_ONLY.value:
            raise AuthorizationException(
                message=_("system_agent_assignment.error.agent_not_accessible"),
            )

        # 企业端校验 scope 可见性
        scope = agent.scope
        if scope in (
            ResourceScopeEnum.ADMIN_AND_ALL.value,
            ResourceScopeEnum.ALL_TENANTS.value,
        ):
            return  # 全局可见

        if scope == ResourceScopeEnum.ADMIN_ONLY.value:
            raise AuthorizationException(
                message=_("system_agent_assignment.error.agent_not_accessible"),
            )

        if agent.tenant_id == tenant_id:
            return  # 同企业

        # assigned scope：检查 ResourceTenantAssignment
        if scope in (
            ResourceScopeEnum.ADMIN_AND_ASSIGNED.value,
            ResourceScopeEnum.ASSIGNED_TENANTS.value,
        ):
            from app.repositories.system.resource_tenant_assignment_repository import (
                ResourceTenantAssignmentRepository,
            )

            rta_repo = ResourceTenantAssignmentRepository(self.repo.db)
            if await rta_repo.check_assignment("agent", agent_id, tenant_id):
                return

        raise AuthorizationException(
            message=_("system_agent_assignment.error.agent_not_accessible"),
        )

    async def _before_create(self, data: dict[str, Any]) -> dict[str, Any]:
        """创建前校验 feature_code + tenant_id 唯一 / Before create: ensure feature_code + tenant_id unique."""
        feature_code = data.get("feature_code", "")
        tenant_id = data.get("tenant_id")
        if tenant_id is not None:
            existing = await self.repo.get_tenant_override(feature_code, tenant_id)
        else:
            existing = await self.repo.get_by_feature_code(feature_code)
        if existing:
            raise ConflictException(
                message=_("system_agent_assignment.error.feature_code_exists"),
            )
        return data

    async def resolve(self, feature_code: str) -> SystemAgentAssignment | None:
        """
        全局 resolve：返回启用的全局默认绑定 / Resolve global: return active global default binding.
        """
        return await self.repo.get_active_by_feature_code(feature_code)

    async def resolve_for_tenant(
        self, feature_code: str, tenant_id: int
    ) -> SystemAgentAssignment | None:
        """
        企业 resolve：先查企业覆盖，未找到则 fallback 到全局默认 / Tenant resolve: tenant override first, then global default.
        """
        return await self.repo.resolve_for_tenant(feature_code, tenant_id)

    async def get_all_global(self) -> list[SystemAgentAssignment]:
        """获取所有全局默认绑定 / Get all global default bindings."""
        return await self.repo.get_all_global()

    async def get_all_for_tenant(self, tenant_id: int) -> list[SystemAgentAssignment]:
        """获取企业的所有覆盖绑定 / Get all tenant override bindings."""
        return await self.repo.get_all_for_tenant(tenant_id)

    async def set_tenant_override(
        self, feature_code: str, tenant_id: int, agent_id: int | None, config: dict | None = None
    ) -> SystemAgentAssignment:
        """
        创建或更新企业覆盖绑定 / Create or update tenant override binding.
        """
        await self.validate_agent_id(agent_id, tenant_id=tenant_id)

        existing = await self.repo.get_tenant_override(feature_code, tenant_id)
        if existing:
            update_data: dict[str, Any] = {"agent_id": agent_id}
            if config is not None:
                update_data["config"] = config
            # 同步全局默认的 feature_name / description（防止 rename 后 stale）
            global_default = await self.repo.get_by_feature_code(feature_code)
            if global_default:
                update_data["feature_name"] = global_default.feature_name
                update_data["description"] = global_default.description
            return await self.update(existing.id, update_data)

        # Verify the feature_code exists as a global default
        global_default = await self.repo.get_by_feature_code(feature_code)
        if not global_default:
            raise NotFoundException(
                message=_("system_agent_assignment.error.not_found"),
            )

        try:
            return await self.create({
                "feature_code": feature_code,
                "feature_name": global_default.feature_name,
                "description": global_default.description,
                "tenant_id": tenant_id,
                "agent_id": agent_id,
                "config": config,
                "is_active": True,
            })
        except IntegrityError:
            # 并发竞态：另一个请求已创建覆盖，回退后重试更新路径
            await self.repo.db.rollback()
            existing = await self.repo.get_tenant_override(feature_code, tenant_id)
            if existing:
                return await self.update(existing.id, {"agent_id": agent_id})
            raise ConflictException(
                message=_("system_agent_assignment.error.feature_code_exists"),
            )

    async def delete_tenant_override(self, feature_code: str, tenant_id: int) -> bool:
        """删除企业覆盖（恢复全局默认）/ Delete tenant override (restore to global default).

        使用硬删除，因为覆盖是配置记录而非用户数据，
        且 UniqueConstraint 不含 is_deleted 过滤，软删除后无法重建。
        """
        existing = await self.repo.get_tenant_override(feature_code, tenant_id)
        if not existing:
            return False
        await self.delete(existing.id, soft=False)
        return True


__all__ = ["AgentAssignmentService"]
