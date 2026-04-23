"""
Runtime orchestration for BaseEngine._handle_tool_calls().
"""

from __future__ import annotations

import dataclasses
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from app.ai.tools.types import ToolDefinition, ToolResult
from app.ai.types import ChatMessage, ChatResponse
from app.core.logging import LogManager

from .budget_guard import BudgetGuard
from .tool_followup_runner import run_tool_followup
from .tool_loop_session import (
    ToolLoopSession,
    append_ordered_progress_hint,
    apply_round_recovery_and_focus,
    build_round_policy,
    build_tool_loop_session,
    prepare_round_tools_for_followup,
    sync_sandbox_runtime_model_info,
)
from .tool_round_execution_helpers import (
    ToolRoundExecutionOutcome,
    ToolRoundExecutionState,
    execute_tool_round,
)
from .types import (
    ExecutionBudget,
    ExecutionRequest,
    ResearchContinuationContext,
    ToolUsePolicy,
)

logger = LogManager.get_logger("ai.engine")


@dataclass(slots=True)
class ToolCallLoopRuntime:
    sandbox: Any
    agent: Any
    messages: list[ChatMessage]
    response: ChatResponse
    tools: list[ToolDefinition]
    all_tools: list[ToolDefinition] | None
    request: ExecutionRequest
    skip_final_call: bool
    tool_consent_modes: dict[str, str]
    continuation_context: ResearchContinuationContext | None
    tool_use_policy: ToolUsePolicy | None
    execution_budget: ExecutionBudget | None
    starting_total_tokens: int | None
    starting_completion_tokens: int | None


@dataclass(slots=True)
class ToolCallLoopCallbacks:
    ordered_requested_families_from_intents: Callable[..., list[str]]
    truncate_tool_calls_after_navigation: Callable[
        [list[dict[str, Any]]],
        tuple[list[dict[str, Any]], bool],
    ]
    mark_multi_family_progress: Callable[..., None]
    budget_exit_response: Callable[[int], ChatResponse]
    build_page_no_progress_recovery: Callable[
        ...,
        tuple[list[str], dict[str, Any]],
    ]
    messages_have_blocking_pending_interaction: Callable[
        [list[ChatMessage]],
        bool,
    ]
    first_incomplete_requested_family: Callable[[list[str], set[str]], str | None]
    allowed_tool_names_for_family: Callable[
        [str, list[ToolDefinition], dict[str, Any] | None],
        list[str],
    ]
    build_ordered_capability_hint: Callable[
        [list[str] | None, list[ToolDefinition], dict[str, Any] | None],
        str | None,
    ]
    needs_fetch_url_before_summary: Callable[[list[ChatMessage]], bool]
    apply_fetch_url_only_gate: Callable[
        [list[ChatMessage], list[ToolDefinition], list[ToolDefinition]],
        list[ToolDefinition],
    ]
    restrict_tools_to_names: Callable[
        [list[ToolDefinition], list[str] | None],
        list[ToolDefinition],
    ]
    call_followup_llm: Callable[
        [list[ToolDefinition], ToolUsePolicy],
        Awaitable[ChatResponse],
    ]


def _round_limit(execution_budget: ExecutionBudget | None) -> int:
    if execution_budget is None or execution_budget.max_tool_rounds <= 0:
        return 1
    return int(execution_budget.max_tool_rounds)


def _budget_exit_tuple(
    *,
    session: ToolLoopSession,
    budget_exit_response: Callable[[int], ChatResponse],
) -> tuple[ChatResponse | None, list[ToolResult], int, int]:
    return (
        budget_exit_response(session.total_tokens),
        session.all_tool_results,
        session.total_tokens,
        session.completion_tokens_used,
    )


def _truncate_round_tool_calls(
    *,
    session: ToolLoopSession,
    tool_calls: list[dict[str, Any]],
    truncate_tool_calls_after_navigation: Callable[
        [list[dict[str, Any]]],
        tuple[list[dict[str, Any]], bool],
    ],
) -> list[dict[str, Any]]:
    truncated_tool_calls, truncated_after_navigation = (
        truncate_tool_calls_after_navigation(tool_calls)
    )
    if truncated_after_navigation:
        session.current_response.tool_calls = truncated_tool_calls
        logger.info(
            "Truncated assistant tool call batch after navigation op to avoid stale page follow-up calls: {}",
            [
                str(
                    (tool_call.get("function") or {}).get("name")
                    or tool_call.get("name")
                    or ""
                )
                for tool_call in truncated_tool_calls
            ],
        )
    return truncated_tool_calls


