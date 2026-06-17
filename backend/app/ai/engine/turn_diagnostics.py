"""Helpers to serialize orchestration diagnostics."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Literal

from .types import ExecutionBudget, IntentPlan, RecoveryDecision

TurnEventKind = Literal[
    "turn.started",
    "turn.intent_planned",
    "turn.path_selected",
    "turn.capability_gated",
    "turn.tools_filtered",
    "turn.model_called",
    "turn.tool_round",
    "turn.tool_completed",
    "turn.tool_failed",
    "turn.budget_checked",
    "turn.recovery_decided",
    "turn.partial_exit",
    "turn.consent_paused",
    "turn.completed",
    "turn.failed",
]

_PREPARATION_DIAGNOSTIC_PASSTHROUGH_KEYS = (
    "partial_exit_reason",
    "untrusted_final_output_fallback_applied",
    "stripped_untrusted_final_output",
)


@dataclass
class TurnEvent:
    """Canonical machine-readable turn event."""

    kind: TurnEventKind
    timestamp_ms: int
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "timestamp_ms": int(self.timestamp_ms or 0),
            "data": dict(self.data or {}),
        }


class TurnDiagnostics:
    @staticmethod
    def _as_dict(value: Any) -> dict[str, Any]:
        if isinstance(value, Mapping):
            return dict(value)
        return {}

    @staticmethod
    def _as_int(value: Any, default: int = 0) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return int(default)

    @staticmethod
    def _as_bool(value: Any, default: bool = False) -> bool:
        if isinstance(value, bool):
            return value
        if value is None:
            return default
        normalized = str(value).strip().lower()
        if normalized in {"true", "1", "yes", "y", "on"}:
            return True
        if normalized in {"false", "0", "no", "n", "off"}:
            return False
        return bool(value)

    @staticmethod
    def _as_text(value: Any) -> str | None:
        text = str(value or "").strip()
        return text or None

    @staticmethod
    def _normalize_token(value: Any) -> str:
        return str(value or "").strip().lower()

    @staticmethod
    def _path_reason(
        *,
        execution_path: str | None,
        intent_count: int,
        all_shortcircuit: bool,
    ) -> str:
        if all_shortcircuit:
            return "all_shortcircuit"
        if (execution_path or "") == "fast" and intent_count <= 1:
            return "single_intent"
        if (execution_path or "") == "normal":
            return "bounded_multi_intent"
        if (execution_path or "") == "deep":
            return "complex_multi_intent"
        if (execution_path or "") == "react":
            return "react_autonomous"
        return "default_path"

    @staticmethod
    def build_path_decision(
        *,
        execution_path: str | None,
        intents: list[IntentPlan],
        preparation_diagnostics: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        prep_diagnostics = TurnDiagnostics._as_dict(preparation_diagnostics)
        explicit_decision = TurnDiagnostics._as_dict(
            prep_diagnostics.get("path_decision")
        )
        intent_count = len(intents)
        all_shortcircuit = bool(intents) and all(
            bool(getattr(intent, "shortcircuit", False)) for intent in intents
        )
        explicit_reason = (
            explicit_decision.get("reason")
            or prep_diagnostics.get("execution_path_reason")
            or prep_diagnostics.get("path_reason")
        )
        reason = str(explicit_reason).strip() if explicit_reason else ""
        if not reason:
            reason = TurnDiagnostics._path_reason(
                execution_path=execution_path,
                intent_count=intent_count,
                all_shortcircuit=all_shortcircuit,
            )
        return {
            "path": str(explicit_decision.get("path") or execution_path or "fast"),
            "reason": reason,
            "all_shortcircuit": (
                bool(explicit_decision.get("all_shortcircuit"))
                if "all_shortcircuit" in explicit_decision
                else all_shortcircuit
            ),
            "intent_count": (
                TurnDiagnostics._as_int(
                    explicit_decision.get("intent_count"),
                    intent_count,
                )
                if "intent_count" in explicit_decision
                else intent_count
            ),
        }

    @staticmethod
    def build_capability_injection(
        *,
        preparation_diagnostics: dict[str, Any] | None = None,
        path_decision: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        prep_diagnostics = TurnDiagnostics._as_dict(preparation_diagnostics)
        normalized_path = TurnDiagnostics._as_dict(path_decision)
        raw = TurnDiagnostics._as_dict(
            prep_diagnostics.get("capability_injection")
            or prep_diagnostics.get("capability_injection_decision")
        )
        all_shortcircuit = bool(normalized_path.get("all_shortcircuit"))
        bypass_reason = str(raw.get("bypass_reason") or "").strip() or None
        if bypass_reason is None and all_shortcircuit:
            bypass_reason = "all_shortcircuit"
        return {
            "skills_injected": bool(raw.get("skills_injected", False)),
            "kb_injected": bool(raw.get("kb_injected", False)),
            "memory_injected": bool(raw.get("memory_injected", False)),
            "bypass_reason": bypass_reason,
        }

    @staticmethod
    def build_tool_filtering(
        *,
        candidate_tool_names: list[str],
        all_tool_names: list[str] | None = None,
        budget: ExecutionBudget | None = None,
        path_decision: dict[str, Any] | None = None,
        preparation_diagnostics: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        prep_diagnostics = TurnDiagnostics._as_dict(preparation_diagnostics)
        normalized_path = TurnDiagnostics._as_dict(path_decision)
        raw_filtering = TurnDiagnostics._as_dict(
            prep_diagnostics.get("tool_filtering")
            or prep_diagnostics.get("tool_filtering_reason")
        )
        all_count = TurnDiagnostics._as_int(
            raw_filtering.get("all_tools_count"),
            len(all_tool_names or []),
        )
        candidate_count = TurnDiagnostics._as_int(
            raw_filtering.get("candidate_tools_count"),
            len(candidate_tool_names or []),
        )
        filtering_reason = str(raw_filtering.get("filtering_reason") or "").strip()
        if not filtering_reason:
            if all_count <= candidate_count:
                filtering_reason = "all_tools_allowed"
            elif (
                budget is not None
                and int(getattr(budget, "max_candidate_tools", 0) or 0) > 0
                and candidate_count >= int(getattr(budget, "max_candidate_tools", 0))
            ):
                filtering_reason = "budget_capped"
            elif bool(normalized_path.get("all_shortcircuit")):
                filtering_reason = "intent_scoped_shortcircuit"
            else:
                filtering_reason = "intent_scoped"
        return {
            "all_tools_count": max(0, all_count),
            "candidate_tools_count": max(0, candidate_count),
            "filtering_reason": filtering_reason,
        }

    @staticmethod
    def serialize_intents(intents: list[IntentPlan]) -> list[dict[str, Any]]:
        return [intent.to_dict() for intent in intents]

    @staticmethod
    def serialize_recovery(history: list[RecoveryDecision]) -> list[dict[str, Any]]:
        serialized: list[dict[str, Any]] = []
        for decision in history:
            if isinstance(decision, RecoveryDecision):
                serialized.append(decision.to_dict())
            elif isinstance(decision, Mapping):
                serialized.append(dict(decision))
        return serialized

    @staticmethod
    def serialize_turn_events(
        events: list[TurnEvent | dict[str, Any]] | None,
    ) -> list[dict[str, Any]]:
        serialized: list[dict[str, Any]] = []
        for event in events or []:
            if isinstance(event, TurnEvent):
                serialized.append(event.to_dict())
                continue
            if isinstance(event, Mapping):
                kind = str(event.get("kind") or "").strip()
                if not kind:
                    continue
                serialized.append(
                    {
                        "kind": kind,
                        "timestamp_ms": TurnDiagnostics._as_int(
                            event.get("timestamp_ms"),
                            0,
                        ),
                        "data": TurnDiagnostics._as_dict(event.get("data")),
                    }
                )
        return serialized

    @staticmethod
    def build_recovery_chain(history: list[RecoveryDecision]) -> list[dict[str, Any]]:
        chain: list[dict[str, Any]] = []
        for index, decision in enumerate(history):
            payload = (
                decision.to_dict()
                if isinstance(decision, RecoveryDecision)
                else dict(decision)
                if isinstance(decision, Mapping)
                else {}
            )
            if not payload:
                continue
            item = {
                "step": index + 1,
                "action": str(payload.get("action") or "none"),
                "target_intent": (
                    str(payload.get("target_intent_id") or "").strip() or None
                ),
                "reason": str(payload.get("reason") or ""),
                "provider_failure_kind": str(
                    payload.get("provider_failure_kind") or "none"
                ),
            }
            chain.append(item)
        return chain

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
        all_tool_names: list[str] | None = None,
        preparation_diagnostics: dict[str, Any] | None = None,
        current_state: str | None = None,
        state_history: list[str] | None = None,
        turn_events: list[TurnEvent | dict[str, Any]] | None = None,
        cache_insights: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        unfinished_intents = [
            intent.intent_id for intent in intents if intent.status != "completed"
        ]
        active_intent_id = next(
            (
                intent.intent_id
                for intent in intents
                if intent.status not in {"completed", "failed", "skipped"}
                and intent.family != "none"
                and intent.requires_tools
            ),
            None,
        ) or TurnDiagnostics._as_text(
            TurnDiagnostics._as_dict(preparation_diagnostics).get("active_intent_id")
        )
        retry_events = TurnDiagnostics.serialize_recovery(recovery_history)
        recovery_chain = TurnDiagnostics.build_recovery_chain(recovery_history)
        prep_diagnostics = TurnDiagnostics._as_dict(preparation_diagnostics)
        tool_planner = TurnDiagnostics._as_dict(prep_diagnostics.get("tool_planner"))
        continuation_source = TurnDiagnostics._as_text(
            prep_diagnostics.get("continuation_source")
        )
        contract_breach_type = TurnDiagnostics._as_text(
            prep_diagnostics.get("contract_breach_type")
        )
        final_output_source = TurnDiagnostics._as_text(
            prep_diagnostics.get("final_output_source")
        )
        post_tool_completion_state = TurnDiagnostics._as_text(
            prep_diagnostics.get("post_tool_completion_state")
        )
        provider_failure_recovered_from_tool_evidence = TurnDiagnostics._as_bool(
            prep_diagnostics.get("provider_failure_recovered_from_tool_evidence"),
            False,
        )
        recovered_completed_output_rebuilt_from_tool_evidence = (
            TurnDiagnostics._as_bool(
                prep_diagnostics.get(
                    "recovered_completed_output_rebuilt_from_tool_evidence"
                ),
                False,
            )
        )
        recovered_provider_failure_kind = TurnDiagnostics._as_text(
            prep_diagnostics.get("recovered_provider_failure_kind")
        )
        recovered_provider_events = (
            list(prep_diagnostics.get("recovered_provider_events") or [])
            if isinstance(prep_diagnostics.get("recovered_provider_events"), list)
            else []
        )
        assistant_claimed_tool_call_without_tool_event = TurnDiagnostics._as_bool(
            prep_diagnostics.get("assistant_claimed_tool_call_without_tool_event"),
            False,
        )
        path_decision = TurnDiagnostics.build_path_decision(
            execution_path=execution_path,
            intents=intents,
            preparation_diagnostics=preparation_diagnostics,
        )
        capability_injection = TurnDiagnostics.build_capability_injection(
            preparation_diagnostics=preparation_diagnostics,
            path_decision=path_decision,
        )
        tool_filtering = TurnDiagnostics.build_tool_filtering(
            candidate_tool_names=candidate_tool_names,
            all_tool_names=all_tool_names,
            budget=budget,
            path_decision=path_decision,
            preparation_diagnostics=preparation_diagnostics,
        )
        serialized_turn_events = TurnDiagnostics.serialize_turn_events(turn_events)
        budget_snapshot = budget.snapshot() if budget is not None else None
        budget_exit_reason = (
            str(budget_snapshot.get("exit_reason") or "").strip()
            if isinstance(budget_snapshot, dict)
            else ""
        )
        partial_exit_reason = next(
            (
                decision.reason
                for decision in reversed(recovery_history)
                if decision.action == "return_partial"
            ),
            None,
        )
        if not partial_exit_reason and current_state == "partial_exit":
            partial_exit_reason = budget_exit_reason or (
                "provider_failure_after_partial_progress"
                if provider_failure_kind != "none"
                else None
            )
        conversation_outcome = "success"
        if current_state == "awaiting_consent":
            conversation_outcome = "awaiting_consent"
        elif current_state == "partial_exit" or partial_exit_reason:
            conversation_outcome = "partial"
        elif current_state == "failed" or provider_failure_kind != "none":
            conversation_outcome = "failed"
        elif unfinished_intents and current_state != "completed":
            conversation_outcome = "partial"
        payload = {
            "execution_path": execution_path,
            "intent_plan": TurnDiagnostics.serialize_intents(intents),
            "unfinished_intents": unfinished_intents,
            "tool_planner": tool_planner or None,
            "active_intent_id": active_intent_id,
            "continuation_source": continuation_source,
            "conversation_outcome": conversation_outcome,
            "path_decision": path_decision,
            "capability_injection": capability_injection,
            "tool_filtering": tool_filtering,
            "recovery_chain": recovery_chain,
            "turn_events": serialized_turn_events,
            "routing": {
                "candidate_tool_names": list(candidate_tool_names),
                "tool_filtering": tool_filtering,
            },
            "recovery": {
                "retry_events": retry_events,
                "unfinished_intents": unfinished_intents,
                "partial_exit_reason": partial_exit_reason,
                "recovery_chain": recovery_chain,
            },
            "failures": {
                "failure_kind": provider_failure_kind,
                "provider_events": list(provider_events),
                "provider_failure_recovered_from_tool_evidence": (
                    provider_failure_recovered_from_tool_evidence
                ),
                "recovered_completed_output_rebuilt_from_tool_evidence": (
                    recovered_completed_output_rebuilt_from_tool_evidence
                ),
                "recovered_provider_failure_kind": recovered_provider_failure_kind,
                "recovered_provider_events": recovered_provider_events,
            },
            "retry_events": retry_events,
            "partial_exit_reason": partial_exit_reason,
            "failure_kind": provider_failure_kind,
            "provider_events": list(provider_events),
            "candidate_tool_names": list(candidate_tool_names),
            "contract_breach_type": contract_breach_type,
            "final_output_source": final_output_source,
            "post_tool_completion_state": post_tool_completion_state,
            "provider_failure_recovered_from_tool_evidence": (
                provider_failure_recovered_from_tool_evidence
            ),
            "recovered_completed_output_rebuilt_from_tool_evidence": (
                recovered_completed_output_rebuilt_from_tool_evidence
            ),
            "recovered_provider_failure_kind": recovered_provider_failure_kind,
            "recovered_provider_events": recovered_provider_events,
            "assistant_claimed_tool_call_without_tool_event": (
                assistant_claimed_tool_call_without_tool_event
            ),
            "current_state": current_state,
            "state_history": list(state_history or []),
        }
        if budget_snapshot is not None:
            budget_usage = (
                TurnDiagnostics._as_dict(budget_snapshot.get("usage"))
                if isinstance(budget_snapshot, dict)
                else {}
            )
            payload["budget"] = budget_snapshot
            payload["budget_status"] = budget_snapshot.get("status")
            payload["budget_exit_reason"] = budget_snapshot.get("exit_reason")
            payload["elapsed_over_limit"] = bool(
                budget_snapshot.get("elapsed_over_limit")
                or budget_usage.get("elapsed_over_limit")
            )
            payload["elapsed_over_limit_ms"] = TurnDiagnostics._as_int(
                budget_snapshot.get("elapsed_over_limit_ms"),
                TurnDiagnostics._as_int(
                    budget_usage.get("elapsed_over_limit_ms"),
                    0,
                ),
            )
            payload["elapsed_limit_ms"] = TurnDiagnostics._as_int(
                budget_snapshot.get("elapsed_limit_ms"),
                TurnDiagnostics._as_int(
                    budget_usage.get("elapsed_limit_ms"),
                    0,
                ),
            )
        if cache_insights is not None:
            payload["cache_hits"] = dict(cache_insights)
        for key in _PREPARATION_DIAGNOSTIC_PASSTHROUGH_KEYS:
            if key not in prep_diagnostics:
                continue
            value = prep_diagnostics.get(key)
            if value in (None, [], {}, ""):
                continue
            current_value = payload.get(key)
            if current_value in (None, [], {}, ""):
                payload[key] = value
        return payload


__all__ = ["TurnDiagnostics", "TurnEvent", "TurnEventKind"]
