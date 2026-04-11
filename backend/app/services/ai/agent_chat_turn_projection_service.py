"""Shared turn projection binders for AgentChatService."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.ai.engine.types import ExecutionResult
from app.services.ai.agent_chat_turn_projection import (
    build_context_diagnostics,
    build_last_run_summary,
    extract_turn_meta_from_result,
)

ContextDiagnosticsBuilder = Callable[[ExecutionResult], dict[str, Any]]
LastRunSummaryBuilder = Callable[[ExecutionResult], dict[str, Any]]


@dataclass(frozen=True)
class AgentChatTurnProjectionBundle:
    """Context diagnostics + last-run summary produced for one turn result."""

    context_diagnostics: dict[str, Any]
    last_run_summary: dict[str, Any]


class BoundAgentChatTurnProjector:
    """Memoizes per-result turn projection so chat/stream can share one path."""

    def __init__(
        self,
        *,
        context_diagnostics_builder: ContextDiagnosticsBuilder,
        last_run_summary_builder: LastRunSummaryBuilder,
    ) -> None:
        self._context_diagnostics_builder = context_diagnostics_builder
        self._last_run_summary_builder = last_run_summary_builder
        self._cache: dict[int, AgentChatTurnProjectionBundle] = {}

    def build(self, result: ExecutionResult) -> AgentChatTurnProjectionBundle:
        cache_key = id(result)
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached
        projection = AgentChatTurnProjectionBundle(
            context_diagnostics=self._context_diagnostics_builder(result),
            last_run_summary=self._last_run_summary_builder(result),
        )
        self._cache[cache_key] = projection
        return projection

    def build_context_diagnostics(self, result: ExecutionResult) -> dict[str, Any]:
        return self.build(result).context_diagnostics

    def build_last_run_summary(self, result: ExecutionResult) -> dict[str, Any]:
        return self.build(result).last_run_summary


class AgentChatTurnProjectionService:
    """Facade around shared agent-chat turn projection helpers."""

    @staticmethod
    def extract_turn_meta_from_result(result: ExecutionResult) -> dict[str, Any]:
        return extract_turn_meta_from_result(result)

    @staticmethod
    def build_context_diagnostics(
        result: ExecutionResult,
        *,
        interaction_mode_effective: str,
    ) -> dict[str, Any]:
        return build_context_diagnostics(
            result,
            interaction_mode_effective=interaction_mode_effective,
        )

    @staticmethod
    def build_last_run_summary(
        result: ExecutionResult,
        *,
        interaction_mode_effective: str,
        downgrade_reason: str | None,
    ) -> dict[str, Any]:
        return build_last_run_summary(
            result,
            interaction_mode_effective=interaction_mode_effective,
            downgrade_reason=downgrade_reason,
        )

    @staticmethod
    def bind(
        *,
        context_diagnostics_builder: ContextDiagnosticsBuilder,
        last_run_summary_builder: LastRunSummaryBuilder,
    ) -> BoundAgentChatTurnProjector:
        return BoundAgentChatTurnProjector(
            context_diagnostics_builder=context_diagnostics_builder,
            last_run_summary_builder=last_run_summary_builder,
        )


__all__ = [
    "AgentChatTurnProjectionBundle",
    "AgentChatTurnProjectionService",
    "BoundAgentChatTurnProjector",
]
