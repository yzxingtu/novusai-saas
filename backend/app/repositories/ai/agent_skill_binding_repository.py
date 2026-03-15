"""
智能体技能绑定 Repository / Agent Skill Binding Repository
"""

from sqlalchemy import and_, delete, select

from app.core.base_repository import TenantRepository
from app.models.ai.agent_skill_binding import AgentSkillBinding


class AgentSkillBindingRepository(TenantRepository[AgentSkillBinding]):
    """
    智能体技能绑定 Repository / Agent skill binding repository.

    - tenant 场景: tenant_id = 指定企业 / tenant: tenant_id = given tenant
    - admin/global 场景: tenant_id IS NULL / admin/global: tenant_id IS NULL
    """

    model = AgentSkillBinding

    def __init__(self, db, tenant_id: int | None):
        # TenantRepository 支持传入 None（用于 admin/global agent 绑定记录）
        super().__init__(db, tenant_id)  # type: ignore[arg-type]

    def _tenant_filter(self):
        """构建 tenant_id 过滤条件（支持 NULL）。/ Build tenant_id filter (supports NULL)."""
        if self.tenant_id is None:
            return AgentSkillBinding.tenant_id.is_(None)
        return AgentSkillBinding.tenant_id == self.tenant_id

    async def get_by_agent_id(self, agent_id: int) -> list[AgentSkillBinding]:
        """
        获取指定智能体的所有技能包绑定（按 sort_order 排序） / Get all skill bindings for an agent (ordered by sort_order).

        Args:
            agent_id: 智能体 ID / Agent ID

        Returns:
            AgentSkillBinding 列表（含 SkillPackage 关系 selectin 加载） / List of AgentSkillBinding
        """
        stmt = (
            select(AgentSkillBinding)
            .where(
                and_(
                    AgentSkillBinding.agent_id == agent_id,
                    self._tenant_filter(),
                    AgentSkillBinding.is_deleted.is_(False),
                )
            )
            .order_by(AgentSkillBinding.sort_order)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_enabled_by_agent_id(self, agent_id: int) -> list[AgentSkillBinding]:
        """
        获取指定智能体的已启用技能包绑定 / Get enabled skill package bindings for an agent.

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
                    self._tenant_filter(),
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
        获取指定 agent-package 绑定 / Get agent-package binding by ids.

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
                self._tenant_filter(),
                AgentSkillBinding.is_deleted.is_(False),
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def delete_by_agent_id(self, agent_id: int) -> int:
        """
        删除指定智能体的所有绑定（物理删除）/ Delete all bindings for an agent (hard delete).

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
                    self._tenant_filter(),
                )
            )
        )
        result = await self.db.execute(stmt)
        return result.rowcount


__all__ = ["AgentSkillBindingRepository"]
