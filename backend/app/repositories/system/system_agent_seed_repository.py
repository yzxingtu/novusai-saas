"""
System agent seed repository.

Owns the database queries and persistence used by the admin-side bootstrap and
repair flow for built-in Copilot agents.
"""

from __future__ import annotations

from sqlalchemy import and_, select
from sqlalchemy.orm import selectinload

from app.core.base_repository import BaseRepository
from app.enums.ai import ModelTypeEnum
from app.models.ai import AIModel, AIProvider, Agent, AgentSkillGrant, Skill, SkillPackage
from app.models.system.agent_assignment import SystemAgentAssignment


class SystemAgentSeedRepository(BaseRepository[SystemAgentAssignment]):
    """Repository for system Copilot bootstrap and repair operations."""

    model = SystemAgentAssignment

    async def get_first_active_provider(self) -> AIProvider | None:
        stmt = (
            select(AIProvider)
            .where(
                AIProvider.is_active.is_(True),
                AIProvider.is_deleted.is_(False),
            )
            .order_by(AIProvider.sort_order.asc(), AIProvider.created_at.desc())
            .limit(1)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_first_active_chat_model(self) -> AIModel | None:
        stmt = (
            select(AIModel)
            .join(AIProvider, AIProvider.id == AIModel.provider_id)
            .where(
                AIModel.type == ModelTypeEnum.CHAT.value,
                AIModel.is_active.is_(True),
                AIModel.is_deleted.is_(False),
                AIProvider.is_active.is_(True),
                AIProvider.is_deleted.is_(False),
            )
            .options(selectinload(AIModel.provider))
            .order_by(
                AIProvider.sort_order.asc(),
                AIModel.input_price_per_1k.asc().nulls_last(),
                AIModel.id.asc(),
            )
            .limit(1)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_ready_chat_model_with_active_provider(
        self,
        model_id: int,
    ) -> AIModel | None:
        stmt = (
            select(AIModel)
            .join(AIProvider, AIProvider.id == AIModel.provider_id)
            .where(
                AIModel.id == model_id,
                AIModel.type == ModelTypeEnum.CHAT.value,
                AIModel.is_active.is_(True),
                AIModel.is_deleted.is_(False),
                AIProvider.is_active.is_(True),
                AIProvider.is_deleted.is_(False),
            )
            .options(selectinload(AIModel.provider))
            .limit(1)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_global_assignment(
        self,
        feature_code: str,
        *,
        include_deleted: bool = False,
    ) -> SystemAgentAssignment | None:
        stmt = (
            select(SystemAgentAssignment)
            .where(
                SystemAgentAssignment.feature_code == feature_code,
                SystemAgentAssignment.tenant_id.is_(None),
            )
            .options(selectinload(SystemAgentAssignment.agent))
            .order_by(
                SystemAgentAssignment.is_deleted.asc(),
                SystemAgentAssignment.id.asc(),
            )
            .limit(1)
        )
        if not include_deleted:
            stmt = stmt.where(SystemAgentAssignment.is_deleted.is_(False))
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_active_platform_agent(self, agent_id: int) -> Agent | None:
        stmt = (
            select(Agent)
            .where(
                Agent.id == agent_id,
                Agent.owner_tenant_id.is_(None),
                Agent.is_deleted.is_(False),
            )
            .limit(1)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_platform_agent_by_name(
        self,
        name: str,
        *,
        include_deleted: bool = False,
    ) -> Agent | None:
        stmt = (
            select(Agent)
            .where(
                Agent.name == name,
                Agent.owner_tenant_id.is_(None),
            )
            .limit(1)
        )
        if not include_deleted:
            stmt = stmt.where(Agent.is_deleted.is_(False))
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_platform_system_agent_by_name(
        self,
        name: str,
        *,
        include_deleted: bool = False,
    ) -> Agent | None:
        stmt = (
            select(Agent)
            .where(
                Agent.name == name,
                Agent.owner_tenant_id.is_(None),
                Agent.is_system.is_(True),
            )
            .order_by(Agent.is_deleted.asc(), Agent.id.asc())
            .limit(1)
        )
        if not include_deleted:
            stmt = stmt.where(Agent.is_deleted.is_(False))
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_platform_skill_package_by_name(
        self,
        name: str,
        *,
        include_deleted: bool = False,
    ) -> SkillPackage | None:
        stmt = (
            select(SkillPackage)
            .where(
                SkillPackage.name == name,
                SkillPackage.tenant_id.is_(None),
            )
            .limit(1)
        )
        if not include_deleted:
            stmt = stmt.where(SkillPackage.is_deleted.is_(False))
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_platform_system_skill_package_by_name(
        self,
        name: str,
        *,
        include_deleted: bool = False,
    ) -> SkillPackage | None:
        stmt = (
            select(SkillPackage)
            .where(
                SkillPackage.name == name,
                SkillPackage.tenant_id.is_(None),
                SkillPackage.is_system.is_(True),
            )
            .order_by(SkillPackage.is_deleted.asc(), SkillPackage.id.asc())
            .limit(1)
        )
        if not include_deleted:
            stmt = stmt.where(SkillPackage.is_deleted.is_(False))
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_platform_skill_by_key(
        self,
        key: str,
        *,
        include_deleted: bool = False,
    ) -> Skill | None:
        stmt = (
            select(Skill)
            .where(
                Skill.key == key,
                Skill.tenant_id.is_(None),
            )
            .limit(1)
        )
        if not include_deleted:
            stmt = stmt.where(Skill.is_deleted.is_(False))
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_any_skill_by_key(
        self,
        key: str,
        *,
        include_deleted: bool = False,
    ) -> Skill | None:
        stmt = select(Skill).where(Skill.key == key).limit(1)
        if not include_deleted:
            stmt = stmt.where(Skill.is_deleted.is_(False))
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_platform_system_skill_by_key(
        self,
        key: str,
        *,
        include_deleted: bool = False,
    ) -> Skill | None:
        stmt = (
            select(Skill)
            .where(
                Skill.key == key,
                Skill.tenant_id.is_(None),
                Skill.is_system.is_(True),
            )
            .order_by(Skill.is_deleted.asc(), Skill.id.asc())
            .limit(1)
        )
        if not include_deleted:
            stmt = stmt.where(Skill.is_deleted.is_(False))
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_agent_skill_grant(
        self,
        *,
        agent_id: int,
        skill_id: int,
        include_deleted: bool = False,
    ) -> AgentSkillGrant | None:
        stmt = (
            select(AgentSkillGrant)
            .where(
                AgentSkillGrant.agent_id == agent_id,
                AgentSkillGrant.skill_id == skill_id,
            )
            .limit(1)
        )
        if not include_deleted:
            stmt = stmt.where(AgentSkillGrant.is_deleted.is_(False))
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def create_skill_package(self, data: dict) -> SkillPackage:
        package = SkillPackage(**data)
        self.db.add(package)
        await self.db.flush()
        await self.db.refresh(package)
        return package

    async def create_skill(self, data: dict) -> Skill:
        skill = Skill(**data)
        self.db.add(skill)
        await self.db.flush()
        await self.db.refresh(skill)
        return skill

    async def create_agent(self, data: dict) -> Agent:
        agent = Agent(**data)
        self.db.add(agent)
        await self.db.flush()
        await self.db.refresh(agent)
        return agent

    async def create_agent_skill_grant(self, data: dict) -> AgentSkillGrant:
        grant = AgentSkillGrant(**data)
        self.db.add(grant)
        await self.db.flush()
        await self.db.refresh(grant)
        return grant

    async def create_assignment(self, data: dict) -> SystemAgentAssignment:
        assignment = SystemAgentAssignment(**data)
        self.db.add(assignment)
        await self.db.flush()
        await self.db.refresh(assignment)
        return assignment

    async def list_global_assignments(
        self,
        feature_codes: list[str],
    ) -> list[SystemAgentAssignment]:
        stmt = (
            select(SystemAgentAssignment)
            .where(
                SystemAgentAssignment.feature_code.in_(feature_codes),
                SystemAgentAssignment.tenant_id.is_(None),
                SystemAgentAssignment.is_deleted.is_(False),
            )
            .options(selectinload(SystemAgentAssignment.agent))
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def list_valid_assignment_agents(
        self,
        agent_ids: list[int],
    ) -> dict[int, Agent]:
        if not agent_ids:
            return {}

        stmt = select(Agent).where(
            and_(
                Agent.id.in_(agent_ids),
                Agent.owner_tenant_id.is_(None),
                Agent.is_deleted.is_(False),
            )
        )
        result = await self.db.execute(stmt)
        return {agent.id: agent for agent in result.scalars().all()}


__all__ = ["SystemAgentSeedRepository"]
