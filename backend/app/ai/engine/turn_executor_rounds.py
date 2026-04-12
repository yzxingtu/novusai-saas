"""Execution rounds for clarification and post-tool follow-ups."""

from __future__ import annotations

from typing import Any, Callable, TYPE_CHECKING

from app.ai.types import ChatMessage, ChatResponse

from .execution_state_machine import ExecutionStateMachine
from .recovery_manager import RecoveryManager
from .types import RecoveryDecision, ToolUsePolicy

if TYPE_CHECKING:
    from .turn_executor import TurnIOAdapter


def intent_missing_args(intent: Any | None) -> list[str]:
    metadata = (
        dict(getattr(intent, "metadata", {}) or {}) if intent is not None else {}
    )
    raw_missing_args = metadata.get("missing_args")
    if not isinstance(raw_missing_args, list):
        return []
    return [str(item).strip() for item in raw_missing_args if str(item).strip()]


def intent_requires_clarification(intent: Any | None) -> bool:
    return bool(
        intent is not None
        and getattr(intent, "allow_text_response", False)
        and intent_missing_args(intent)
    )


async def run_missing_args_clarification(
    *,
    state: ExecutionStateMachine,
    io: TurnIOAdapter,
    intent: Any,
    messages: list[ChatMessage],
    total_tokens: int,
    completion_tokens_used: int,
    emit_round_started: Callable[..., None],
) -> tuple[ChatResponse | None, int, int]:
    missing_args = intent_missing_args(intent)
    decision = RecoveryDecision(
        action="retry_intent",
        target_intent_id=getattr(intent, "intent_id", None),
        retry_family=getattr(intent, "family", None),
        completed_intent_ids=[
            item.intent_id for item in state.intent_plan if item.status == "completed"
        ],
        unfinished_intent_ids=[
            item.intent_id
            for item in state.intent_plan
            if item.status not in {"completed", "skipped"}
        ],
        reason="missing_args_clarification",
        metadata={"missing_args": missing_args},
    )
    state.register_retry(decision)
    messages.append(
        RecoveryManager.build_missing_args_clarification_message(
            decision=decision,
            intents=state.intent_plan,
            missing_args=missing_args,
        )
    )
    clarification_policy = ToolUsePolicy(
        family="none",
        mode="none",
        allowed_tool_names=[],
        retry_on_contract_breach=False,
        reason="missing_args_clarification",
    )
    emit_round_started(
        state,
        round_kind="intent_retry",
        policy=clarification_policy,
        tools=[],
        intent=intent,
        reason="missing_args_clarification",
    )
    clarification_round = await io.call_llm(
        messages=messages,
        tools=None,
        tool_use_policy=clarification_policy,
        breach_retry_result="intent_retry",
    )
    response = clarification_round.response
    total_tokens += int(clarification_round.total_tokens or 0)
    completion_tokens_used += int(clarification_round.completion_tokens_used or 0)
    state.register_completion_tokens(completion_tokens_used)
    intent.status = "completed"
    intent.metadata = dict(getattr(intent, "metadata", {}) or {})
    intent.metadata["clarification_requested"] = True
    return response, total_tokens, completion_tokens_used


async def run_post_tool_follow_up_round(
    *,
    state: ExecutionStateMachine,
    io: TurnIOAdapter,
    messages: list[ChatMessage],
    total_tokens: int,
    completion_tokens_used: int,
    emit_round_started: Callable[..., None],
) -> tuple[ChatResponse | None, int, int]:
    follow_up_policy = ToolUsePolicy(
        family="none",
        mode="none",
        allowed_tool_names=[],
        retry_on_contract_breach=False,
        reason="post_tool_follow_up",
    )
    emit_round_started(
        state,
        round_kind="normal_follow_up_round",
        policy=follow_up_policy,
        tools=[],
        reason="post_tool_follow_up",
    )
    follow_up_round = await io.call_llm(
        messages=messages,
        tools=None,
        tool_use_policy=follow_up_policy,
        breach_retry_result="normal_follow_up_round",
    )
    response = follow_up_round.response
    total_tokens += int(follow_up_round.total_tokens or 0)
    completion_tokens_used += int(follow_up_round.completion_tokens_used or 0)
    state.register_completion_tokens(completion_tokens_used)
    return response, total_tokens, completion_tokens_used


__all__ = [
    "intent_missing_args",
    "intent_requires_clarification",
    "run_missing_args_clarification",
    "run_post_tool_follow_up_round",
]
