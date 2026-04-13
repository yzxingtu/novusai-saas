"""Execution rounds for clarification and post-tool follow-ups."""

from __future__ import annotations

from typing import Any, Callable, TYPE_CHECKING

from app.ai.tools.types import ToolResult
from app.ai.types import ChatMessage, ChatResponse

from .execution_state_machine import ExecutionStateMachine
from .recovery_manager import RecoveryManager
from .turn_executor_completion import response_has_visible_content
from .turn_executor_helpers import current_turn_messages
from .turn_executor_tool_batch import (
    build_shortcircuit_fallback_response,
    execute_tool_batch,
)
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


async def run_initial_round(
    *,
    state: ExecutionStateMachine,
    io: TurnIOAdapter,
    intent: Any | None,
    messages: list[ChatMessage],
    tools: list[Any] | None,
    tool_use_policy: ToolUsePolicy | None,
    total_tokens: int,
    completion_tokens_used: int,
    emit_round_started: Callable[..., None],
) -> tuple[ChatResponse | None, int, int]:
    initial_budget_exit = state.budget_exit_reason()
    if initial_budget_exit:
        state.register_provider_failure(
            kind="budget_exit",
            event={"kind": "budget_exit", "reason": initial_budget_exit},
        )
        response = ChatResponse(
            message=ChatMessage(role="assistant", content=""),
            total_tokens=0,
            output_tokens=0,
        )
        return response, total_tokens, completion_tokens_used

    if intent_requires_clarification(intent):
        return await run_missing_args_clarification(
            state=state,
            io=io,
            intent=intent,
            messages=messages,
            total_tokens=total_tokens,
            completion_tokens_used=completion_tokens_used,
            emit_round_started=emit_round_started,
        )

    model_round = await io.call_llm(
        messages=messages,
        tools=tools,
        tool_use_policy=tool_use_policy,
    )
    response = model_round.response
    total_tokens = int(model_round.total_tokens or 0)
    completion_tokens_used = int(model_round.completion_tokens_used or 0)
    state.register_completion_tokens(completion_tokens_used)
    if (
        getattr(model_round, "native_search_observed", False)
        and response_has_visible_content(response)
        and state.intent_plan
    ):
        state.intent_plan = RecoveryManager.complete_native_search_intents(
            state.intent_plan
        )
    return response, total_tokens, completion_tokens_used


