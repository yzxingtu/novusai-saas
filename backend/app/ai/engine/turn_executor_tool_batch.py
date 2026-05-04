"""Tool batch helpers for turn execution."""

from __future__ import annotations

import json
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


def _tool_round_delta_since(
    *,
    before_count: int,
    messages: list[ChatMessage],
) -> int:
    return max(0, _assistant_tool_round_count(messages) - before_count)


def _register_tool_round_delta(
    state: ExecutionStateMachine,
    *,
    before_count: int,
    messages: list[ChatMessage],
) -> None:
    delta = _tool_round_delta_since(before_count=before_count, messages=messages)
    for _round_idx in range(delta):
        state.register_tool_round()


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
    if tool_results:
        state.intent_plan = RecoveryManager.update_intent_statuses(
            state.intent_plan,
            messages=messages,
            turn_messages=turn_messages,
            tool_results=tool_results,
        )
        chained_fetch = await _chain_required_fetch_url_after_search_if_needed(
            state=state,
            io=io,
            response=next_response,
            tools=tools,
            all_tools=all_tools or tools,
            messages=messages,
            turn_messages=turn_messages,
            tool_use_policy=tool_use_policy,
            input_variables=input_variables,
            total_tokens=next_total_tokens,
            completion_tokens_used=next_completion_tokens,
            before_count=tool_rounds_before,
        )
        if chained_fetch is not None:
            (
                next_response,
                chained_tool_results,
                next_total_tokens,
                next_completion_tokens,
            ) = chained_fetch
            tool_results.extend(chained_tool_results)
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


def _normalized_url_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    normalized: list[str] = []
    for item in value:
        url = str(item or "").strip()
        if url and url not in normalized:
            normalized.append(url)
    return normalized


def _first_unattempted_fetch_url_candidate(intent: Any) -> tuple[str, int]:
    metadata = dict(getattr(intent, "metadata", {}) or {})
    candidate_urls = _normalized_url_list(metadata.get("fetch_url_candidate_urls"))
    attempted_url_list = _normalized_url_list(metadata.get("fetch_url_attempted_urls"))
    blocked_url_list = _normalized_url_list(metadata.get("fetch_url_blocked_urls"))
    attempted_urls = set(attempted_url_list + blocked_url_list)
    attempt_index = len(attempted_urls) + 1
    for url in candidate_urls:
        if url not in attempted_urls:
            return url, attempt_index
    return "", attempt_index


def _active_required_fetch_url_intent(state: ExecutionStateMachine) -> Any | None:
    for intent in state.intent_plan:
        if getattr(intent, "status", None) in {"completed", "failed", "skipped"}:
            continue
        if str(getattr(intent, "family", "") or "").strip() != "web_research":
            continue
        metadata = dict(getattr(intent, "metadata", {}) or {})
        gate_reason = str(metadata.get("auto_fetch_gate_reason") or "").strip()
        if not bool(metadata.get("requires_fetch_url")) and gate_reason != (
            "candidate_urls_ready"
        ):
            continue
        allowed_names = {
            str(name or "").strip()
            for name in (
                list(getattr(intent, "allowed_tool_names", []) or [])
                + list(getattr(intent, "completion_signals", []) or [])
            )
            if str(name or "").strip()
        }
        if "fetch_url" in allowed_names:
            return intent
    return None


def _can_chain_synthetic_tool_round(
    *,
    state: ExecutionStateMachine,
    before_count: int,
    messages: list[ChatMessage],
) -> bool:
    budget = state.budget
    if budget is None or not int(budget.max_tool_rounds or 0):
        return True
    projected_rounds = (
        int(budget.tool_rounds_used or 0)
        + _tool_round_delta_since(before_count=before_count, messages=messages)
        + 1
    )
    if projected_rounds <= int(budget.max_tool_rounds or 0):
        return True
    state.preparation_diagnostics["synthetic_required_fetch_url_skipped_reason"] = (
        "tool_round_budget_exceeded"
    )
    return False


