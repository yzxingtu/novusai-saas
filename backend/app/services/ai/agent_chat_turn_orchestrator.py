"""Conversation turn orchestration helpers for AgentChatService."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from app.services.ai.agent_chat_conversation_turn_service import (
    AgentChatConversationTurnService,
    PreparedConversationTurn,
)
from app.services.ai.agent_chat_interaction_mode_manager import (
    AgentChatInteractionModeManager,
)

ResolveInteractionModeFn = Callable[
    ...,
    Awaitable[tuple[str, dict[str, Any] | None, str | None]],
]
ApplyInteractionStateFn = Callable[..., Awaitable[list[dict[str, Any]] | None]]
BuildMemoryEventIdFn = Callable[[int], str]


class AgentChatTurnOrchestrator:
    """Coordinates shared conversation bootstrap across chat + stream paths."""

    def __init__(
        self,
        *,
        conversation_service: Any,
        interaction_mode_manager: AgentChatInteractionModeManager,
        build_memory_event_id: BuildMemoryEventIdFn,
    ) -> None:
        self._conversation_service = conversation_service
        self._interaction_mode_manager = interaction_mode_manager
        self._conversation_turn_service = AgentChatConversationTurnService()
        self._build_memory_event_id = build_memory_event_id

    async def _resolve_interaction_mode(
        self,
        *,
        requested_mode: str | None,
        conversation_id: int | None,
        agent_id: int,
        operator_id: int | None,
        operator_type: str | None,
        explicit_trust_policy_ref: dict[str, Any] | None = None,
        interaction_updates: list[dict[str, Any]] | None = None,
    ) -> tuple[str, dict[str, Any] | None, str | None]:
        outcome = await self._interaction_mode_manager.resolve_mode(
            requested_mode=requested_mode,
            conversation_id=conversation_id,
            agent_id=agent_id,
            operator_id=operator_id,
            operator_type=operator_type,
            explicit_trust_policy_ref=explicit_trust_policy_ref,
            interaction_updates=interaction_updates,
        )
        return (
            outcome.effective_mode,
            outcome.trust_policy_ref,
            outcome.downgrade_reason,
        )

    async def _grant_trusted_auto_policies(
        self,
        *,
        conversation_id: int,
        agent_id: int,
        operator_id: int | None,
        operator_type: str | None,
        interaction_updates: list[dict[str, Any]] | None,
        interaction_mode: str,
    ) -> None:
        await self._interaction_mode_manager.grant_trusted_auto_policies(
            conversation_id=conversation_id,
            agent_id=agent_id,
            operator_id=operator_id,
            operator_type=operator_type,
            interaction_updates=interaction_updates,
            interaction_mode=interaction_mode,
        )

    async def _apply_interaction_state(
        self,
        *,
        conversation: Any,
        agent_id: int,
        user_id: int | None,
        conversation_owner_type: str,
        requested_mode: str | None,
        interaction_mode_effective: str,
        interaction_mode_downgrade_reason: str | None,
        interaction_updates: list[dict[str, Any]] | None,
    ) -> list[dict[str, Any]] | None:
        return await self._conversation_turn_service.apply_interaction_state(
            conversation=conversation,
            agent_id=agent_id,
            user_id=user_id,
            conversation_owner_type=conversation_owner_type,
            requested_mode=requested_mode,
            interaction_mode_effective=interaction_mode_effective,
            interaction_mode_downgrade_reason=interaction_mode_downgrade_reason,
            interaction_updates=interaction_updates,
            conversation_service=self._conversation_service,
            interaction_mode_manager=self._interaction_mode_manager,
            grant_trusted_auto_policies=self._grant_trusted_auto_policies,
        )

    async def prepare_conversation_turn(
        self,
        *,
        agent_id: int,
        conversation_id: int | None,
        message: str,
        user_id: int | None,
        user_role: str,
        interaction_mode: str | None,
        interaction_updates: list[dict[str, Any]] | None,
        trust_policy_ref: dict[str, Any] | None,
    ) -> PreparedConversationTurn:
        return await self._conversation_turn_service.prepare_conversation_turn(
            agent_id=agent_id,
            conversation_id=conversation_id,
            user_id=user_id,
            user_role=user_role,
            first_message=message,
            requested_mode=interaction_mode,
            interaction_updates=interaction_updates,
            trust_policy_ref=trust_policy_ref,
            resolve_interaction_mode=self._resolve_interaction_mode,
            apply_interaction_state=self._apply_interaction_state,
            build_memory_event_id=self._build_memory_event_id,
            conversation_service=self._conversation_service,
        )


__all__ = ["AgentChatTurnOrchestrator"]
