"""Query helpers for AgentChatService (agent lookup, KB filtering)."""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.configs.service import PLATFORM_TENANT_ID
from app.core.i18n import _
from app.core.logging import LogManager
from app.enums.agent import AgentStatusEnum
from app.exceptions import BusinessException, NotFoundException
from app.repositories.ai.agent_repository import AgentRepository

logger = LogManager.get_logger("ai.agent_chat_service")


class AgentChatQueryService:
    """Read-focused queries extracted from AgentChatService."""

    def __init__(self, db: AsyncSession, tenant_id: int) -> None:
        self.db = db
        self.tenant_id = tenant_id

    async def validate_agent(self, agent_id: int) -> Any:
        """
        Load and validate agent (existence + published).

        Raises:
            NotFoundException: agent not found
            BusinessException: agent not published
        """
        if self.tenant_id == PLATFORM_TENANT_ID:
            from app.repositories.ai.agent_repository import AdminAgentRepository

            agent_repo = AdminAgentRepository(self.db)
        else:
            agent_repo = AgentRepository(self.db, self.tenant_id)
        agent = await agent_repo.get_by_id(agent_id)
        if not agent:
            raise NotFoundException(message=_("agent.error.not_found"))
        if agent.status != AgentStatusEnum.PUBLISHED.value:
            raise BusinessException(message=_("agent.error.not_published"))
        return agent

    async def sanitize_client_knowledge_base_ids(
        self,
        agent_id: int,
        knowledge_base_ids: list[int] | None,
    ) -> tuple[list[int] | None, list[int]]:
        """
        Keep only KB ids bound to the agent (tenant-scoped bindings).
        None => no narrowing.
        """
        if not knowledge_base_ids:
            return None, []
        from app.ai.rag_injector import load_agent_kb_bindings

        bound_ids, _ = await load_agent_kb_bindings(
            self.db,
            agent_id,
            self.tenant_id,
        )
        allowed = set(bound_ids or [])
        filtered = [x for x in knowledge_base_ids if x in allowed]
        dropped = [x for x in knowledge_base_ids if x not in allowed]
        if dropped:
            logger.warning(
                "Dropped knowledge_base_ids not bound to agent_id={}: {}",
                agent_id,
                dropped,
            )
        return filtered or None, dropped


__all__ = ["AgentChatQueryService"]