def _append_assistant_tool_call_message(
    *,
    processor: Any,
    session: ToolLoopSession,
    messages: list[ChatMessage],
    tool_calls: list[dict[str, Any]],
) -> None:
    messages.append(
        processor.build_assistant_tool_call_message(
            content=session.current_response.message.content or "",
            tool_calls=tool_calls,
            reasoning_content=(session.current_response.message.content or "").strip()
            or None,
            metadata=(
                dict(session.current_response.metadata or {})
                if isinstance(session.current_response.metadata, dict)
                else None
            ),
        )
    )


def _build_round_state(
    *,
    session: ToolLoopSession,
    messages: list[ChatMessage],
) -> ToolRoundExecutionState:
    return ToolRoundExecutionState(
        messages=messages,
        all_tool_results=session.all_tool_results,
        round_tool_results=[],
        follow_up_messages=[],
        total_tokens=session.total_tokens,
        completion_tokens_used=session.completion_tokens_used,
        tracked_tool_result_bytes=session.tracked_tool_result_bytes,
    )


async def _execute_round(
    *,
    runtime: ToolCallLoopRuntime,
    callbacks: ToolCallLoopCallbacks,
    processor: Any,
    session: ToolLoopSession,
    tool_calls: list[dict[str, Any]],
) -> ToolRoundExecutionOutcome:
    round_state = _build_round_state(session=session, messages=runtime.messages)
    round_outcome = await execute_tool_round(
        processor=processor,
        tool_calls=tool_calls,
        request=runtime.request,
        current_response=session.current_response,
        state=round_state,
        execution_budget=runtime.execution_budget,
        mark_multi_family_progress=callbacks.mark_multi_family_progress,
        build_budget_exit_response=callbacks.budget_exit_response,
        ordered_requested_families=session.ordered_requested_families,
        completed_families=session.completed_families,
        has_fetch_url_in_toolset=session.has_fetch_url_in_toolset,
        input_variables=runtime.request.input_variables,
    )
    session.tracked_tool_result_bytes = round_outcome.tracked_tool_result_bytes
    if round_outcome.early_return is not None:
        return round_outcome

    if round_state.follow_up_messages:
        runtime.messages.extend(round_state.follow_up_messages)
    apply_round_recovery_and_focus(
        session=session,
        messages=runtime.messages,
        tool_calls=tool_calls,
        round_tool_results=round_state.round_tool_results,
        all_tools=session.all_tools_full,
        input_variables=runtime.request.input_variables,
        build_page_no_progress_recovery=callbacks.build_page_no_progress_recovery,
        messages_have_blocking_pending_interaction=callbacks.messages_have_blocking_pending_interaction,
        first_incomplete_requested_family=callbacks.first_incomplete_requested_family,
        allowed_tool_names_for_family=callbacks.allowed_tool_names_for_family,
        conversation_id=runtime.request.conversation_id,
    )
    return round_outcome


async def _run_round_followup(
    *,
    runtime: ToolCallLoopRuntime,
    callbacks: ToolCallLoopCallbacks,
    session: ToolLoopSession,
    processor: Any,
    round_index: int,
    round_limit: int,
) -> tuple[ChatResponse | None, list[ToolResult], int, int] | None:
    followup_decision = await run_tool_followup(
        skip_final_call=runtime.skip_final_call,
        round_index=round_index,
        round_limit=round_limit,
        execution_budget=runtime.execution_budget,
        all_tool_results=session.all_tool_results,
        current_response=session.current_response,
        total_tokens=session.total_tokens,
        completion_tokens_used=session.completion_tokens_used,
        budget_exit_response=callbacks.budget_exit_response,
        append_ordered_progress_hint=lambda: append_ordered_progress_hint(
            session=session,
            messages=runtime.messages,
            all_tools=session.all_tools_full,
            input_variables=runtime.request.input_variables,
            build_ordered_capability_hint=callbacks.build_ordered_capability_hint,
        ),
        round_tools_for_followup=lambda: prepare_round_tools_for_followup(
            session=session,
            messages=runtime.messages,
            processor=processor,
            all_tools=session.all_tools_full,
            needs_fetch_url_before_summary=callbacks.needs_fetch_url_before_summary,
            apply_fetch_url_only_gate=callbacks.apply_fetch_url_only_gate,
            restrict_tools_to_names=callbacks.restrict_tools_to_names,
        ),
        round_policy=lambda round_tools: build_round_policy(
            session=session,
            round_tools=round_tools,
        ),
        call_followup_llm=callbacks.call_followup_llm,
    )
    session.total_tokens = followup_decision.total_tokens
    session.completion_tokens_used = followup_decision.completion_tokens_used
    if followup_decision.early_return is not None:
        return followup_decision.early_return
    if followup_decision.current_response is not None:
        session.current_response = followup_decision.current_response
    if followup_decision.should_continue:
        return None
    return (
        session.current_response,
        session.all_tool_results,
        session.total_tokens,
        session.completion_tokens_used,
    )


