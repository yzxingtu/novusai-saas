"""Shared mutable orchestration state for streaming and non-streaming flows."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Literal

from app.ai.tools.types import ToolResult
from app.ai.types import ChatMessage

from .recovery_manager import RecoveryManager
from .turn_diagnostics import TurnDiagnostics
from .types import (
    ExecutionBudget,
    IntentPlan,
    PreparedExecution,
    ProviderFailureKind,
    RecoveryDecision,
)

ExecutionState = Literal[
    "prepared",
    "model_call",
    "tool_round",
    "recovery",
    "awaiting_consent",
    "partial_exit",
    "completed",
    "failed",
    "interrupted",
]


@dataclass
class ExecutionStateMachine:
    intent_plan: list[IntentPlan]
    budget: ExecutionBudget | None
    execution_path: str
    candidate_tool_names: list[str] = field(default_factory=list)
    provider_events: list[dict[str, Any]] = field(default_factory=list)
    recovery_history: list[RecoveryDecision] = field(default_factory=list)
    provider_failure_kind: ProviderFailureKind = "none"
    started_at: float = field(default_factory=time.perf_counter)
    current_state: ExecutionState = "prepared"
    state_history: list[ExecutionState] = field(default_factory=lambda: ["prepared"])

    @classmethod
    def from_prepared_execution(cls, prep: PreparedExecution) -> "ExecutionStateMachine":
        raw_intents = list(getattr(prep, "intent_plan", []) or [])
        normalized_intents: list[IntentPlan] = []
        for intent in raw_intents:
            if isinstance(intent, IntentPlan):
                normalized_intents.append(IntentPlan(**intent.to_dict()))
            elif isinstance(intent, dict):
                normalized_intents.append(IntentPlan(**intent))
        return cls(
            intent_plan=normalized_intents,
            budget=getattr(prep, "execution_budget", None),
            execution_path=getattr(prep, "execution_path", "fast"),
            candidate_tool_names=[
                tool.name for tool in (getattr(prep, "tools", []) or [])
            ],
            provider_events=list(getattr(prep, "provider_events", []) or []),
            recovery_history=list(getattr(prep, "recovery_history", []) or []),
        )

    def sync_elapsed(self) -> None:
        if self.budget is not None:
            self.budget.elapsed_ms_used = int((time.perf_counter() - self.started_at) * 1000)

    def transition(self, state: ExecutionState) -> None:
        self.current_state = state
        if not self.state_history or self.state_history[-1] != state:
            self.state_history.append(state)

    def register_completion_tokens(self, completion_tokens: int) -> None:
        self.transition("model_call")
        if self.budget is not None:
            self.budget.completion_tokens_used = max(
                self.budget.completion_tokens_used,
                int(completion_tokens or 0),
            )

    def register_tool_round(self) -> None:
        self.transition("tool_round")
        if self.budget is not None:
            self.budget.tool_rounds_used += 1
            self.sync_elapsed()

    def register_tool_results(
        self,
        *,
        messages: list[ChatMessage],
        tool_results: list[ToolResult],
    ) -> None:
        if tool_results:
            self.transition("tool_round")
        if self.budget is not None:
            self.budget.tool_result_bytes_used += sum(
                len((result.output or result.error or "").encode("utf-8"))
                for result in tool_results
            )
        self.intent_plan = RecoveryManager.update_intent_statuses(
            self.intent_plan,
            messages=messages,
            tool_results=tool_results,
        )

    def register_retry(self, decision: RecoveryDecision) -> None:
        self.transition("recovery")
        self.recovery_history.append(decision)
        if self.budget is not None and decision.target_intent_id:
            retries = int(self.budget.retries_by_intent.get(decision.target_intent_id, 0) or 0)
            self.budget.retries_by_intent[decision.target_intent_id] = retries + 1

    def register_provider_failure(
        self,
        *,
        kind: ProviderFailureKind,
        event: dict[str, Any] | None = None,
    ) -> None:
        if kind != "none":
            self.transition("failed" if kind != "budget_exit" else "partial_exit")
        self.provider_failure_kind = kind
        if event:
            self.provider_events.append(dict(event))

    def budget_exit_reason(self) -> str | None:
        self.sync_elapsed()
        if self.budget is None:
            return None
        return self.budget.first_exceeded_reason()

    def build_diagnostics_payload(self) -> dict[str, Any]:
        return TurnDiagnostics.build_payload(
            execution_path=self.execution_path,
            budget=self.budget,
            intents=self.intent_plan,
            recovery_history=self.recovery_history,
            provider_events=self.provider_events,
            provider_failure_kind=self.provider_failure_kind,
            candidate_tool_names=self.candidate_tool_names,
            current_state=self.current_state,
            state_history=self.state_history,
        )


__all__ = ["ExecutionStateMachine"]
