"""
系统智能体绑定服务

提供系统智能体绑定的业务逻辑
"""

from typing import Any

from app.core.base_service import GlobalService
from app.core.i18n import _
from app.core.logging import LogManager
from app.exceptions import ConflictException, NotFoundException
from app.models.system.agent_assignment import SystemAgentAssignment
from app.repositories.system.agent_assignment_repository import AgentAssignmentRepository

logger = LogManager.get_logger("app")


class AgentAssignmentService(GlobalService[SystemAgentAssignment, AgentAssignmentRepository]):
    """
    系统智能体绑定服务
    """

    model = SystemAgentAssignment
    repository_class = AgentAssignmentRepository

    async def _before_create(self, data: dict[str, Any]) -> dict[str, Any]:
        """创建前校验 feature_code + tenant_id 唯一"""
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
        全局 resolve：返回启用的全局默认绑定
        """
        return await self.repo.get_active_by_feature_code(feature_code)

    async def resolve_for_tenant(
        self, feature_code: str, tenant_id: int
    ) -> SystemAgentAssignment | None:
        """
        租户 resolve：先查租户覆盖，未找到则 fallback 到全局默认
        """
        return await self.repo.resolve_for_tenant(feature_code, tenant_id)

    async def get_all_global(self) -> list[SystemAgentAssignment]:
        """获取所有全局默认绑定"""
        return await self.repo.get_all_global()

    async def get_all_for_tenant(self, tenant_id: int) -> list[SystemAgentAssignment]:
        """获取租户的所有覆盖绑定"""
        return await self.repo.get_all_for_tenant(tenant_id)

    async def set_tenant_override(
        self, feature_code: str, tenant_id: int, agent_id: int | None, config: dict | None = None
    ) -> SystemAgentAssignment:
        """
        创建或更新租户覆盖绑定
        """
        existing = await self.repo.get_tenant_override(feature_code, tenant_id)
        if existing:
            update_data: dict[str, Any] = {"agent_id": agent_id}
            if config is not None:
                update_data["config"] = config
            return await self.update(existing.id, update_data)

        # Verify the feature_code exists as a global default
        global_default = await self.repo.get_by_feature_code(feature_code)
        if not global_default:
            raise NotFoundException(
                message=_("system_agent_assignment.error.not_found"),
            )

        return await self.create({
            "feature_code": feature_code,
            "feature_name": global_default.feature_name,
            "description": global_default.description,
            "tenant_id": tenant_id,
            "agent_id": agent_id,
            "config": config,
            "is_active": True,
        })

    async def delete_tenant_override(self, feature_code: str, tenant_id: int) -> bool:
        """删除租户覆盖（恢复全局默认）"""
        existing = await self.repo.get_tenant_override(feature_code, tenant_id)
        if not existing:
            return False
        await self.delete(existing.id)
        return True


__all__ = ["AgentAssignmentService"]