async def run_tool_call_loop(
    *,
    runtime: ToolCallLoopRuntime,
    callbacks: ToolCallLoopCallbacks,
) -> tuple[ChatResponse | None, list[ToolResult], int, int]:
    from .tool_processor import ToolCallProcessor

    processor = ToolCallProcessor(
        sandbox=runtime.sandbox,
        tools=runtime.tools,
        all_tools=runtime.all_tools,
        consent_modes=runtime.tool_consent_modes,
        approved_pending_consent_tools=ToolCallProcessor.approved_pending_consent_tool_names(
            runtime.request.interaction_updates,
        ),
        interaction_mode=runtime.request.interaction_mode,
    )
    session = build_tool_loop_session(
        response=runtime.response,
        tools=runtime.tools,
        all_tools=runtime.all_tools,
        request=dataclasses.replace(runtime.request, messages=runtime.messages),
        continuation_context=runtime.continuation_context,
        tool_use_policy=runtime.tool_use_policy,
        execution_budget=runtime.execution_budget,
        starting_total_tokens=runtime.starting_total_tokens,
        starting_completion_tokens=runtime.starting_completion_tokens,
        ordered_requested_families_from_intents=callbacks.ordered_requested_families_from_intents,
    )
    sync_sandbox_runtime_model_info(
        sandbox=runtime.sandbox,
        response=runtime.response,
    )

    round_limit = _round_limit(runtime.execution_budget)
    for round_index in range(round_limit):
        sync_sandbox_runtime_model_info(
            sandbox=runtime.sandbox,
            response=session.current_response,
        )
        tool_calls = session.current_response.tool_calls
        if not tool_calls:
            break
        if BudgetGuard.pre_model_reason(runtime.execution_budget):
            return _budget_exit_tuple(
                session=session,
                budget_exit_response=callbacks.budget_exit_response,
            )
        session.tracked_tool_rounds += 1
        if BudgetGuard.tool_round_reason(
            runtime.execution_budget,
            next_rounds_used=session.tracked_tool_rounds,
        ):
            return _budget_exit_tuple(
                session=session,
                budget_exit_response=callbacks.budget_exit_response,
            )
        tool_calls = _truncate_round_tool_calls(
            session=session,
            tool_calls=tool_calls,
            truncate_tool_calls_after_navigation=callbacks.truncate_tool_calls_after_navigation,
        )
        _append_assistant_tool_call_message(
            processor=processor,
            session=session,
            messages=runtime.messages,
            tool_calls=tool_calls,
        )
        round_outcome = await _execute_round(
            runtime=runtime,
            callbacks=callbacks,
            processor=processor,
            session=session,
            tool_calls=tool_calls,
        )
        if round_outcome.early_return is not None:
            return round_outcome.early_return

        followup_result = await _run_round_followup(
            runtime=runtime,
            callbacks=callbacks,
            session=session,
            processor=processor,
            round_index=round_index,
            round_limit=round_limit,
        )
        if followup_result is None:
            continue
        return followup_result
    else:
        return _budget_exit_tuple(
            session=session,
            budget_exit_response=callbacks.budget_exit_response,
        )

    return (
        session.current_response,
        session.all_tool_results,
        session.total_tokens,
        session.completion_tokens_used,
    )


__all__ = [
    "ToolCallLoopCallbacks",
    "ToolCallLoopRuntime",
    "run_tool_call_loop",
]
