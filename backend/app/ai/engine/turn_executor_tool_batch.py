"""Tool batch helpers for turn execution."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from app.ai.tools.types import ToolResult
from app.ai.types import ChatMessage, ChatResponse

from .execution_state_machine import ExecutionStateMachine
from .tool_execution_helpers import (
    register_tool_failures,
    synthesize_tool_results_from_calls,
)
from .turn_executor_helpers import assistant_tool_round_count, register_tool_round_delta
from .types import ToolUsePolicy

if TYPE_CHECKING:
    from .turn_executor import TurnIOAdapter


async def execute_tool_batch(
    *,
    state: ExecutionStateMachine,
    io: TurnIOAdapter,
    response: ChatResponse,
    tools: list[Any],
    messages: list[ChatMessage],
    turn_messages: list[ChatMessage] | None,
    tool_use_policy: ToolUsePolicy | None,
    total_tokens: int,
    completion_tokens_used: int,
) -> tuple[ChatResponse | None, list[ToolResult], int, int]:
    tool_rounds_before = assistant_tool_round_count(messages)
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
    register_tool_round_delta(
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
                f"synthetic_{getattr(intent, 'intent_id', 'intent')}"
                "_get_current_time"
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


__all__ = [
    "build_shortcircuit_fallback_response",
    "execute_tool_batch",
]
