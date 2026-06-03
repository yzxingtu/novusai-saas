"""
Agent router query helpers (DB access and visibility checks).
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.configs.service import PLATFORM_TENANT_ID
from app.core.i18n import _
from app.enums.agent import (
    AgentExecutionModeEnum,
    AgentStatusEnum,
    ConversationOwnerTypeEnum,
)
from app.enums.common import UserRoleEnum
from app.exceptions import NotFoundException
from app.models.ai.agent import Agent
from app.models.ai.agent_conversation import AgentConversation
from app.models.ai.agent_skill_grant import AgentSkillGrant
from app.models.ai.skill import Skill
from app.models.system.agent_assignment import SystemAgentAssignment
from app.repositories.ai.agent_repository import _tenant_available_condition
from app.services.ai.agent_router_capability_support import agent_can_handle_images
from app.services.ai.agent_service import AgentService


class AgentRouterQueryService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_available_agents(
        self,
        tenant_id: int | None,
        user_role: str,
        *,
        user_id: int | None = None,
        user_role_id: int | None = None,
    ) -> list[Agent]:
        query = (
            select(Agent)
            .options(
                selectinload(Agent.model),
                selectinload(Agent.skill_grants)
                .selectinload(AgentSkillGrant.skill)
                .selectinload(Skill.package),
            )
            .where(
                Agent.status == AgentStatusEnum.PUBLISHED.value,
                Agent.is_deleted.is_(False),
                Agent.execution_mode != AgentExecutionModeEnum.ROUTER.value,
            )
        )

        if user_role == UserRoleEnum.PLATFORM_ADMIN.value:
            query = query.where(Agent.owner_tenant_id.is_(None))
            agents = list((await self.db.execute(query)).scalars().unique().all())
            return sorted(agents, key=lambda item: item.id)
        if tenant_id:
            query = query.where(_tenant_available_condition(tenant_id))
        else:
            return []

        agents = list((await self.db.execute(query)).scalars().all())
        if not agents:
            return []

        agent_service = AgentService(self.db, tenant_id)
        visible: list[Agent] = []
        for agent in agents:
            allowed = await agent_service.check_user_access(
                agent_id=agent.id,
                user_id=user_id or 0,
                user_role=user_role,
                user_role_id=user_role_id,
            )
            if allowed:
                visible.append(agent)
        return sorted(visible, key=lambda item: item.id)

    async def get_router_agent(self) -> Agent | None:
        result = await self.db.execute(
            select(Agent)
            .where(
                Agent.execution_mode == AgentExecutionModeEnum.ROUTER.value,
                Agent.is_system.is_(True),
                Agent.owner_tenant_id.is_(None),
                Agent.status == AgentStatusEnum.PUBLISHED.value,
                Agent.is_deleted.is_(False),
            )
            .order_by(Agent.id.asc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_published_agent(self, agent_id: int) -> Agent | None:
        result = await self.db.execute(
            select(Agent)
            .options(
                selectinload(Agent.model),
                selectinload(Agent.skill_grants)
                .selectinload(AgentSkillGrant.skill)
                .selectinload(Skill.package),
            )
            .where(
                Agent.id == agent_id,
                Agent.status == AgentStatusEnum.PUBLISHED.value,
                Agent.is_deleted.is_(False),
            )
        )
        return result.scalar_one_or_none()

    async def get_accessible_conversation(
        self,
        conversation_id: int,
        tenant_id: int | None,
        user_role: str,
        *,
        user_id: int | None,
    ) -> AgentConversation:
        stmt = select(AgentConversation).where(
            AgentConversation.id == conversation_id,
            AgentConversation.is_deleted.is_(False),
        )
        if user_role == UserRoleEnum.PLATFORM_ADMIN.value:
            stmt = stmt.where(
                AgentConversation.tenant_id == PLATFORM_TENANT_ID,
                AgentConversation.owner_type
                == ConversationOwnerTypeEnum.PLATFORM_ADMIN.value,
            )
        elif tenant_id:
            stmt = stmt.where(
                AgentConversation.tenant_id == tenant_id,
                AgentConversation.owner_type
                == ConversationOwnerTypeEnum.from_user_role(
                    user_role,
                ),
            )
        else:
            raise NotFoundException(
                message=_("agent_chat.error.conversation_not_found"),
            )

        if user_role != UserRoleEnum.PLATFORM_ADMIN.value and user_id is not None:
            stmt = stmt.where(AgentConversation.user_id == user_id)

        result = await self.db.execute(stmt.limit(1))
        conversation = result.scalar_one_or_none()
        if not conversation:
            raise NotFoundException(
                message=_("agent_chat.error.conversation_not_found"),
            )
        return conversation

    async def is_agent_visible(
        self,
        agent: Agent,
        tenant_id: int | None,
        user_role: str,
        *,
        user_id: int | None,
        user_role_id: int | None,
    ) -> bool:
        if user_role == UserRoleEnum.PLATFORM_ADMIN.value:
            return getattr(agent, "owner_tenant_id", None) is None

        if not tenant_id:
            return False

        try:
            return await AgentService(self.db, tenant_id).check_user_access(
                agent_id=agent.id,
                user_id=user_id or 0,
                user_role=user_role,
                user_role_id=user_role_id,
            )
        except NotFoundException:
            return False

    async def agent_can_handle_images(self, agent: Agent | None) -> bool:
        return await agent_can_handle_images(self.db, agent)

    async def resolve_default_assignment(
        self,
        *,
        tenant_id: int | None,
        user_role: str,
        feature_code: str,
    ) -> SystemAgentAssignment | None:
        assignment: SystemAgentAssignment | None = None

        if tenant_id and user_role != UserRoleEnum.PLATFORM_ADMIN.value:
            result = await self.db.execute(
                select(SystemAgentAssignment).where(
                    SystemAgentAssignment.feature_code == feature_code,
                    SystemAgentAssignment.tenant_id == tenant_id,
                    SystemAgentAssignment.is_active.is_(True),
                    SystemAgentAssignment.is_deleted.is_(False),
                )
            )
            assignment = result.scalar_one_or_none()

        if not assignment:
            result = await self.db.execute(
                select(SystemAgentAssignment).where(
                    SystemAgentAssignment.feature_code == feature_code,
                    SystemAgentAssignment.tenant_id.is_(None),
                    SystemAgentAssignment.is_active.is_(True),
                    SystemAgentAssignment.is_deleted.is_(False),
                )
            )
            assignment = result.scalar_one_or_none()

        return assignment


__all__ = ["AgentRouterQueryService"]
