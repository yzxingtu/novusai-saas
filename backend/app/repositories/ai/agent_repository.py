"""
智能体 Repository
"""

from typing import Optional, List

from sqlalchemy import select, and_

from app.models.ai.agent import Agent
from app.core.base_repository import TenantRepository, BaseRepository


class AgentRepository(TenantRepository[Agent]):
    """
    租户级智能体 Repository

    提供基于租户隔离的智能体数据访问
    """

    model = Agent

    async def get_by_status(
        self,
        status: str,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Agent]:
        """
        按状态获取智能体列表

        Args:
            status: 智能体状态
            skip: 跳过数量
            limit: 返回数量

        Returns:
            Agent 列表
        """
        stmt = (
            select(Agent)
            .where(
                and_(
                    Agent.tenant_id == self.tenant_id,
                    Agent.status == status,
                    Agent.is_deleted == False,
                )
            )
            .order_by(Agent.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_published_agents(
        self,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Agent]:
        """
        获取已发布的智能体列表

        Args:
            skip: 跳过数量
            limit: 返回数量

        Returns:
            已发布的 Agent 列表
        """
        from app.enums.agent import AgentStatusEnum

        return await self.get_by_status(
            AgentStatusEnum.PUBLISHED.value, skip, limit
        )

    async def get_by_name(
        self,
        name: str,
        exclude_id: Optional[int] = None,
    ) -> Optional[Agent]:
        """
        按名称查找智能体（同租户内唯一性检查）

        Args:
            name: 智能体名称
            exclude_id: 排除的 ID（用于更新时排除自身）

        Returns:
            Agent 实例或 None
        """
        conditions = [
            Agent.tenant_id == self.tenant_id,
            Agent.name == name,
            Agent.is_deleted == False,
        ]
        if exclude_id is not None:
            conditions.append(Agent.id != exclude_id)

        stmt = select(Agent).where(and_(*conditions))
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()


class AdminAgentRepository(BaseRepository[Agent]):
    """
    管理端智能体 Repository

    无租户隔离，供平台管理端全局查询使用
    """

    model = Agent


__all__ = ["AgentRepository", "AdminAgentRepository"]
