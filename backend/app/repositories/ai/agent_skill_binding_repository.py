"""
智能体技能绑定 Repository
"""

from sqlalchemy import select, and_, delete

from app.models.ai.agent_skill_binding import AgentSkillBinding
from app.core.base_repository import TenantRepository


class AgentSkillBindingRepository(TenantRepository[AgentSkillBinding]):
    """
    租户级智能体技能绑定 Repository
    """

    model = AgentSkillBinding

    async def get_by_agent_id(self, agent_id: int) -> list[AgentSkillBinding]:
        """
        获取指定智能体的所有技能包绑定（按 sort_order 排序）

        Args:
            agent_id: 智能体 ID

        Returns:
            AgentSkillBinding 列表（含 SkillPackage 关系 selectin 加载）
        """
        stmt = (
            select(AgentSkillBinding)
            .where(
                and_(
                    AgentSkillBinding.agent_id == agent_id,
                    AgentSkillBinding.tenant_id == self.tenant_id,
                    AgentSkillBinding.is_deleted.is_(False),
                )
            )
            .order_by(AgentSkillBinding.sort_order)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_enabled_by_agent_id(self, agent_id: int) -> list[AgentSkillBinding]:
        """
        获取指定智能体的已启用技能包绑定

        Args:
            agent_id: 智能体 ID

        Returns:
            已启用的 AgentSkillBinding 列表
        """
        stmt = (
            select(AgentSkillBinding)
            .where(
                and_(
                    AgentSkillBinding.agent_id == agent_id,
                    AgentSkillBinding.tenant_id == self.tenant_id,
                    AgentSkillBinding.enabled.is_(True),
                    AgentSkillBinding.is_deleted.is_(False),
                )
            )
            .order_by(AgentSkillBinding.sort_order)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_binding(
        self, agent_id: int, package_id: int
    ) -> AgentSkillBinding | None:
        """
        获取指定 agent-package 绑定

        Args:
            agent_id: 智能体 ID
            package_id: 技能包 ID

        Returns:
            AgentSkillBinding 实例或 None
        """
        stmt = select(AgentSkillBinding).where(
            and_(
                AgentSkillBinding.agent_id == agent_id,
                AgentSkillBinding.package_id == package_id,
                AgentSkillBinding.tenant_id == self.tenant_id,
                AgentSkillBinding.is_deleted.is_(False),
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def delete_by_agent_id(self, agent_id: int) -> int:
        """
        删除指定智能体的所有绑定（物理删除）

        Args:
            agent_id: 智能体 ID

        Returns:
            删除的记录数
        """
        stmt = (
            delete(AgentSkillBinding)
            .where(
                and_(
                    AgentSkillBinding.agent_id == agent_id,
                    AgentSkillBinding.tenant_id == self.tenant_id,
                )
            )
        )
        result = await self.db.execute(stmt)
        return result.rowcount


__all__ = ["AgentSkillBindingRepository"]