def build_required_fetch_url_fallback_response(
    *,
    intent: Any | None,
    response: ChatResponse | None,
    tools: list[Any],
    total_tokens: int,
    completion_tokens_used: int,
    reason: str = "required_fetch_url_retry_without_tool_call",
) -> ChatResponse | None:
    if intent is None:
        return None
    if str(getattr(intent, "family", "") or "").strip() != "web_research":
        return None
    if getattr(response, "tool_calls", None):
        return None
    if not any(
        str(getattr(tool, "name", "") or "").strip() == "fetch_url" for tool in tools
    ):
        return None

    metadata = dict(getattr(intent, "metadata", {}) or {})
    gate_reason = str(metadata.get("auto_fetch_gate_reason") or "").strip()
    if (
        not bool(metadata.get("requires_fetch_url"))
        and gate_reason != "candidate_urls_ready"
    ):
        return None

    selected_url, attempt_index = _first_unattempted_fetch_url_candidate(intent)
    if not selected_url:
        return None

    intent_id = str(getattr(intent, "intent_id", "") or "intent").strip() or "intent"
    synthetic_call = [
        {
            "id": f"synthetic_{intent_id}_fetch_url_{attempt_index}",
            "type": "function",
            "function": {
                "name": "fetch_url",
                "arguments": json.dumps(
                    {"url": selected_url, "max_length": 12000},
                    ensure_ascii=False,
                ),
            },
        }
    ]
    response_metadata = dict(getattr(response, "metadata", {}) or {})
    response_metadata.update(
        {
            "synthetic_required_fetch_url_tool_call": True,
            "synthetic_required_fetch_url_intent_id": intent_id,
            "synthetic_required_fetch_url_tool_name": "fetch_url",
            "synthetic_required_fetch_url": selected_url,
            "synthetic_required_fetch_url_attempt_index": attempt_index,
            "synthetic_required_fetch_url_reason": reason,
        }
    )
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
        metadata=response_metadata,
    )


async def _chain_required_fetch_url_after_search_if_needed(
    *,
    state: ExecutionStateMachine,
    io: TurnIOAdapter,
    response: ChatResponse | None,
    tools: list[Any],
    all_tools: list[Any] | None,
    messages: list[ChatMessage],
    turn_messages: list[ChatMessage] | None,
    tool_use_policy: ToolUsePolicy | None,
    input_variables: dict[str, Any] | None,
    total_tokens: int,
    completion_tokens_used: int,
    before_count: int,
) -> tuple[ChatResponse | None, list[ToolResult], int, int] | None:
    if response is not None and getattr(response, "tool_calls", None):
        return None
    if not _can_chain_synthetic_tool_round(
        state=state,
        before_count=before_count,
        messages=messages,
    ):
        return None

    fetch_intent = _active_required_fetch_url_intent(state)
    if fetch_intent is None:
        return None

    tool_pool = list(all_tools or tools)
    fetch_tools = list(io.restrict_tools_to_names(tool_pool, ["fetch_url"]))
    if not fetch_tools:
        return None

    fetch_policy = ToolUsePolicy(
        family=str(getattr(fetch_intent, "family", "") or "web_research"),
        mode="required",
        allowed_tool_names=["fetch_url"],
        retry_on_contract_breach=False,
        reason="required_fetch_url_after_search_success",
    )
    fallback_response = build_required_fetch_url_fallback_response(
        intent=fetch_intent,
        response=response,
        tools=fetch_tools,
        total_tokens=total_tokens,
        completion_tokens_used=completion_tokens_used,
        reason="required_fetch_url_after_search_success",
    )
    if fallback_response is None:
        return None

    state.preparation_diagnostics[
        "synthetic_required_fetch_url_after_search_success"
    ] = True
    record_synthetic_required_fetch_url(state, fallback_response)
    tool_batch = await io.handle_tool_calls(
        response=fallback_response,
        tools=fetch_tools,
        messages=messages,
        tool_use_policy=fetch_policy,
        starting_total_tokens=total_tokens,
        starting_completion_tokens=completion_tokens_used,
    )
    chained_response = tool_batch.response
    chained_results = list(tool_batch.tool_results)
    if not chained_results:
        chained_results = synthesize_tool_results_from_calls(
            getattr(fallback_response, "tool_calls", None),
            skip_unresolved_interactions=True,
        )
    return (
        chained_response,
        chained_results,
        int(tool_batch.total_tokens or 0),
        int(tool_batch.completion_tokens_used or 0),
    )


