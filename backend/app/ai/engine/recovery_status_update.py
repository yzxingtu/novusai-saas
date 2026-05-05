"""Intent status update helpers extracted from RecoveryManager."""

from __future__ import annotations

from app.ai.tools.types import ToolResult
from app.ai.types import ChatMessage

from .recovery_consent_helpers import extract_pending_consent_payload
from .recovery_result_normalizer import RecoveryResultNormalizer
from .recovery_tool_result_helpers import (
    intent_recovery_result_max_length,
    intent_result_from_tool_results,
    successful_tool_names,
)
from .system_prompt_intent_helpers import (
    intent_completion_matches as resolve_intent_completion_matches,
)
from .system_prompt_intent_helpers import (
    intent_completion_signals as resolve_intent_completion_signals,
)
from .types import IntentPlan


def update_intent_statuses(
    intents: list[IntentPlan],
    *,
    messages: list[ChatMessage],
    turn_messages: list[ChatMessage] | None = None,
    tool_results: list[ToolResult] | None = None,
) -> list[IntentPlan]:
    evidence_messages = turn_messages if turn_messages is not None else messages
    completed_tool_names = set(successful_tool_names(evidence_messages, tool_results))
    pending_payload = extract_pending_consent_payload(messages)
    pending_tool_name = (
        str((pending_payload or {}).get("tool_name") or "").strip()
        if isinstance(pending_payload, dict)
        else ""
    )
    pending_consent_assigned = False
    updated: list[IntentPlan] = []

    for intent in intents:
        clone = IntentPlan(**intent.to_dict())
        clone.metadata = dict(clone.metadata or {})
        clone.metadata.pop("pending_consent", None)

        normalized_completion_signals = resolve_intent_completion_signals(
            clone.family,
            intent_kind=clone.kind,
            allowed_tool_names=list(clone.allowed_tool_names or []),
            preferred_tool_names=list(clone.preferred_tool_names or []),
            intent_metadata=clone.metadata,
        )
        if normalized_completion_signals:
            clone.completion_signals = list(normalized_completion_signals)
        completion_matches = resolve_intent_completion_matches(
            clone.family,
            completed_tool_names=completed_tool_names,
            intent_kind=clone.kind,
            allowed_tool_names=list(clone.allowed_tool_names or []),
            preferred_tool_names=list(clone.preferred_tool_names or []),
            intent_metadata=clone.metadata,
        )
        completion_signals = set(clone.completion_signals or clone.allowed_tool_names)
        if clone.family == "none" or not clone.requires_tools:
            clone.status = "completed"
        elif completion_matches:
            clone.status = "completed"
            clone.completed_by_tool_names = list(completion_matches)

        if clone.status == "completed":
            cached_result = None
            result_max_length = intent_recovery_result_max_length(clone)
            if not cached_result:
                cached_result = intent_result_from_tool_results(clone, tool_results)
            if not cached_result:
                cached_result = RecoveryResultNormalizer._intent_cached_result(
                    clone,
                    max_length=result_max_length,
                )
            if cached_result:
                RecoveryResultNormalizer._cache_intent_result(
                    clone,
                    cached_result,
                    max_length=result_max_length,
                )
        elif clone.status not in {"failed", "skipped"}:
            clone.status = "pending"
            partial_result = intent_result_from_tool_results(clone, tool_results)
            if partial_result:
                RecoveryResultNormalizer._cache_partial_intent_result(
                    clone,
                    partial_result,
                )

        if (
            pending_payload
            and not pending_consent_assigned
            and clone.requires_tools
            and clone.status not in {"failed", "skipped"}
            and (
                clone.status != "completed"
                or (pending_tool_name and pending_tool_name in completion_signals)
            )
        ):
            clone.status = "awaiting_consent"
            clone.cached_result = None
            clone.completed_by_tool_names = []
            clone.metadata["pending_consent"] = dict(pending_payload)
            pending_consent_assigned = True

        updated.append(clone)
    return updated


__all__ = ["update_intent_statuses"]
