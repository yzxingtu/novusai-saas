"""
Agent skill grant repository.
"""

from sqlalchemy import and_, delete, select
from sqlalchemy.orm import selectinload

from app.core.base_repository import TenantRepository
from app.models.ai.agent_skill_grant import AgentSkillGrant
from app.models.ai.skill import Skill
from app.models.ai.skill_package import SkillPackage
from app.repositories.ai.retired_skill_catalog_filters import (
    not_retired_skill_condition,
    not_retired_skill_package_condition,
)


class AgentSkillGrantRepository(TenantRepository[AgentSkillGrant]):
    """
    Direct Agent-Skill grant repository.

    tenant 场景: tenant_id = 指定企业
    admin/global 场景: tenant_id IS NULL
    """

    model = AgentSkillGrant

    def __init__(self, db, tenant_id: int | None):
        super().__init__(db, tenant_id)  # type: ignore[arg-type]  # 租户可空 / nullable tenant

    def _tenant_filter(self):
        """Build tenant_id filter and support NULL owner grants."""
        if self.tenant_id is None:
            return AgentSkillGrant.tenant_id.is_(None)
        return AgentSkillGrant.tenant_id == self.tenant_id

    def _with_available_skill_filters(self, stmt):
        return (
            stmt.join(Skill, AgentSkillGrant.skill_id == Skill.id)
            .join(SkillPackage, Skill.package_id == SkillPackage.id)
            .where(
                Skill.is_deleted.is_(False),
                SkillPackage.is_deleted.is_(False),
                not_retired_skill_condition(Skill),
                not_retired_skill_package_condition(SkillPackage),
            )
        )

    async def get_by_id(
        self,
        id: int,
        include_deleted: bool = False,
    ) -> AgentSkillGrant | None:
        """Get grant by id without surfacing retired skill/package grants."""
        stmt = (
            select(AgentSkillGrant)
            .options(
                selectinload(AgentSkillGrant.skill).selectinload(Skill.package),
            )
            .where(
                and_(
                    AgentSkillGrant.id == id,
                    self._tenant_filter(),
                )
            )
        )
        if not include_deleted:
            stmt = stmt.where(AgentSkillGrant.is_deleted.is_(False))
        stmt = self._with_available_skill_filters(stmt)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_agent_id(self, agent_id: int) -> list[AgentSkillGrant]:
        """Get all grants for an agent ordered by sort_order."""
        stmt = (
            select(AgentSkillGrant)
            .options(
                selectinload(AgentSkillGrant.skill).selectinload(Skill.package),
            )
            .where(
                and_(
                    AgentSkillGrant.agent_id == agent_id,
                    self._tenant_filter(),
                    AgentSkillGrant.is_deleted.is_(False),
                )
            )
        )
        stmt = self._with_available_skill_filters(stmt).order_by(
            AgentSkillGrant.sort_order
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_enabled_by_agent_id(self, agent_id: int) -> list[AgentSkillGrant]:
        """Get enabled grants for an agent ordered by sort_order."""
        stmt = (
            select(AgentSkillGrant)
            .options(
                selectinload(AgentSkillGrant.skill).selectinload(Skill.package),
            )
            .where(
                and_(
                    AgentSkillGrant.agent_id == agent_id,
                    self._tenant_filter(),
                    AgentSkillGrant.enabled.is_(True),
                    AgentSkillGrant.is_deleted.is_(False),
                )
            )
        )
        stmt = self._with_available_skill_filters(stmt).order_by(
            AgentSkillGrant.sort_order
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_grant(
        self,
        agent_id: int,
        skill_id: int,
    ) -> AgentSkillGrant | None:
        """Get a specific grant by agent_id and skill_id."""
        stmt = (
            select(AgentSkillGrant)
            .options(
                selectinload(AgentSkillGrant.skill).selectinload(Skill.package),
            )
            .where(
                and_(
                    AgentSkillGrant.agent_id == agent_id,
                    AgentSkillGrant.skill_id == skill_id,
                    self._tenant_filter(),
                    AgentSkillGrant.is_deleted.is_(False),
                )
            )
        )
        stmt = self._with_available_skill_filters(stmt)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def delete_by_agent_id(self, agent_id: int) -> int:
        """Hard-delete all grants for an agent."""
        stmt = delete(AgentSkillGrant).where(
            and_(
                AgentSkillGrant.agent_id == agent_id,
                self._tenant_filter(),
            )
        )
        result = await self.db.execute(stmt)
        return result.rowcount


__all__ = ["AgentSkillGrantRepository"]
