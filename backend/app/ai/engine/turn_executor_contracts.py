"""Contract-breach handling helpers for turn execution."""

from __future__ import annotations

from typing import Any

from .execution_state_machine import ExecutionStateMachine
from .types import ToolUsePolicy


def record_contract_breach(
    state: ExecutionStateMachine,
    *,
    breach_type: str,
    diagnostics: dict[str, Any],
) -> None:
    state.preparation_diagnostics["contract_breach_type"] = breach_type
    if diagnostics.get("unfinished_intents"):
        state.preparation_diagnostics["unfinished_intents"] = list(
            diagnostics.get("unfinished_intents") or []
        )
    if diagnostics.get("leaked_tool_names"):
        state.preparation_diagnostics["leaked_tool_names"] = list(
            diagnostics.get("leaked_tool_names") or []
        )
    if diagnostics.get("tool_leak_detected") is not None:
        state.preparation_diagnostics["tool_leak_detected"] = bool(
            diagnostics.get("tool_leak_detected")
        )
    if diagnostics.get("assistant_claimed_tool_call_without_tool_event") is not None:
        state.preparation_diagnostics[
            "assistant_claimed_tool_call_without_tool_event"
        ] = bool(diagnostics.get("assistant_claimed_tool_call_without_tool_event"))


def constrain_retry_policy_to_active_intent(
    *,
    retry_policy: ToolUsePolicy,
    breach_type: str | None,
    active_intent: Any | None,
    current_policy: ToolUsePolicy | None,
) -> ToolUsePolicy:
    if str(getattr(retry_policy, "mode", "") or "").strip() == "none":
        return retry_policy
    if active_intent is None:
        return retry_policy
    normalized_breach = str(breach_type or "").strip()
    normalized_reason = str(retry_policy.reason or "").strip()
    if (
        (
            normalized_breach == "unfinished_multi_intent_reply"
            or normalized_reason.startswith("unfinished")
        )
        and retry_policy.allowed_tool_names
    ):
        return ToolUsePolicy(
            family=(
                str(retry_policy.family or "").strip()
                or str(getattr(active_intent, "family", "") or "").strip()
                or str(getattr(current_policy, "family", "") or "").strip()
                or retry_policy.family
            ),
            mode="required",
            allowed_tool_names=list(retry_policy.allowed_tool_names),
            retry_on_contract_breach=False,
            reason=retry_policy.reason,
        )
    allowed_tool_names = list(
        getattr(active_intent, "allowed_tool_names", None)
        or getattr(current_policy, "allowed_tool_names", None)
        or retry_policy.allowed_tool_names
    )
    family = (
        str(getattr(active_intent, "family", "") or "").strip()
        or str(getattr(current_policy, "family", "") or "").strip()
        or retry_policy.family
    )
    return ToolUsePolicy(
        family=family or retry_policy.family,
        mode="required",
        allowed_tool_names=allowed_tool_names,
        retry_on_contract_breach=False,
        reason=retry_policy.reason,
    )


def suppress_contract_placeholder_response(
    response: Any | None,
) -> Any | None:
    if response is None:
        return None
    if getattr(response, "tool_calls", None):
        return response
    response.message.content = ""
    return response


__all__ = [
    "constrain_retry_policy_to_active_intent",
    "record_contract_breach",
    "suppress_contract_placeholder_response",
]
