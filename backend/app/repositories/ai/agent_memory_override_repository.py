"""
智能体记忆开关覆盖 Repository / Agent Memory Override Repository
"""

from sqlalchemy import and_, select

from app.core.base_repository import TenantRepository
from app.models.ai.agent_memory_override import AgentMemoryOverride


class AgentMemoryOverrideRepository(TenantRepository[AgentMemoryOverride]):
    """
    企业级智能体记忆开关覆盖仓储 / Tenant agent memory override repository.
    """

    model = AgentMemoryOverride

    async def get_by_agent_id(self, agent_id: int) -> AgentMemoryOverride | None:
        """获取当前企业对指定 agent 的覆盖记录 / Get current tenant's override for agent."""
        result = await self.db.execute(
            select(self.model).where(
                and_(
                    self.model.tenant_id == self.tenant_id,
                    self.model.agent_id == agent_id,
                    self.model.is_deleted.is_(False),
                )
            )
        )
        return result.scalar_one_or_none()
