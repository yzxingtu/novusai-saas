"""Focused helpers for streamed model-round aggregation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from app.ai.types import ChatMessage, ChatResponse

from .budget_guard import BudgetGuard
from .turn_executor import ModelRoundResult

if TYPE_CHECKING:
    from .stream_handler import StreamIOAdapter


@dataclass(slots=True)
class StreamRoundState:
    output: str = ""
    reasoning: str = ""
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    total_tokens: int = 0
    completion_tokens_used: int = 0
    finish_reason: str = "stop"
    native_search_observed: bool = False


async def handle_stream_chunk(
    adapter: StreamIOAdapter,
    state: StreamRoundState,
    *,
    chunk: Any,
) -> None:
    adapter._sync_runtime_metadata(getattr(chunk, "metadata", None))

    chunk_meta = getattr(chunk, "metadata", None)
    if isinstance(chunk_meta, dict) and chunk_meta.get("web_search_in_progress"):
        state.native_search_observed = True
        await adapter.handler._emit_runtime_event(
            {"event": "status", "status": "web_search_in_progress"}
        )

    reasoning_delta = getattr(chunk, "reasoning_delta", None)
    if reasoning_delta:
        state.reasoning += reasoning_delta
        adapter.handler._reasoning_output = state.reasoning
        await adapter.handler._emit_runtime_event(
            {
                "event": "thinking",
                "delta": reasoning_delta,
            }
        )

    delta = getattr(chunk, "delta", None)
    if delta:
        state.output += delta
        adapter.handler._visible_stream_content += delta
        adapter.handler._output = adapter.handler._visible_stream_content
        await adapter.handler._emit_runtime_event(
            {
                "event": "message",
                "delta": delta,
            }
        )

    incoming_tool_calls = getattr(chunk, "tool_calls", None)
    if incoming_tool_calls:
        state.tool_calls = adapter.handler._merge_stream_tool_calls(
            state.tool_calls,
            incoming_tool_calls,
        )

    if getattr(chunk, "total_tokens", None) is not None:
        state.total_tokens = int(chunk.total_tokens or 0)
    if getattr(chunk, "output_tokens", None) is not None:
        state.completion_tokens_used = int(chunk.output_tokens or 0)

    state.finish_reason = getattr(chunk, "finish_reason", None) or state.finish_reason


def finalize_model_round(
    adapter: StreamIOAdapter,
    state: StreamRoundState,
) -> ModelRoundResult:
    finalized_tool_calls = adapter.handler._finalize_stream_tool_calls(state.tool_calls)
    if state.completion_tokens_used <= 0:
        state.completion_tokens_used = int(state.total_tokens or 0)

    completion_reason = BudgetGuard.completion_reason(
        adapter.handler._state.budget,
        completion_tokens=state.completion_tokens_used,
        total_tokens=state.total_tokens,
    )
    if completion_reason and state.output.strip() and finalized_tool_calls:
        finalized_tool_calls = []
        state.finish_reason = "stop"

    adapter.handler._clear_before_next_message = bool(
        finalized_tool_calls and state.output.strip()
    )
    adapter.handler._total_tokens = int(state.total_tokens or 0)
    adapter.handler._completion_tokens_used = int(state.completion_tokens_used or 0)

    response = ChatResponse(
        message=ChatMessage(
            role="assistant",
            content=state.output,
            reasoning_content=state.reasoning or None,
            tool_calls=finalized_tool_calls or None,
        ),
        total_tokens=state.total_tokens,
        output_tokens=state.completion_tokens_used,
        finish_reason=(
            "tool_calls" if finalized_tool_calls else (state.finish_reason or "stop")
        ),
        tool_calls=finalized_tool_calls or None,
    )
    return ModelRoundResult(
        response=response,
        total_tokens=state.total_tokens,
        completion_tokens_used=state.completion_tokens_used,
        native_search_observed=state.native_search_observed,
    )


__all__ = [
    "StreamRoundState",
    "finalize_model_round",
    "handle_stream_chunk",
]
