"""
Factory for ToolCallLoopCallbacks to keep BaseEngine thin.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from app.ai.tools.types import ToolDefinition
from app.ai.types import ChatResponse

from .tool_call_loop_policy import ToolCallLoopPolicy
from .tool_call_loop_runtime import ToolCallLoopCallbacks
from .types import ToolUsePolicy


def build_tool_call_loop_callbacks(
    *,
    policy: ToolCallLoopPolicy,
    ordered_requested_families_from_intents: Callable[..., list[str]],
    keep_tool_calls_for_round: Callable[
        [list[dict[str, Any]]],
        tuple[list[dict[str, Any]], bool],
    ],
    mark_multi_family_progress: Callable[..., None],
    budget_exit_response: Callable[[int], ChatResponse],
    call_followup_llm: Callable[
        [list[ToolDefinition], ToolUsePolicy],
        Awaitable[ChatResponse],
    ],
) -> ToolCallLoopCallbacks:
    return ToolCallLoopCallbacks(
        ordered_requested_families_from_intents=ordered_requested_families_from_intents,
        keep_tool_calls_for_round=keep_tool_calls_for_round,
        mark_multi_family_progress=mark_multi_family_progress,
        budget_exit_response=budget_exit_response,
        messages_have_blocking_pending_interaction=policy.messages_have_blocking_pending_interaction,
        first_incomplete_requested_family=policy.first_incomplete_requested_family,
        allowed_tool_names_for_family=policy.allowed_tool_names_for_family,
        build_ordered_capability_hint=policy.build_ordered_capability_hint,
        restrict_tools_to_names=policy.restrict_tools_to_names,
        call_followup_llm=call_followup_llm,
    )