async def run_intent_retry_loop(
    *,
    state: ExecutionStateMachine,
    io: TurnIOAdapter,
    prep: Any,
    request: Any,
    agent: Any,
    messages: list[ChatMessage],
    start_index: int,
    tools: list[Any],
    response: ChatResponse | None,
    total_tokens: int,
    completion_tokens_used: int,
    tool_results: list[ToolResult],
    emit_round_started: Callable[..., None],
) -> tuple[ChatResponse | None, list[ToolResult], int, int, RecoveryDecision | None]:
    budget_exit_reason = state.budget_exit_reason()
    if budget_exit_reason:
        state.register_provider_failure(
            kind="budget_exit",
            event={"kind": "budget_exit", "reason": budget_exit_reason},
        )

    decision = RecoveryManager.decide(
        state.intent_plan,
        budget=state.budget,
        provider_failure_kind=state.provider_failure_kind,
    )
    while decision is not None and decision.action == "retry_intent":
        retry_intent = next(
            (
                intent
                for intent in state.intent_plan
                if intent.intent_id == decision.target_intent_id
            ),
            None,
        )
        if intent_requires_clarification(retry_intent):
            response, total_tokens, completion_tokens_used = (
                await run_missing_args_clarification(
                    state=state,
                    io=io,
                    intent=retry_intent,
                    messages=messages,
                    total_tokens=total_tokens,
                    completion_tokens_used=completion_tokens_used,
                    emit_round_started=emit_round_started,
                )
            )
            decision = RecoveryManager.decide(
                state.intent_plan,
                budget=state.budget,
                provider_failure_kind=state.provider_failure_kind,
            )
            continue
        state.register_retry(decision)
        messages.append(
            RecoveryManager.build_recovery_message(
                decision=decision,
                intents=state.intent_plan,
            )
        )
        retry_tools = io.restrict_tools_to_names(
            prep.all_tools or tools,
            decision.allowed_tool_names,
        )
        retry_policy = ToolUsePolicy(
            family=decision.retry_family or prep.tool_use_policy.family,
            mode="required",
            allowed_tool_names=decision.allowed_tool_names
            or [tool.name for tool in retry_tools],
            retry_on_contract_breach=False,
            reason=decision.reason,
        )
        emit_round_started(
            state,
            round_kind="intent_retry",
            policy=retry_policy,
            tools=retry_tools,
            intent=retry_intent,
            reason=decision.reason or "intent_retry",
        )
        if retry_policy.mode == "required" and retry_tools:
            io.log_tool_contract_diagnostics(
                agent=agent,
                messages=messages,
                response=response,
                tools=retry_tools,
                policy=retry_policy,
                conversation_id=request.conversation_id,
                breach_type=decision.reason or "intent_retry",
                retry_result="retrying",
                continuation=prep.continuation_context,
            )
        retry_round = await io.call_llm(
            messages=messages,
            tools=retry_tools or None,
            tool_use_policy=retry_policy,
            breach_retry_result="intent_retry",
        )
        response = retry_round.response
        total_tokens += int(retry_round.total_tokens or 0)
        completion_tokens_used += int(retry_round.completion_tokens_used or 0)
        state.register_completion_tokens(completion_tokens_used)
        if getattr(response, "tool_calls", None) and retry_tools:
            (
                response,
                extra_tool_results,
                total_tokens,
                completion_tokens_used,
            ) = await execute_tool_batch(
                state=state,
                io=io,
                response=response,
                tools=retry_tools,
                messages=messages,
                turn_messages=current_turn_messages(
                    messages,
                    start_index=start_index,
                ),
                tool_use_policy=retry_policy,
                total_tokens=total_tokens,
                completion_tokens_used=completion_tokens_used,
            )
            tool_results.extend(extra_tool_results)
        elif retry_tools:
            fallback_response = build_shortcircuit_fallback_response(
                intent=retry_intent,
                response=response,
                tools=retry_tools,
                total_tokens=total_tokens,
                completion_tokens_used=completion_tokens_used,
            )
            if fallback_response is not None:
                (
                    response,
                    extra_tool_results,
                    total_tokens,
                    completion_tokens_used,
                ) = await execute_tool_batch(
                    state=state,
                    io=io,
                    response=fallback_response,
                    tools=retry_tools,
                    messages=messages,
                    turn_messages=current_turn_messages(
                        messages,
                        start_index=start_index,
                    ),
                    tool_use_policy=retry_policy,
                    total_tokens=total_tokens,
                    completion_tokens_used=completion_tokens_used,
                )
                tool_results.extend(extra_tool_results)
                decision = RecoveryManager.decide(
                    state.intent_plan,
                    budget=state.budget,
                    provider_failure_kind=state.provider_failure_kind,
                )
                continue
        if state.intent_plan and not getattr(response, "tool_calls", None):
            state.intent_plan = RecoveryManager.update_intent_statuses(
                state.intent_plan,
                messages=messages,
                turn_messages=current_turn_messages(
                    messages,
                    start_index=start_index,
                ),
                tool_results=[],
            )
            if retry_policy.mode == "required" and retry_tools and response is not None:
                io.log_tool_contract_diagnostics(
                    agent=agent,
                    messages=messages,
                    response=response,
                    tools=retry_tools,
                    policy=retry_policy,
                    conversation_id=request.conversation_id,
                    breach_type=decision.reason or "intent_retry",
                    retry_result="failed",
                    continuation=prep.continuation_context,
                )
        budget_exit_reason = state.budget_exit_reason()
        if budget_exit_reason:
            state.register_provider_failure(
                kind="budget_exit",
                event={"kind": "budget_exit", "reason": budget_exit_reason},
            )
        decision = RecoveryManager.decide(
            state.intent_plan,
            budget=state.budget,
            provider_failure_kind=state.provider_failure_kind,
        )

    return response, tool_results, total_tokens, completion_tokens_used, decision


__all__ = [
    "intent_missing_args",
    "intent_requires_clarification",
    "run_missing_args_clarification",
    "run_post_tool_follow_up_round",
    "run_initial_round",
    "run_intent_retry_loop",
]
