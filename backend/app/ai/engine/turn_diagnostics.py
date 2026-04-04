"""Helpers to serialize orchestration diagnostics."""

from __future__ import annotations

from typing import Any

from .types import ExecutionBudget, IntentPlan, RecoveryDecision


class TurnDiagnostics:
    @staticmethod
    def serialize_intents(intents: list[IntentPlan]) -> list[dict[str, Any]]:
        return [intent.to_dict() for intent in intents]

    @staticmethod
    def serialize_recovery(history: list[RecoveryDecision]) -> list[dict[str, Any]]:
        return [decision.to_dict() for decision in history]

    @staticmethod
    def build_payload(
        *,
        execution_path: str | None,
        budget: ExecutionBudget | None,
        intents: list[IntentPlan],
        recovery_history: list[RecoveryDecision],
        provider_events: list[dict[str, Any]],
        provider_failure_kind: str,
        candidate_tool_names: list[str],
        current_state: str | None = None,
        state_history: list[str] | None = None,
    ) -> dict[str, Any]:
        unfinished_intents = [
            intent.intent_id for intent in intents if intent.status != "completed"
        ]
        retry_events = TurnDiagnostics.serialize_recovery(recovery_history)
        partial_exit_reason = next(
            (
                decision.reason
                for decision in reversed(recovery_history)
                if decision.action == "return_partial"
            ),
            None,
        )
        payload = {
            "execution_path": execution_path,
            "intent_plan": TurnDiagnostics.serialize_intents(intents),
            "unfinished_intents": unfinished_intents,
            "routing": {"candidate_tool_names": list(candidate_tool_names)},
            "recovery": {
                "retry_events": retry_events,
                "unfinished_intents": unfinished_intents,
                "partial_exit_reason": partial_exit_reason,
            },
            "failures": {
                "failure_kind": provider_failure_kind,
                "provider_events": list(provider_events),
            },
            "retry_events": retry_events,
            "partial_exit_reason": partial_exit_reason,
            "failure_kind": provider_failure_kind,
            "provider_events": list(provider_events),
            "candidate_tool_names": list(candidate_tool_names),
            "current_state": current_state,
            "state_history": list(state_history or []),
        }
        if budget is not None:
            budget_snapshot = budget.snapshot()
            payload["budget"] = budget_snapshot
            payload["budget_status"] = budget_snapshot.get("status")
            payload["budget_exit_reason"] = budget_snapshot.get("exit_reason")
        return payload


__all__ = ["TurnDiagnostics"]
