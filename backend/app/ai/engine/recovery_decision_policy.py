"""Decision and stop-loss helpers extracted from RecoveryManager."""

from __future__ import annotations

from typing import Any

from .types import ExecutionBudget, IntentPlan, ProviderFailureKind, RecoveryDecision

_BUDGET_EXIT_REASONS: frozenset[str] = frozenset(
    {
        "prompt_budget_exceeded",
        "completion_budget_exceeded",
        "tool_round_budget_exceeded",
        "elapsed_budget_exceeded",
        "tool_result_budget_exceeded",
        "candidate_tool_budget_exceeded",
    }
)
_RETRYABLE_FAILURE_KINDS: frozenset[ProviderFailureKind] = frozenset(
    {"tool_timeout", "tool_execution_error", "provider_timeout", "provider_rate_limit"}
)
_TERMINAL_FAILURE_KINDS: frozenset[ProviderFailureKind] = frozenset(
    {
        "provider_unavailable",
        "provider_http_5xx",
        "provider_bad_response",
        "server_interrupt",
    }
)


def is_budget_exit_reason(reason: str) -> bool:
    return reason in _BUDGET_EXIT_REASONS


def is_retryable_failure_kind(kind: ProviderFailureKind) -> bool:
    return kind in _RETRYABLE_FAILURE_KINDS


def is_terminal_failure_kind(kind: ProviderFailureKind) -> bool:
    return kind == "budget_exit" or kind in _TERMINAL_FAILURE_KINDS


def next_unfinished_intents(intents: list[IntentPlan]) -> list[IntentPlan]:
    return [
        intent for intent in intents if intent.status not in {"completed", "skipped"}
    ]


def pending_consent_intent(intents: list[IntentPlan]) -> IntentPlan | None:
    for intent in intents:
        if intent.status == "awaiting_consent":
            return intent
    return None


def decide(
    intents: list[IntentPlan],
    *,
    budget: ExecutionBudget | None,
    provider_failure_kind: ProviderFailureKind = "none",
) -> RecoveryDecision | None:
    unfinished = next_unfinished_intents(intents)
    completed = [intent.intent_id for intent in intents if intent.status == "completed"]
    pending_intent = pending_consent_intent(intents)
    if pending_intent:
        pending_meta = (pending_intent.metadata or {}).get("pending_consent")
        payload = dict(pending_meta) if isinstance(pending_meta, dict) else None
        metadata: dict[str, Any] = {}
        if payload:
            metadata["pending_consent"] = payload
        return RecoveryDecision(
            action="pause_for_consent",
            target_intent_id=pending_intent.intent_id,
            completed_intent_ids=completed,
            unfinished_intent_ids=[intent.intent_id for intent in unfinished],
            reason="awaiting_user_consent",
            provider_failure_kind=provider_failure_kind,
            metadata=metadata,
        )

    budget_exit_reason = budget.first_exceeded_reason() if budget is not None else None
    if budget_exit_reason:
        return RecoveryDecision(
            action="return_partial",
            completed_intent_ids=completed,
            unfinished_intent_ids=[intent.intent_id for intent in unfinished],
            reason=budget_exit_reason,
            provider_failure_kind="budget_exit",
            metadata={},
        )
    if provider_failure_kind == "budget_exit":
        return RecoveryDecision(
            action="return_partial",
            completed_intent_ids=completed,
            unfinished_intent_ids=[intent.intent_id for intent in unfinished],
            reason="budget_exit",
            provider_failure_kind=provider_failure_kind,
            metadata={},
        )
    if not unfinished and provider_failure_kind == "none":
        return None
    if unfinished:
        target = unfinished[0]
        if provider_failure_kind != "none" and not is_retryable_failure_kind(
            provider_failure_kind
        ):
            return RecoveryDecision(
                action="return_partial",
                completed_intent_ids=completed,
                unfinished_intent_ids=[intent.intent_id for intent in unfinished],
                reason="terminal_failure",
                provider_failure_kind=provider_failure_kind,
                metadata={},
            )
        retry_count = int(
            (
                budget.retries_by_intent.get(target.intent_id, 0)
                if budget is not None
                else 0
            )
            or 0
        )
        if budget is not None and retry_count >= budget.max_retry_per_intent:
            return RecoveryDecision(
                action="return_partial",
                completed_intent_ids=completed,
                unfinished_intent_ids=[intent.intent_id for intent in unfinished],
                reason="retry_budget_exhausted",
                provider_failure_kind=provider_failure_kind,
                metadata={},
            )
        allowed_tool_names: list[str] = []
        seen: set[str] = set()
        target_family = str(target.family or "").strip().casefold()
        for intent in unfinished:
            intent_family = str(intent.family or "").strip().casefold()
            if intent_family != target_family:
                continue
            for name in intent.allowed_tool_names:
                if name and name not in seen:
                    seen.add(name)
                    allowed_tool_names.append(name)
        return RecoveryDecision(
            action="retry_intent",
            target_intent_id=target.intent_id,
            retry_family=target.family,
            allowed_tool_names=allowed_tool_names or list(target.allowed_tool_names),
            completed_intent_ids=completed,
            unfinished_intent_ids=[intent.intent_id for intent in unfinished],
            reason="unfinished_intent_retry",
            provider_failure_kind=provider_failure_kind,
            metadata={},
        )
    if provider_failure_kind != "none":
        return RecoveryDecision(
            action="return_partial",
            completed_intent_ids=completed,
            unfinished_intent_ids=[],
            reason=(
                "terminal_failure"
                if is_terminal_failure_kind(provider_failure_kind)
                else "provider_failure_after_partial_progress"
            ),
            provider_failure_kind=provider_failure_kind,
        )
    return RecoveryDecision(
        action="return_partial",
        completed_intent_ids=completed,
        unfinished_intent_ids=[],
        reason="provider_failure_after_partial_progress",
        provider_failure_kind=provider_failure_kind,
    )


__all__ = [
    "decide",
    "is_budget_exit_reason",
    "is_retryable_failure_kind",
    "is_terminal_failure_kind",
    "next_unfinished_intents",
    "pending_consent_intent",
]
