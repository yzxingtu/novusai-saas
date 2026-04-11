"""Runtime billing attribution helpers for AgentChatService."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.configs.service import PLATFORM_TENANT_ID

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.models.ai.agent import Agent


async def build_billing_context(
    *,
    db: AsyncSession,
    tenant_id: int,
    agent: Agent,
    user_id: int | None,
    user_role: str,
    user_role_id: int | None = None,
) -> dict[str, Any]:
    """Build immutable billing attribution context."""
    if tenant_id == PLATFORM_TENANT_ID:
        from app.services.ai.agent_service import AdminAgentService

        return await AdminAgentService(db).build_usage_attribution_context(
            agent=agent,
            user_id=user_id,
            user_role=user_role,
            user_role_id=user_role_id,
        )

    from app.services.ai.agent_service import AgentService

    return await AgentService(
        db,
        tenant_id,
    ).build_usage_attribution_context(
        agent=agent,
        user_id=user_id,
        user_role=user_role,
        user_role_id=user_role_id,
    )
