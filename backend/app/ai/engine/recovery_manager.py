"""Intent-scoped recovery and partial-exit helpers."""

from __future__ import annotations

from .recovery_consent_helpers import (
    ensure_latest_assistant_pending_consent as _ensure_latest_assistant_pending_consent_impl,
)
from .recovery_consent_helpers import (
    extract_pending_consent_payload as _extract_pending_consent_payload_impl,
)
from .recovery_consent_helpers import (
    pending_consent_payload_from_decision as _pending_consent_payload_from_decision_impl,
)
from .recovery_consent_helpers import (
    pending_consent_payload_from_tool_calls as _pending_consent_payload_from_tool_calls_impl,
)
from .recovery_decision_policy import (
    decide,
    is_budget_exit_reason,
    is_retryable_failure_kind,
    is_terminal_failure_kind,
    next_unfinished_intents,
)
from .recovery_prompt_builders import (
    build_completed_output,
    build_missing_args_clarification_message,
    build_partial_output,
    build_partial_response_prompt,
    build_recovery_message,
    has_completed_output_evidence,
)
from .recovery_status_update import update_intent_statuses
from .types import RecoveryDecision


class RecoveryManager:
    """Thin facade for recovery helpers during the staged split."""

    is_budget_exit_reason = staticmethod(is_budget_exit_reason)
    is_retryable_failure_kind = staticmethod(is_retryable_failure_kind)
    is_terminal_failure_kind = staticmethod(is_terminal_failure_kind)
    pending_consent_payload_from_decision = staticmethod(
        _pending_consent_payload_from_decision_impl
    )
    ensure_latest_assistant_pending_consent = staticmethod(
        _ensure_latest_assistant_pending_consent_impl
    )
    update_intent_statuses = staticmethod(update_intent_statuses)
    next_unfinished_intents = staticmethod(next_unfinished_intents)
    decide = staticmethod(decide)
    build_recovery_message = staticmethod(build_recovery_message)
    build_missing_args_clarification_message = staticmethod(
        build_missing_args_clarification_message
    )
    build_partial_output = staticmethod(build_partial_output)
    has_completed_output_evidence = staticmethod(has_completed_output_evidence)
    build_completed_output = staticmethod(build_completed_output)
    build_partial_response_prompt = staticmethod(build_partial_response_prompt)

    _pending_consent_payload_from_tool_calls = staticmethod(
        _pending_consent_payload_from_tool_calls_impl
    )
    _extract_pending_consent_payload = staticmethod(
        _extract_pending_consent_payload_impl
    )


__all__ = ["RecoveryDecision", "RecoveryManager"]
