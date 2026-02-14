"""
智能体访问权限 Repository

提供 AgentAccess 的数据访问操作（基于租户隔离）
"""

from typing import Any

from sqlalchemy import select, and_

from app.core.base_repository import TenantRepository
from app.models.ai.agent_access import AgentAccess


class AgentAccessRepository(TenantRepository[AgentAccess]):
    """
    租户级智能体访问权限 Repository

    提供 get_by_agent_id 和 upsert（按 agent_id 创建或更新）
    """

    model = AgentAccess

    async def get_by_agent_id(self, agent_id: int) -> AgentAccess | None:
        """
        按智能体 ID 获取访问权限配置

        Args:
            agent_id: 智能体 ID

        Returns:
            AgentAccess 实例或 None
        """
        stmt = select(AgentAccess).where(
            and_(
                AgentAccess.tenant_id == self.tenant_id,
                AgentAccess.agent_id == agent_id,
                AgentAccess.is_deleted.is_(False),
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def upsert(self, agent_id: int, data: dict[str, Any]) -> AgentAccess:
        """
        创建或更新智能体访问权限配置

        如果该 agent_id 已有记录则更新，否则创建新记录。

        Args:
            agent_id: 智能体 ID
            data: 访问权限数据

        Returns:
            AgentAccess 实例
        """
        existing = await self.get_by_agent_id(agent_id)
        if existing:
            for key, value in data.items():
                setattr(existing, key, value)
            await self.db.flush()
            await self.db.refresh(existing)
            return existing

        # 新建
        create_data = {
            "agent_id": agent_id,
            **data,
        }
        return await self.create(create_data)


__all__ = ["AgentAccessRepository"]
