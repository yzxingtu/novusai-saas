"""Interaction mode orchestration helpers for AgentChatService."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.schemas.ai.agent_chat import InteractionMode
from app.services.ai.agent_chat_runtime_support import AgentChatRuntimeSupport


@dataclass(frozen=True)
class InteractionModeOutcome:
    """Stable outcome of the interaction-mode negotiation."""

    effective_mode: InteractionMode
    trust_policy_ref: dict[str, Any] | None
    downgrade_reason: str | None


class AgentChatInteractionModeManager:
    """Coordinates interaction mode resolution and update metadata."""

    def __init__(self, runtime_support: AgentChatRuntimeSupport) -> None:
        self._runtime_support = runtime_support

    async def resolve_mode(
        self,
        *,
        requested_mode: str | None,
        conversation_id: int | None,
        agent_id: int,
        operator_id: int | None,
        operator_type: str | None,
        explicit_trust_policy_ref: dict[str, Any] | None = None,
        interaction_updates: list[dict[str, Any]] | None = None,
    ) -> InteractionModeOutcome:
        (
            effective_mode,
            trust_policy_ref,
            downgrade_reason,
        ) = await self._runtime_support.resolve_interaction_mode(
            requested_mode=requested_mode,
            conversation_id=conversation_id,
            agent_id=agent_id,
            operator_id=operator_id,
            operator_type=operator_type,
            explicit_trust_policy_ref=explicit_trust_policy_ref,
            interaction_updates=interaction_updates,
        )
        return InteractionModeOutcome(
            effective_mode=effective_mode,
            trust_policy_ref=trust_policy_ref,
            downgrade_reason=downgrade_reason,
        )

    @staticmethod
    def enrich_interaction_updates(
        interaction_updates: list[dict[str, Any]] | None,
        *,
        requested_mode: str | None,
        effective_mode: str,
        downgrade_reason: str | None,
    ) -> list[dict[str, Any]] | None:
        _requested_mode = requested_mode
        _downgrade_reason = downgrade_reason
        if not interaction_updates:
            return None

        auto_source = (
            "execution_trust_policy" if effective_mode == "trusted_auto" else None
        )
        enriched: list[dict[str, Any]] = []
        for update in interaction_updates:
            if not isinstance(update, dict):
                continue
            enriched.append(
                {
                    **update,
                    "auto_approve_source": auto_source,
                }
            )
        return enriched or None

    async def grant_trusted_auto_policies(
        self,
        *,
        conversation_id: int,
        agent_id: int,
        operator_id: int | None,
        operator_type: str | None,
        interaction_updates: list[dict[str, Any]] | None,
        interaction_mode: str,
    ) -> None:
        if not interaction_updates:
            return
        await self._runtime_support.grant_trusted_auto_policies(
            conversation_id=conversation_id,
            agent_id=agent_id,
            operator_id=operator_id,
            operator_type=operator_type,
            interaction_updates=interaction_updates,
            interaction_mode=interaction_mode,
        )
