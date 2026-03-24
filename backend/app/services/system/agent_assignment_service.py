"""
系统智能体绑定服务 / System Agent Assignment Service

提供系统智能体绑定的业务逻辑
Provides system agent assignment business logic.
"""

from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.base_service import GlobalService
from app.core.i18n import _
from app.core.logging import LogManager
from app.enums.agent import AgentStatusEnum
from app.enums.common import ResourceScopeEnum
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
        self,
        agent_id: int | None,
        tenant_id: int | None = None,
        *,
        for_platform_feature_binding: bool = False,
    ) -> None:
        """
        校验 agent_id 有效性：存在 + 已发布 +（可选）平台功能绑定规则 + 对企业可见 / Validate agent_id: exists, published, optional platform binding rules, tenant visibility.

        Args:
            agent_id: 要校验的智能体 ID，None 时跳过（清除绑定）
            tenant_id: 企业 ID，None 表示非企业覆盖场景下的校验
            for_platform_feature_binding: True 时用于管理端「功能分配」全局绑定：
                只允许平台自有且对企业可分发的智能体
        """
        if agent_id is None:
            return

        from app.models.ai.agent import Agent

        result = await self.repo.db.execute(
            select(
                Agent.id,
                Agent.status,
                Agent.owner_tenant_id,
                Agent.scope,
            ).where(
                Agent.id == agent_id,
                Agent.is_deleted.is_(False),
            )
        )
        agent = result.one_or_none()
        if not agent:
            raise ValidationException(
                message=_("system_agent_assignment.error.agent_not_found"),
            )

        if agent.status != AgentStatusEnum.PUBLISHED.value:
            raise ValidationException(
                message=_("system_agent_assignment.error.agent_not_published"),
            )

        if for_platform_feature_binding:
            if agent.owner_tenant_id is not None:
                raise ValidationException(
                    message=_("system_agent_assignment.error.agent_must_be_platform_global"),
                )
            if agent.scope not in (
                ResourceScopeEnum.GLOBAL_SHARED.value,
                ResourceScopeEnum.ALL_TENANTS.value,
            ):
                raise ValidationException(
                    message=_("system_agent_assignment.error.agent_must_be_global_shared_scope"),
                )
            return

        # 非「平台功能分配」且未指定企业：仅校验存在 + 已发布（兼容其它调用方） / Non platform-feature assignment and no tenant: only verify exists + published (compat)
        if tenant_id is None:
            return

        if agent.owner_tenant_id == tenant_id:
            return

        if agent.owner_tenant_id is None and agent.scope in (
            ResourceScopeEnum.GLOBAL_SHARED.value,
            ResourceScopeEnum.ALL_TENANTS.value,
        ):
            return

        if agent.owner_tenant_id is None and agent.scope in (
            ResourceScopeEnum.ADMIN_AND_SELECTED_TENANTS.value,
            ResourceScopeEnum.SELECTED_TENANTS.value,
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

        # Verify the feature_code exists as a global default / 校验全局默认特性码 / verify global feature code
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
            # 并发竞态：另一个请求已创建覆盖，回退后重试更新路径 / Concurrency: another request created override; retry update path
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
