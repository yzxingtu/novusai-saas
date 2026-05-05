"""Turn projection helpers shared by AgentChatService command paths."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.ai.engine.types import ExecutionResult
from app.services.ai.agent_chat_turn_projection_service import (
    AgentChatTurnProjectionBundle,
    AgentChatTurnProjectionService,
    BoundAgentChatTurnProjector,
)


def bind_turn_projector(
    *,
    interaction_mode_effective: str,
    downgrade_reason: str | None,
    context_diagnostics_builder: Callable[[ExecutionResult], dict[str, Any]]
    | None = None,
    last_run_summary_builder: Callable[[ExecutionResult], dict[str, Any]] | None = None,
) -> BoundAgentChatTurnProjector:
    return AgentChatTurnProjectionService.bind(
        context_diagnostics_builder=context_diagnostics_builder
        or (
            lambda result: AgentChatTurnProjectionService.build_context_diagnostics(
                result,
                interaction_mode_effective=interaction_mode_effective,
            )
        ),
        last_run_summary_builder=last_run_summary_builder
        or (
            lambda result: AgentChatTurnProjectionService.build_last_run_summary(
                result,
                interaction_mode_effective=interaction_mode_effective,
                downgrade_reason=downgrade_reason,
            )
        ),
    )


def build_turn_projection_bundle(
    result: ExecutionResult,
    *,
    interaction_mode_effective: str,
    downgrade_reason: str | None,
) -> AgentChatTurnProjectionBundle:
    return bind_turn_projector(
        interaction_mode_effective=interaction_mode_effective,
        downgrade_reason=downgrade_reason,
    ).build(result)


__all__ = ["bind_turn_projector", "build_turn_projection_bundle"]
