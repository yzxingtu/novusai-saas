"""Shared conversation-turn setup helpers for AgentChatService."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from app.enums.agent import ConversationOwnerTypeEnum

ResolveInteractionModeFn = Callable[
    ...,
    Awaitable[tuple[str, dict[str, Any] | None, str | None]],
]
ApplyInteractionStateFn = Callable[..., Awaitable[list[dict[str, Any]] | None]]
BuildMemoryEventIdFn = Callable[[int], str]


@dataclass(frozen=True)
class PreparedConversationTurn:
    """Stable conversation turn bootstrap result shared by chat/stream_chat."""

    conversation: Any
    is_new_conversation: bool
    conversation_owner_type: str
    interaction_mode_effective: str
    resolved_trust_policy_ref: dict[str, Any] | None
    interaction_mode_downgrade_reason: str | None
    interaction_updates: list[dict[str, Any]] | None
    memory_event_id: str


class AgentChatConversationTurnService:
    """Coordinates shared conversation opening and interaction-state setup."""

    @staticmethod
    def build_conversation_interaction_metadata(
        conversation_metadata: dict[str, Any],
        *,
        requested_mode: str | None,
        effective_mode: str,
        downgrade_reason: str | None,
    ) -> dict[str, Any]:
        metadata = dict(conversation_metadata or {})
        metadata["interaction_mode"] = effective_mode
        metadata["interaction_mode_requested"] = requested_mode
        if downgrade_reason:
            metadata["interaction_mode_downgrade_reason"] = downgrade_reason
        else:
            metadata.pop("interaction_mode_downgrade_reason", None)
        return metadata

    @classmethod
    async def apply_interaction_state(
        cls,
        *,
        conversation: Any,
        agent_id: int,
        user_id: int | None,
        conversation_owner_type: str,
        requested_mode: str | None,
        interaction_mode_effective: str,
        interaction_mode_downgrade_reason: str | None,
        interaction_updates: list[dict[str, Any]] | None,
        conversation_service: Any,
        interaction_mode_manager: Any,
        grant_trusted_auto_policies: Callable[..., Awaitable[None]],
    ) -> list[dict[str, Any]] | None:
        conversation.metadata_ = cls.build_conversation_interaction_metadata(
            dict(conversation.metadata_ or {}),
            requested_mode=requested_mode,
            effective_mode=interaction_mode_effective,
            downgrade_reason=interaction_mode_downgrade_reason,
        )
        enriched_updates = interaction_mode_manager.enrich_interaction_updates(
            interaction_updates,
            requested_mode=requested_mode,
            effective_mode=interaction_mode_effective,
            downgrade_reason=interaction_mode_downgrade_reason,
        )
        if not enriched_updates:
            return None
        await conversation_service.update_last_assistant_interaction_state(
            conversation.id,
            enriched_updates,
            user_id=user_id,
            owner_type=conversation_owner_type,
            interaction_mode_requested=requested_mode,
            interaction_mode_effective=interaction_mode_effective,
            interaction_mode_downgrade_reason=interaction_mode_downgrade_reason,
        )
        await grant_trusted_auto_policies(
            conversation_id=conversation.id,
            agent_id=agent_id,
            operator_id=user_id,
            operator_type=conversation_owner_type,
            interaction_updates=enriched_updates,
            interaction_mode=interaction_mode_effective,
        )
        return enriched_updates

    async def prepare_conversation_turn(
        self,
        *,
        agent_id: int,
        conversation_id: int | None,
        user_id: int | None,
        user_role: str,
        first_message: str,
        requested_mode: str | None,
        interaction_updates: list[dict[str, Any]] | None,
        trust_policy_ref: dict[str, Any] | None,
        resolve_interaction_mode: ResolveInteractionModeFn,
        apply_interaction_state: ApplyInteractionStateFn,
        build_memory_event_id: BuildMemoryEventIdFn,
        conversation_service: Any,
    ) -> PreparedConversationTurn:
        is_new_conversation = conversation_id is None
        conversation_owner_type = ConversationOwnerTypeEnum.from_user_role(user_role)
        (
            interaction_mode_effective,
            resolved_trust_policy_ref,
            interaction_mode_downgrade_reason,
        ) = await resolve_interaction_mode(
            requested_mode=requested_mode,
            conversation_id=conversation_id,
            agent_id=agent_id,
            operator_id=user_id,
            operator_type=conversation_owner_type,
            explicit_trust_policy_ref=trust_policy_ref,
            interaction_updates=interaction_updates,
        )
        conversation = await conversation_service.get_or_create_for_chat(
            agent_id=agent_id,
            conversation_id=conversation_id,
            user_id=user_id,
            owner_type=conversation_owner_type,
            first_message=first_message,
        )
        resolved_interaction_updates = await apply_interaction_state(
            conversation=conversation,
            agent_id=agent_id,
            user_id=user_id,
            conversation_owner_type=conversation_owner_type,
            requested_mode=requested_mode,
            interaction_mode_effective=interaction_mode_effective,
            interaction_mode_downgrade_reason=interaction_mode_downgrade_reason,
            interaction_updates=interaction_updates,
        )
        return PreparedConversationTurn(
            conversation=conversation,
            is_new_conversation=is_new_conversation,
            conversation_owner_type=conversation_owner_type,
            interaction_mode_effective=interaction_mode_effective,
            resolved_trust_policy_ref=resolved_trust_policy_ref,
            interaction_mode_downgrade_reason=interaction_mode_downgrade_reason,
            interaction_updates=resolved_interaction_updates,
            memory_event_id=build_memory_event_id(conversation.id),
        )


__all__ = [
    "AgentChatConversationTurnService",
    "PreparedConversationTurn",
]