def record_synthetic_required_fetch_url(
    state: ExecutionStateMachine,
    response: ChatResponse,
) -> None:
    metadata = dict(getattr(response, "metadata", {}) or {})
    if not metadata.get("synthetic_required_fetch_url_tool_call"):
        return
    state.preparation_diagnostics.update(
        {
            "synthetic_required_fetch_url_tool_call": True,
            "synthetic_required_fetch_url_intent_id": metadata.get(
                "synthetic_required_fetch_url_intent_id"
            ),
            "synthetic_required_fetch_url_tool_name": "fetch_url",
            "synthetic_required_fetch_url_attempt_index": metadata.get(
                "synthetic_required_fetch_url_attempt_index"
            ),
            "synthetic_required_fetch_url_reason": metadata.get(
                "synthetic_required_fetch_url_reason"
            ),
        }
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
        result = await execute_tool_batch(
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
        return result

    if tools:
        fallback_response = build_required_fetch_url_fallback_response(
            intent=intent,
            response=response,
            tools=tools,
            total_tokens=total_tokens,
            completion_tokens_used=completion_tokens_used,
        )
        if fallback_response is None:
            fallback_response = build_shortcircuit_fallback_response(
                intent=intent,
                response=response,
                tools=tools,
                total_tokens=total_tokens,
                completion_tokens_used=completion_tokens_used,
            )
        if fallback_response is not None:
            record_synthetic_required_fetch_url(state, fallback_response)
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


async def _execute_synthetic_required_fetch_url_if_needed(
    *,
    state: ExecutionStateMachine,
    io: TurnIOAdapter,
    intent: Any | None,
    response: ChatResponse | None,
    tools: list[Any],
    all_tools: list[Any] | None,
    messages: list[ChatMessage],
    turn_messages: list[ChatMessage],
    tool_use_policy: ToolUsePolicy | None,
    input_variables: dict[str, Any] | None,
    total_tokens: int,
    completion_tokens_used: int,
) -> tuple[ChatResponse | None, list[ToolResult], int, int] | None:
    fallback_response = build_required_fetch_url_fallback_response(
        intent=intent,
        response=response,
        tools=tools,
        total_tokens=total_tokens,
        completion_tokens_used=completion_tokens_used,
    )
    if fallback_response is None:
        return None
    record_synthetic_required_fetch_url(state, fallback_response)
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
            fallback_result = await _execute_synthetic_required_fetch_url_if_needed(
                state=state,
                io=io,
                intent=active_intent,
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
            if fallback_result is not None:
                (
                    response,
                    extra_tool_results,
                    total_tokens,
                    completion_tokens_used,
                ) = fallback_result
                tool_results.extend(extra_tool_results)
                return (
                    response,
                    tool_results,
                    total_tokens,
                    completion_tokens_used,
                    active_policy,
                    list(active_tools or []),
                )
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
    return response, total_tokens, completion_tokens_used, True, active_policy


__all__ = [
    "build_required_fetch_url_fallback_response",
    "build_shortcircuit_fallback_response",
    "execute_tool_batch",
    "maybe_retry_web_research_contract",
    "record_synthetic_required_fetch_url",
    "run_contract_retry_round",
    "run_tool_batch_or_update_intents",
]
