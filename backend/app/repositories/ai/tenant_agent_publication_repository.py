"""
Tenant agent publication repository / 企业智能体用户发布 Repository
"""

from typing import Any

from sqlalchemy import and_, select

from app.core.base_repository import TenantRepository
from app.models.ai.tenant_agent_publication import TenantAgentPublication


class TenantAgentPublicationRepository(TenantRepository[TenantAgentPublication]):
    """
    企业智能体用户发布 Repository / Tenant agent publication repository.

    提供按 agent_id 查询和 upsert 能力。
    """

    model = TenantAgentPublication

    async def get_by_agent_id(self, agent_id: int) -> TenantAgentPublication | None:
        stmt = select(TenantAgentPublication).where(
            and_(
                TenantAgentPublication.tenant_id == self.tenant_id,
                TenantAgentPublication.agent_id == agent_id,
                TenantAgentPublication.is_deleted.is_(False),
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def upsert(
        self,
        agent_id: int,
        data: dict[str, Any],
    ) -> TenantAgentPublication:
        existing = await self.get_by_agent_id(agent_id)
        if existing:
            for key, value in data.items():
                setattr(existing, key, value)
            await self.db.flush()
            await self.db.refresh(existing)
            return existing

        create_data = {
            "agent_id": agent_id,
            **data,
        }
        return await self.create(create_data)


__all__ = ["TenantAgentPublicationRepository"]
