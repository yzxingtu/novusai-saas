"""
智能体版本 Repository
"""

from typing import Optional, List

from sqlalchemy import select, and_

from app.core.base_repository import TenantRepository
from app.models.ai.agent_version import AgentVersion


class AgentVersionRepository(TenantRepository[AgentVersion]):
    """
    租户级智能体版本 Repository

    提供基于租户隔离的版本数据访问
    """

    model = AgentVersion

    async def get_by_agent_and_version(
        self,
        agent_id: int,
        version: int,
    ) -> Optional[AgentVersion]:
        """
        按智能体 ID 和版本号获取版本记录

        Args:
            agent_id: 智能体 ID
            version: 版本号

        Returns:
            AgentVersion 实例或 None
        """
        stmt = select(AgentVersion).where(
            and_(
                AgentVersion.tenant_id == self.tenant_id,
                AgentVersion.agent_id == agent_id,
                AgentVersion.version == version,
                AgentVersion.is_deleted == False,
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_versions_by_agent(
        self,
        agent_id: int,
        skip: int = 0,
        limit: int = 100,
    ) -> List[AgentVersion]:
        """
        获取智能体的版本列表（按版本号降序）

        Args:
            agent_id: 智能体 ID
            skip: 跳过数量
            limit: 返回数量

        Returns:
            AgentVersion 列表
        """
        stmt = (
            select(AgentVersion)
            .where(
                and_(
                    AgentVersion.tenant_id == self.tenant_id,
                    AgentVersion.agent_id == agent_id,
                    AgentVersion.is_deleted == False,
                )
            )
            .order_by(AgentVersion.version.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_latest_version_number(
        self,
        agent_id: int,
    ) -> int:
        """
        获取智能体的最新版本号

        Args:
            agent_id: 智能体 ID

        Returns:
            最新版本号（无版本时返回 0）
        """
        from sqlalchemy import func

        stmt = select(func.coalesce(func.max(AgentVersion.version), 0)).where(
            and_(
                AgentVersion.tenant_id == self.tenant_id,
                AgentVersion.agent_id == agent_id,
                AgentVersion.is_deleted == False,
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one()


__all__ = ["AgentVersionRepository"]
