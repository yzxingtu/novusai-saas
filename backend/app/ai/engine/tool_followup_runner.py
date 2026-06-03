"""
Helpers for BaseEngine._handle_tool_calls() follow-up continuation/finalization.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from app.ai.tools.types import ToolDefinition, ToolResult
from app.ai.types import ChatResponse

from .budget_guard import BudgetGuard
from .types import ExecutionBudget, ToolUsePolicy


@dataclass
class ToolFollowupDecision:
    current_response: ChatResponse | None
    total_tokens: int
    completion_tokens_used: int
    early_return: tuple[ChatResponse | None, list[ToolResult], int, int] | None = None
    should_continue: bool = False
    should_break: bool = False


async def run_tool_followup(
    *,
    skip_final_call: bool,
    round_index: int,
    round_limit: int,
    execution_budget: ExecutionBudget | None,
    all_tool_results: list[ToolResult],
    current_response: ChatResponse,
    total_tokens: int,
    completion_tokens_used: int,
    budget_exit_response: Callable[[int], ChatResponse],
    append_ordered_progress_hint: Callable[[], None],
    round_tools_for_followup: Callable[[], list[ToolDefinition]],
    round_policy: Callable[[list[ToolDefinition]], ToolUsePolicy],
    call_followup_llm: Callable[
        [list[ToolDefinition], ToolUsePolicy],
        Awaitable[ChatResponse],
    ],
) -> ToolFollowupDecision:
    if skip_final_call:
        if round_index < round_limit - 1:
            if BudgetGuard.pre_model_reason(execution_budget):
                return ToolFollowupDecision(
                    current_response=None,
                    total_tokens=total_tokens,
                    completion_tokens_used=completion_tokens_used,
                    early_return=(
                        None,
                        all_tool_results,
                        total_tokens,
                        completion_tokens_used,
                    ),
                )
            append_ordered_progress_hint()
            round_tools = round_tools_for_followup()
            followup_policy = round_policy(round_tools)
            peek_response = await call_followup_llm(round_tools, followup_policy)
            total_tokens += peek_response.total_tokens or 0
            completion_tokens_used += int(
                peek_response.output_tokens
                if peek_response.output_tokens is not None
                else (peek_response.total_tokens or 0)
            )
            if BudgetGuard.completion_reason(
                execution_budget,
                completion_tokens=completion_tokens_used,
                total_tokens=total_tokens,
            ):
                return ToolFollowupDecision(
                    current_response=None,
                    total_tokens=total_tokens,
                    completion_tokens_used=completion_tokens_used,
                    early_return=(
                        None,
                        all_tool_results,
                        total_tokens,
                        completion_tokens_used,
                    ),
                )
            if peek_response.tool_calls:
                return ToolFollowupDecision(
                    current_response=peek_response,
                    total_tokens=total_tokens,
                    completion_tokens_used=completion_tokens_used,
                    should_continue=True,
                )
        return ToolFollowupDecision(
            current_response=None,
            total_tokens=total_tokens,
            completion_tokens_used=completion_tokens_used,
            early_return=(
                None,
                all_tool_results,
                total_tokens,
                completion_tokens_used,
            ),
        )

    if BudgetGuard.pre_model_reason(execution_budget):
        return ToolFollowupDecision(
            current_response=current_response,
            total_tokens=total_tokens,
            completion_tokens_used=completion_tokens_used,
            early_return=(
                budget_exit_response(total_tokens),
                all_tool_results,
                total_tokens,
                completion_tokens_used,
            ),
        )

    append_ordered_progress_hint()
    round_tools = round_tools_for_followup()
    followup_policy = round_policy(round_tools)
    next_response = await call_followup_llm(round_tools, followup_policy)
    total_tokens += next_response.total_tokens or 0
    completion_tokens_used += int(
        next_response.output_tokens
        if next_response.output_tokens is not None
        else (next_response.total_tokens or 0)
    )
    completion_reason = BudgetGuard.completion_reason(
        execution_budget,
        completion_tokens=completion_tokens_used,
        total_tokens=total_tokens,
    )
    if completion_reason:
        grace_active = bool(
            execution_budget is not None
            and bool(getattr(execution_budget, "finalization_grace_applied", False))
        )
        if (
            completion_reason == "elapsed_budget_exceeded"
            and grace_active
            and not next_response.tool_calls
            and str(next_response.message.content or "").strip()
        ):
            return ToolFollowupDecision(
                current_response=next_response,
                total_tokens=total_tokens,
                completion_tokens_used=completion_tokens_used,
                should_break=True,
            )
        return ToolFollowupDecision(
            current_response=next_response,
            total_tokens=total_tokens,
            completion_tokens_used=completion_tokens_used,
            early_return=(
                budget_exit_response(total_tokens),
                all_tool_results,
                total_tokens,
                completion_tokens_used,
            ),
        )
    if not next_response.tool_calls:
        return ToolFollowupDecision(
            current_response=next_response,
            total_tokens=total_tokens,
            completion_tokens_used=completion_tokens_used,
            should_break=True,
        )
    return ToolFollowupDecision(
        current_response=next_response,
        total_tokens=total_tokens,
        completion_tokens_used=completion_tokens_used,
        should_continue=True,
    )


__all__ = ["ToolFollowupDecision", "run_tool_followup"]
