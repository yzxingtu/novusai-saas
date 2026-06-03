"""
企业停用平台知识库绑定 Repository / Tenant platform KB suppression repository
"""

from sqlalchemy import and_, select

from app.core.base_repository import TenantRepository
from app.models.ai.tenant_agent_platform_kb_suppression import (
    TenantAgentPlatformKbSuppression,
)


class TenantAgentPlatformKbSuppressionRepository(
    TenantRepository[TenantAgentPlatformKbSuppression]
):
    """按企业查询/维护平台 KB 停用记录 / Tenant-scoped suppression rows."""

    model = TenantAgentPlatformKbSuppression

    async def list_active_kb_ids(self, agent_id: int) -> set[int]:
        """当前企业对某 agent 已停用的平台 KB id 集合 / Active suppressed KB ids."""
        stmt = select(self.model.knowledge_base_id).where(
            and_(
                self.model.tenant_id == self.tenant_id,
                self.model.agent_id == agent_id,
                self.model.is_deleted.is_(False),
            )
        )
        result = await self.db.execute(stmt)
        return {int(r[0]) for r in result.all()}

    async def get_active_row(
        self, agent_id: int, knowledge_base_id: int
    ) -> TenantAgentPlatformKbSuppression | None:
        result = await self.db.execute(
            select(self.model).where(
                and_(
                    self.model.tenant_id == self.tenant_id,
                    self.model.agent_id == agent_id,
                    self.model.knowledge_base_id == knowledge_base_id,
                    self.model.is_deleted.is_(False),
                )
            )
        )
        return result.scalar_one_or_none()

    async def get_any_row(
        self, agent_id: int, knowledge_base_id: int
    ) -> TenantAgentPlatformKbSuppression | None:
        """含软删，用于恢复 / Include soft-deleted for restore."""
        result = await self.db.execute(
            select(self.model).where(
                and_(
                    self.model.tenant_id == self.tenant_id,
                    self.model.agent_id == agent_id,
                    self.model.knowledge_base_id == knowledge_base_id,
                )
            )
        )
        return result.scalar_one_or_none()


__all__ = ["TenantAgentPlatformKbSuppressionRepository"]
