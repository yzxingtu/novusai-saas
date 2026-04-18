"""Shared mutable orchestration state for streaming and non-streaming flows."""

from __future__ import annotations

import contextvars
import time
from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from typing import Any, Literal

from app.ai.tools.types import ToolResult
from app.ai.types import ChatMessage

_CURRENT_EXECUTION_STATE_MACHINE: ContextVar[
    "ExecutionStateMachine | None"
] = contextvars.ContextVar(
    "execution_state_machine.current",
    default=None,
)


def get_current_execution_state_machine() -> "ExecutionStateMachine | None":
    return _CURRENT_EXECUTION_STATE_MACHINE.get()


def set_current_execution_state_machine(
    state: "ExecutionStateMachine",
) -> Token:
    return _CURRENT_EXECUTION_STATE_MACHINE.set(state)


def reset_current_execution_state_machine(token: Token) -> None:
    _CURRENT_EXECUTION_STATE_MACHINE.reset(token)

from .recovery_manager import RecoveryManager
from .turn_diagnostics import TurnDiagnostics, TurnEvent, TurnEventKind
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
    all_tool_names: list[str] = field(default_factory=list)
    preparation_diagnostics: dict[str, Any] = field(default_factory=dict)
    provider_events: list[dict[str, Any]] = field(default_factory=list)
    recovery_history: list[RecoveryDecision] = field(default_factory=list)
    provider_failure_kind: ProviderFailureKind = "none"
    readonly_tool_cache: dict[str, tuple[ToolResult, int]] = field(
        default_factory=dict,
        repr=False,
    )
    page_context_cache: dict[str, tuple[ToolResult, int]] = field(
        default_factory=dict,
        repr=False,
    )
    search_query_cache: dict[str, tuple[ToolResult, int]] = field(
        default_factory=dict,
        repr=False,
    )
    cache_hit_kinds: set[str] = field(default_factory=set, repr=False)
    dedupe_hit: bool = False
    page_context_cache_hit: bool = False
    started_at: float = field(default_factory=time.perf_counter)
    current_state: ExecutionState = "prepared"
    state_history: list[ExecutionState] = field(default_factory=lambda: ["prepared"])
    turn_events: list[TurnEvent] = field(default_factory=list)
    _context_token: Token | None = field(default=None, init=False, repr=False)
    _last_budget_exit_reason: str | None = field(
        default=None,
        init=False,
        repr=False,
    )

    @classmethod
    def from_prepared_execution(cls, prep: PreparedExecution) -> ExecutionStateMachine:
        raw_intents = list(getattr(prep, "intent_plan", []) or [])
        raw_recovery_history = list(getattr(prep, "recovery_history", []) or [])
        normalized_intents: list[IntentPlan] = []
        normalized_recovery_history: list[RecoveryDecision] = []
        for intent in raw_intents:
            if isinstance(intent, IntentPlan):
                normalized_intents.append(IntentPlan(**intent.to_dict()))
            elif isinstance(intent, dict):
                normalized_intents.append(IntentPlan(**intent))
        for decision in raw_recovery_history:
            if isinstance(decision, RecoveryDecision):
                normalized_recovery_history.append(
                    RecoveryDecision(**decision.to_dict())
                )
            elif isinstance(decision, dict):
                normalized_recovery_history.append(RecoveryDecision(**decision))

        candidate_tool_names = [tool.name for tool in (getattr(prep, "tools", []) or [])]
        all_tool_names = [tool.name for tool in (getattr(prep, "all_tools", []) or [])]
        if not all_tool_names:
            all_tool_names = list(candidate_tool_names)

        machine = cls(
            intent_plan=normalized_intents,
            budget=getattr(prep, "execution_budget", None),
            execution_path=getattr(prep, "execution_path", "fast"),
            candidate_tool_names=candidate_tool_names,
            all_tool_names=all_tool_names,
            preparation_diagnostics=dict(getattr(prep, "diagnostics", {}) or {}),
            provider_events=list(getattr(prep, "provider_events", []) or []),
            recovery_history=normalized_recovery_history,
        )
        machine._context_token = set_current_execution_state_machine(machine)
        machine._emit_initial_events()
        return machine

    def _elapsed_ms(self) -> int:
        return max(0, int((time.perf_counter() - self.started_at) * 1000))

    def emit_event(
        self,
        kind: TurnEventKind,
        data: dict[str, Any] | None = None,
    ) -> None:
        self.turn_events.append(
            TurnEvent(
                kind=kind,
                timestamp_ms=self._elapsed_ms(),
                data=dict(data or {}),
            )
        )

    def _emit_budget_checked(self, *, force: bool = False) -> None:
        if self.budget is None:
            return
        snapshot = self.budget.snapshot()
        exit_reason = snapshot.get("exit_reason")
        normalized_exit_reason = str(exit_reason).strip() if exit_reason else None
        if not force and normalized_exit_reason == self._last_budget_exit_reason:
            return
        self._last_budget_exit_reason = normalized_exit_reason
        usage = snapshot.get("usage") if isinstance(snapshot.get("usage"), dict) else {}
        self.emit_event(
            "turn.budget_checked",
            {
                "status": snapshot.get("status"),
                "exit_reason": normalized_exit_reason,
                "tool_rounds_used": int(usage.get("tool_rounds_used") or 0),
                "completion_tokens_used": int(usage.get("completion_tokens_used") or 0),
                "elapsed_ms_used": int(usage.get("elapsed_ms_used") or 0),
                "elapsed_limit_ms": int(
                    snapshot.get("elapsed_limit_ms")
                    or usage.get("elapsed_limit_ms")
                    or 0
                ),
                "elapsed_over_limit": bool(
                    snapshot.get("elapsed_over_limit")
                    or usage.get("elapsed_over_limit")
                ),
                "elapsed_over_limit_ms": int(
                    snapshot.get("elapsed_over_limit_ms")
                    or usage.get("elapsed_over_limit_ms")
                    or 0
                ),
                "tool_result_bytes_used": int(usage.get("tool_result_bytes_used") or 0),
            },
        )

    def _emit_initial_events(self) -> None:
        path_decision = TurnDiagnostics.build_path_decision(
            execution_path=self.execution_path,
            intents=self.intent_plan,
            preparation_diagnostics=self.preparation_diagnostics,
        )
        capability_injection = TurnDiagnostics.build_capability_injection(
            preparation_diagnostics=self.preparation_diagnostics,
            path_decision=path_decision,
        )
        tool_filtering = TurnDiagnostics.build_tool_filtering(
            candidate_tool_names=self.candidate_tool_names,
            all_tool_names=self.all_tool_names,
            budget=self.budget,
            path_decision=path_decision,
            preparation_diagnostics=self.preparation_diagnostics,
        )
        self.emit_event(
            "turn.started",
            {
                "execution_path": self.execution_path,
                "intent_count": len(self.intent_plan),
            },
        )
        self.emit_event(
            "turn.intent_planned",
            {
                "intent_count": len(self.intent_plan),
                "intents": [
                    {
                        "intent_id": intent.intent_id,
                        "kind": intent.kind,
                        "family": intent.family,
                        "status": intent.status,
                        "shortcircuit": bool(intent.shortcircuit),
                    }
                    for intent in self.intent_plan
                ],
            },
        )
        self.emit_event("turn.path_selected", path_decision)
        self.emit_event("turn.capability_gated", capability_injection)
        self.emit_event("turn.tools_filtered", tool_filtering)
        self._emit_budget_checked(force=True)

    def cache_for_kind(
        self,
        kind: str,
    ) -> dict[str, tuple[ToolResult, int]]:
        if kind == "search_query":
            return self.search_query_cache
        if kind == "page_context":
            return self.page_context_cache
        return self.readonly_tool_cache

    def register_cache_hit(self, kind: str) -> None:
        if not kind:
            return
        self.dedupe_hit = True
        self.cache_hit_kinds.add(kind)
        if kind == "page_context":
            self.page_context_cache_hit = True

    def _has_turn_event(self, kind: TurnEventKind) -> bool:
        return any(event.kind == kind for event in self.turn_events)

    def sync_elapsed(self) -> None:
        if self.budget is not None:
            self.budget.elapsed_ms_used = int(
                (time.perf_counter() - self.started_at) * 1000
            )

    def transition(self, state: ExecutionState) -> None:
        previous_state = self.current_state
        self.current_state = state
        changed = not self.state_history or self.state_history[-1] != state
        if changed:
            self.state_history.append(state)
        if not changed or previous_state == state:
            return
        if state == "awaiting_consent":
            self.emit_event("turn.consent_paused", {})
        elif state == "partial_exit":
            partial_reason = next(
                (
                    str(decision.reason or "").strip()
                    for decision in reversed(self.recovery_history)
                    if decision.action == "return_partial"
                    and str(decision.reason or "").strip()
                ),
                None,
            )
            self.emit_event(
                "turn.partial_exit",
                {
                    "reason": partial_reason or self.budget_exit_reason(),
                    "provider_failure_kind": self.provider_failure_kind,
                },
            )
        elif state == "completed":
            self.emit_event("turn.completed", {})
        elif state == "failed":
            if self.provider_failure_kind != "none":
                self.emit_event(
                    "turn.failed",
                    {"provider_failure_kind": self.provider_failure_kind},
                )

    def register_completion_tokens(self, completion_tokens: int) -> None:
        self.transition("model_call")
        if self.budget is not None:
            self.budget.completion_tokens_used = max(
                self.budget.completion_tokens_used,
                int(completion_tokens or 0),
            )
        self.emit_event(
            "turn.model_called",
            {"completion_tokens_used": int(completion_tokens or 0)},
        )
        self._emit_budget_checked()

    def register_tool_round(self) -> None:
        self.transition("tool_round")
        if self.budget is not None:
            self.budget.tool_rounds_used += 1
            self.sync_elapsed()
        self.emit_event(
            "turn.tool_round",
            {
                "tool_rounds_used": (
                    int(self.budget.tool_rounds_used) if self.budget is not None else 0
                )
            },
        )
        self._emit_budget_checked()

    def register_tool_results(
        self,
        *,
        messages: list[ChatMessage],
        turn_messages: list[ChatMessage] | None = None,
        tool_results: list[ToolResult],
    ) -> None:
        if tool_results:
            self.transition("tool_round")
        if self.budget is not None:
            self.budget.tool_result_bytes_used += sum(
                len((result.output or result.error or "").encode("utf-8"))
                for result in tool_results
            )
        for result in tool_results:
            event_data = {
                "tool_call_id": result.tool_call_id,
                "tool_name": result.name,
                "success": bool(result.success),
                "error_type": result.error_type,
            }
            if result.success:
                self.emit_event("turn.tool_completed", event_data)
            else:
                self.emit_event("turn.tool_failed", event_data)
        self.intent_plan = RecoveryManager.update_intent_statuses(
            self.intent_plan,
            messages=messages,
            turn_messages=turn_messages,
            tool_results=tool_results,
        )
        self._emit_budget_checked()

    def register_retry(self, decision: RecoveryDecision) -> None:
        self.transition("recovery")
        self.recovery_history.append(decision)
        self.emit_event(
            "turn.recovery_decided",
            {
                "step": len(self.recovery_history),
                "action": decision.action,
                "target_intent_id": decision.target_intent_id,
                "reason": decision.reason,
                "provider_failure_kind": decision.provider_failure_kind,
            },
        )
        if self.budget is not None and decision.target_intent_id:
            retries = int(
                self.budget.retries_by_intent.get(decision.target_intent_id, 0) or 0
            )
            self.budget.retries_by_intent[decision.target_intent_id] = retries + 1
        self._emit_budget_checked()

    def register_provider_failure(
        self,
        *,
        kind: ProviderFailureKind,
        event: dict[str, Any] | None = None,
    ) -> None:
        self.provider_failure_kind = kind
        if event:
            self.provider_events.append(dict(event))
        if kind in {"tool_timeout", "tool_execution_error"}:
            self.emit_event(
                "turn.tool_failed",
                {
                    "failure_kind": kind,
                    "event": dict(event or {}),
                },
            )
        if (
            kind != "none"
            and self.current_state == "failed"
            and not self._has_turn_event("turn.failed")
        ):
            self.emit_event(
                "turn.failed",
                {
                    "provider_failure_kind": kind,
                    "event": dict(event or {}),
                },
            )
        self._emit_budget_checked(force=(kind == "budget_exit"))

    def next_action(self) -> Literal["call_llm", "handle_tools", "recover", "exit"]:
        """State-machine-driven next action for unified turn execution."""
        if self.current_state == "prepared":
            return "call_llm"
        if self.current_state in {"model_call", "tool_round"}:
            if self.budget_exit_reason():
                return "exit"
            return "call_llm"
        if self.current_state == "recovery":
            return "recover"
        return "exit"

    def budget_exit_reason(self) -> str | None:
        self.sync_elapsed()
        if self.budget is None:
            return None
        self._emit_budget_checked()
        return self.budget.first_exceeded_reason()

    def build_diagnostics_payload(self) -> dict[str, Any]:
        cache_hit_kind = ", ".join(sorted(self.cache_hit_kinds)) or None
        cache_insights = {
            "dedupe_hit": self.dedupe_hit,
            "cache_hit_kind": cache_hit_kind,
            "page_context_cache_hit": self.page_context_cache_hit,
        }
        return TurnDiagnostics.build_payload(
            execution_path=self.execution_path,
            budget=self.budget,
            intents=self.intent_plan,
            recovery_history=self.recovery_history,
            provider_events=self.provider_events,
            provider_failure_kind=self.provider_failure_kind,
            candidate_tool_names=self.candidate_tool_names,
            all_tool_names=self.all_tool_names,
            preparation_diagnostics=self.preparation_diagnostics,
            current_state=self.current_state,
            state_history=self.state_history,
            turn_events=self.turn_events,
            cache_insights=cache_insights,
        )


__all__ = ["ExecutionStateMachine"]
