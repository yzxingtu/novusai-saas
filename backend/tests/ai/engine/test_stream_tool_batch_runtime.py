"""
Test type: behavioral
Scope: stream tool batch runtime consent, result projection, and budget handling.
Mock strategy: sandbox/runtime collaborators are fakes; stream batch orchestration runs real.
"""

from __future__ import annotations

from types import SimpleNamespace

from app.ai.engine.stream_tool_batch_runtime import (
    StreamToolBatchCallbacks,
    StreamToolBatchRuntimeInput,
)
from app.ai.tools.types import ToolDefinition
from app.ai.types import ChatMessage, ChatResponse


def _build_text_round_response(
    *,
    content: str,
    reasoning_content: str,
    total_tokens: int,
) -> ChatResponse:
    return ChatResponse(
        message=ChatMessage(
            role="assistant",
            content=content,
            reasoning_content=reasoning_content or None,
        ),
        total_tokens=total_tokens,
        finish_reason="stop",
    )


def _build_runtime(
    *,
    sandbox,
    tools: list[ToolDefinition],
    response: ChatResponse,
    messages: list[ChatMessage] | None = None,
    interaction_mode: str = "confirm",
    interaction_updates: list[dict] | None = None,
    tool_consent_modes: dict[str, str] | None = None,
    starting_total_tokens: int = 12,
    starting_completion_tokens: int = 12,
) -> StreamToolBatchRuntimeInput:
    return StreamToolBatchRuntimeInput(
        sandbox=sandbox,
        request=SimpleNamespace(
            conversation_id=9001,
            interaction_mode=interaction_mode,
            interaction_updates=interaction_updates,
        ),
        response=response,
        tools=tools,
        all_tools=tools,
        tool_consent_modes=tool_consent_modes or {},
        messages=list(messages or [ChatMessage(role="user", content="测试")]),
        tool_calls=list(response.tool_calls or response.message.tool_calls or []),
        starting_total_tokens=starting_total_tokens,
        starting_completion_tokens=starting_completion_tokens,
        reasoning_content=(
            str(
                response.message.reasoning_content or response.message.content or ""
            ).strip()
            or None
        ),
    )


def _build_callbacks(
    *,
    events: list[dict],
    emitted_chunks: list[str] | None = None,
    budget_exit_reason=None,
    registered_budget_exit: list[str | None] | None = None,
) -> StreamToolBatchCallbacks:
    async def emit_event(payload: dict) -> None:
        events.append(payload)

    async def emit_chunk(text: str) -> None:
        if emitted_chunks is not None:
            emitted_chunks.append(text)

    def register_budget_exit(reason: str | None) -> None:
        if registered_budget_exit is not None:
            registered_budget_exit.append(reason)

    return StreamToolBatchCallbacks(
        emit_event=emit_event,
        emit_chunk=emit_chunk,
        budget_exit_reason=budget_exit_reason or (lambda: None),
        register_budget_exit=register_budget_exit,
        build_text_round_response=_build_text_round_response,
    )
