"""Event emission helpers for turn execution."""

from __future__ import annotations

from typing import Any

from .execution_state_machine import ExecutionStateMachine
from .types import ToolUsePolicy


def emit_round_started(
    state: ExecutionStateMachine,
    *,
    round_kind: str,
    policy: ToolUsePolicy | None,
    tools: list[Any] | None = None,
    intent: Any | None = None,
    reason: str | None = None,
) -> None:
    payload: dict[str, Any] = {
        "round_kind": round_kind,
        "tool_names": [tool.name for tool in (tools or [])],
        "allowed_tool_names": list(getattr(policy, "allowed_tool_names", []) or []),
        "tool_use_policy_family": getattr(policy, "family", None),
        "tool_use_policy_mode": getattr(policy, "mode", None),
        "tool_use_policy_reason": (
            reason or str(getattr(policy, "reason", "") or "").strip() or None
        ),
    }
    if intent is not None:
        payload["intent_id"] = getattr(intent, "intent_id", None)
        payload["intent_kind"] = getattr(intent, "kind", None)
        payload["intent_family"] = getattr(intent, "family", None)
    state.emit_event("turn.round_started", payload)


__all__ = ["emit_round_started"]
