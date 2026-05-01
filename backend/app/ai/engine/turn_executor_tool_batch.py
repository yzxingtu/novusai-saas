"""Tool batch helpers for turn execution."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from app.ai.tools.types import ToolResult
from app.ai.types import ChatMessage, ChatResponse

from .execution_state_machine import ExecutionStateMachine
from .recovery_manager import RecoveryManager
from .tool_execution_helpers import (
    register_tool_failures,
    synthesize_tool_results_from_calls,
)
from .turn_executor_contracts import (
    constrain_retry_policy_to_active_intent,
    record_contract_breach,
    suppress_contract_placeholder_response,
)
from .types import ToolUsePolicy

if TYPE_CHECKING:
    from .turn_executor import TurnIOAdapter


def _assistant_tool_round_count(messages: list[ChatMessage]) -> int:
    return sum(
        1
        for message in messages
        if message.role == "assistant" and bool(message.tool_calls)
    )


def _register_tool_round_delta(
    state: ExecutionStateMachine,
    *,
    before_count: int,
    messages: list[ChatMessage],
) -> None:
    delta = max(0, _assistant_tool_round_count(messages) - before_count)
    for _round_idx in range(delta):
        state.register_tool_round()


def _response_has_visible_content(response: ChatResponse | None) -> bool:
    if response is None:
        return False
    return bool(str(response.message.content or "").strip())


def _complete_native_search_if_observed(
    *,
    state: ExecutionStateMachine,
    response: ChatResponse | None,
    model_round: Any,
) -> None:
    if (
        getattr(model_round, "native_search_observed", False)
        and _response_has_visible_content(response)
        and state.intent_plan
    ):
        state.intent_plan = RecoveryManager.complete_native_search_intents(
            state.intent_plan
        )


async def execute_tool_batch(
    *,
    state: ExecutionStateMachine,
    io: TurnIOAdapter,
    response: ChatResponse,
    tools: list[Any],
    all_tools: list[Any] | None = None,
    messages: list[ChatMessage],
    turn_messages: list[ChatMessage] | None,
    tool_use_policy: ToolUsePolicy | None,
    input_variables: dict[str, Any] | None = None,
    total_tokens: int,
    completion_tokens_used: int,
) -> tuple[ChatResponse | None, list[ToolResult], int, int]:
    tool_rounds_before = _assistant_tool_round_count(messages)
    tool_call_response = response
    tool_batch = await io.handle_tool_calls(
        response=response,
        tools=tools,
        messages=messages,
        tool_use_policy=tool_use_policy,
        starting_total_tokens=total_tokens,
        starting_completion_tokens=completion_tokens_used,
    )
    next_response = tool_batch.response
    tool_results = list(tool_batch.tool_results)
    next_total_tokens = int(tool_batch.total_tokens or 0)
    next_completion_tokens = int(tool_batch.completion_tokens_used or 0)
    if not tool_results:
        tool_results = synthesize_tool_results_from_calls(
            getattr(tool_call_response, "tool_calls", None),
            skip_unresolved_interactions=True,
        )
    _register_tool_round_delta(
        state,
        before_count=tool_rounds_before,
        messages=messages,
    )
    state.register_tool_results(
        messages=messages,
        turn_messages=turn_messages,
        tool_results=tool_results,
    )
    state.register_completion_tokens(next_completion_tokens)
    register_tool_failures(state, tool_results)
    return next_response, tool_results, next_total_tokens, next_completion_tokens


def build_shortcircuit_fallback_response(
    *,
    intent: Any | None,
    response: ChatResponse | None,
    tools: list[Any],
    total_tokens: int,
    completion_tokens_used: int,
) -> ChatResponse | None:
    if intent is None or not bool(getattr(intent, "shortcircuit", False)):
        return None
    if str(getattr(intent, "kind", "") or "").strip() != "time_query":
        return None

    time_tool = next(
        (
            tool
            for tool in tools
            if str(getattr(tool, "name", "")).strip() == "get_current_time"
        ),
        None,
    )
    if time_tool is None:
        return None

    synthetic_call = [
        {
            "id": (
                f"synthetic_{getattr(intent, 'intent_id', 'intent')}_get_current_time"
            ),
            "type": "function",
            "function": {
                "name": "get_current_time",
                "arguments": "{}",
            },
        }
    ]
    metadata = dict(getattr(response, "metadata", {}) or {})
    metadata["synthetic_shortcircuit_tool_call"] = True
    metadata["synthetic_shortcircuit_intent_id"] = getattr(intent, "intent_id", None)
    metadata["synthetic_shortcircuit_tool_name"] = "get_current_time"
    return ChatResponse(
        message=ChatMessage(
            role="assistant",
            content="",
            tool_calls=synthetic_call,
        ),
        total_tokens=int(total_tokens or getattr(response, "total_tokens", 0) or 0),
        output_tokens=int(
            completion_tokens_used or getattr(response, "output_tokens", 0) or 0
        ),
        finish_reason="tool_calls",
        tool_calls=synthetic_call,
        metadata=metadata,
    )


async def run_tool_batch_or_update_intents(
    *,
    state: ExecutionStateMachine,
    io: TurnIOAdapter,
    intent: Any | None,
    response: ChatResponse | None,
    tools: list[Any],
    all_tools: list[Any] | None = None,
    messages: list[ChatMessage],
    turn_messages: list[ChatMessage],
    tool_use_policy: ToolUsePolicy | None,
    input_variables: dict[str, Any] | None,
    total_tokens: int,
    completion_tokens_used: int,
) -> tuple[ChatResponse | None, list[ToolResult], int, int]:
    if getattr(response, "tool_calls", None) and tools:
        return await execute_tool_batch(
            state=state,
            io=io,
            response=response,
            tools=tools,
            all_tools=all_tools or tools,
            messages=messages,
            turn_messages=turn_messages,
            tool_use_policy=tool_use_policy,
            input_variables=input_variables,
            total_tokens=total_tokens,
            completion_tokens_used=completion_tokens_used,
        )

    if tools:
        fallback_response = build_shortcircuit_fallback_response(
            intent=intent,
            response=response,
            tools=tools,
            total_tokens=total_tokens,
            completion_tokens_used=completion_tokens_used,
        )
        if fallback_response is not None:
            return await execute_tool_batch(
                state=state,
                io=io,
                response=fallback_response,
                tools=tools,
                all_tools=all_tools or tools,
                messages=messages,
                turn_messages=turn_messages,
                tool_use_policy=tool_use_policy,
                input_variables=input_variables,
                total_tokens=total_tokens,
                completion_tokens_used=completion_tokens_used,
            )

    if state.intent_plan:
        state.intent_plan = RecoveryManager.update_intent_statuses(
            state.intent_plan,
            messages=messages,
            turn_messages=turn_messages,
            tool_results=[],
        )

    return response, [], total_tokens, completion_tokens_used


async def run_contract_retry_round(
    *,
    state: ExecutionStateMachine,
    io: TurnIOAdapter,
    agent: Any,
    request: Any,
    prep: Any,
    messages: list[ChatMessage],
    turn_messages: list[ChatMessage],
    response: ChatResponse | None,
    active_policy: ToolUsePolicy | None,
    active_intent: Any | None,
    active_tools: list[Any],
    tools: list[Any],
    tool_results: list[ToolResult],
    total_tokens: int,
    completion_tokens_used: int,
    emit_round_started: Callable[..., None],
) -> tuple[
    ChatResponse | None,
    list[ToolResult],
    int,
    int,
    ToolUsePolicy | None,
    list[Any],
]:
    contract_tools = list(active_tools or prep.all_tools or tools)
    if (
        active_policy is None
        or not active_policy.retry_on_contract_breach
        or not contract_tools
        or tool_results
    ):
        return (
            response,
            tool_results,
            total_tokens,
            completion_tokens_used,
            active_policy,
            list(active_tools or []),
        )

    should_retry = False
    retry_policy: ToolUsePolicy | None = None
    breach_type: str | None = None
    non_intent_breach_type: str | None = None

    if state.intent_plan:
        breach_type, retry_policy, breach_diagnostics = (
            io.analyze_post_tool_contract_breach(
                messages=messages,
                response=response,
                current_policy=active_policy,
                tools=contract_tools,
                input_variables=request.input_variables,
            )
        )
        if breach_type:
            record_contract_breach(
                state,
                breach_type=breach_type,
                diagnostics=breach_diagnostics,
            )
            response = suppress_contract_placeholder_response(response)
        if retry_policy is not None:
            retry_policy = constrain_retry_policy_to_active_intent(
                retry_policy=retry_policy,
                breach_type=breach_type,
                active_intent=active_intent,
                current_policy=active_policy,
            )
            should_retry = True
    else:
        should_retry, retry_policy, _breach_response_text = (
            io.should_retry_tool_contract_breach(
                response=response,
                current_policy=active_policy,
                tools=contract_tools,
                input_variables=request.input_variables,
            )
        )
        if not should_retry:
            should_retry, retry_policy, _breach_response_text = (
                io.should_retry_web_research_contract_breach(
                    messages=messages,
                    response=response,
                    current_policy=active_policy,
                    tools=contract_tools,
                    input_variables=request.input_variables,
                    continuation=prep.continuation_context,
                )
            )
        if should_retry and retry_policy is not None:
            non_intent_breach_type = retry_policy.reason or "tool_contract_breach"

    if should_retry and retry_policy is not None:
        if non_intent_breach_type:
            record_contract_breach(
                state,
                breach_type=non_intent_breach_type,
                diagnostics={},
            )
        retry_tool_pool = list(prep.all_tools or tools or contract_tools)
        retry_tools = io.restrict_tools_to_names(
            retry_tool_pool,
            retry_policy.allowed_tool_names,
        )
        emit_round_started(
            state,
            round_kind="contract_retry",
            policy=retry_policy,
            tools=retry_tools,
            reason=retry_policy.reason or "contract_retry",
        )
        io.log_tool_contract_diagnostics(
            agent=agent,
            messages=messages,
            response=response,
            tools=retry_tool_pool,
            policy=retry_policy,
            conversation_id=request.conversation_id,
            breach_type=retry_policy.reason or "contract_breach",
            retry_result="retrying",
            continuation=prep.continuation_context,
        )
        active_policy = retry_policy
        active_tools = list(retry_tools or [])
        retry_round = await io.call_llm(
            messages=messages,
            tools=retry_tools or None,
            tool_use_policy=retry_policy,
            breach_retry_result="contract_retry",
        )
        response = retry_round.response
        total_tokens += int(retry_round.total_tokens or 0)
        completion_tokens_used += int(retry_round.completion_tokens_used or 0)
        state.register_completion_tokens(completion_tokens_used)
        _complete_native_search_if_observed(
            state=state,
            response=response,
            model_round=retry_round,
        )
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
                all_tools=retry_tool_pool,
                messages=messages,
                turn_messages=turn_messages,
                tool_use_policy=retry_policy,
                input_variables=request.input_variables,
                total_tokens=total_tokens,
                completion_tokens_used=completion_tokens_used,
            )
            tool_results.extend(extra_tool_results)
            if state.intent_plan and retry_policy.allowed_tool_names:
                for intent in state.intent_plan:
                    if (
                        intent.status not in {"completed", "failed", "skipped"}
                        and not intent.allowed_tool_names
                        and (
                            retry_policy.family == "none"
                            or intent.family == retry_policy.family
                        )
                    ):
                        intent.allowed_tool_names = list(
                            retry_policy.allowed_tool_names
                        )
        elif response is not None:
            response = suppress_contract_placeholder_response(response)
            io.log_tool_contract_diagnostics(
                agent=agent,
                messages=messages,
                response=response,
                tools=retry_tools,
                policy=retry_policy,
                conversation_id=request.conversation_id,
                breach_type=retry_policy.reason or "contract_breach",
                retry_result="failed",
                continuation=prep.continuation_context,
            )
        elif state.intent_plan:
            state.intent_plan = RecoveryManager.update_intent_statuses(
                state.intent_plan,
                messages=messages,
                turn_messages=turn_messages,
                tool_results=[],
            )

    return (
        response,
        tool_results,
        total_tokens,
        completion_tokens_used,
        active_policy,
        list(active_tools or []),
    )


async def maybe_retry_web_research_contract(
    *,
    state: ExecutionStateMachine,
    io: TurnIOAdapter,
    agent: Any,
    request: Any,
    prep: Any,
    messages: list[ChatMessage],
    response: ChatResponse | None,
    active_policy: ToolUsePolicy | None,
    active_tools: list[Any],
    tools: list[Any],
    total_tokens: int,
    completion_tokens_used: int,
    emit_round_started: Callable[..., None],
) -> tuple[ChatResponse | None, int, int, bool, ToolUsePolicy | None]:
    if response is None or getattr(response, "tool_calls", None):
        return response, total_tokens, completion_tokens_used, False, active_policy

    contract_tools = list(active_tools or prep.all_tools or tools)
    should_retry_web_research, web_research_retry_policy, _ = (
        io.should_retry_web_research_contract_breach(
            messages=messages,
            response=response,
            current_policy=active_policy,
            tools=contract_tools,
            input_variables=request.input_variables,
            continuation=prep.continuation_context,
        )
    )
    if (
        not should_retry_web_research
        or web_research_retry_policy is None
        or web_research_retry_policy.mode != "none"
        or web_research_retry_policy.allowed_tool_names
    ):
        return response, total_tokens, completion_tokens_used, False, active_policy

    record_contract_breach(
        state,
        breach_type=(
            web_research_retry_policy.reason or "web_research_contract_breach"
        ),
        diagnostics={},
    )
    emit_round_started(
        state,
        round_kind="contract_retry",
        policy=web_research_retry_policy,
        tools=[],
        reason=(web_research_retry_policy.reason or "web_research_contract_breach"),
    )
    io.log_tool_contract_diagnostics(
        agent=agent,
        messages=messages,
        response=response,
        tools=contract_tools,
        policy=web_research_retry_policy,
        conversation_id=request.conversation_id,
        breach_type=(
            web_research_retry_policy.reason or "web_research_contract_breach"
        ),
        retry_result="retrying",
        continuation=prep.continuation_context,
    )
    active_policy = web_research_retry_policy
    retry_round = await io.call_llm(
        messages=messages,
        tools=None,
        tool_use_policy=web_research_retry_policy,
        breach_retry_result="contract_retry",
    )
    response = retry_round.response
    total_tokens += int(retry_round.total_tokens or 0)
    completion_tokens_used += int(retry_round.completion_tokens_used or 0)
    state.register_completion_tokens(completion_tokens_used)
    _complete_native_search_if_observed(
        state=state,
        response=response,
        model_round=retry_round,
    )
    return response, total_tokens, completion_tokens_used, True, active_policy


__all__ = [
    "build_shortcircuit_fallback_response",
    "execute_tool_batch",
    "maybe_retry_web_research_contract",
    "run_contract_retry_round",
    "run_tool_batch_or_update_intents",
]
