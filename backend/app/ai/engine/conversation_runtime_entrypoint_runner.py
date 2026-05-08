"""Run prepared runtime-v2 conversation entrypoint plans."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from app.ai.types import ChatChunk, ChatResponse

from .conversation_runtime_context_builder import ConversationRuntimeEntrypointPlan


def _build_query_engine_call_kwargs(
    *,
    plan: ConversationRuntimeEntrypointPlan,
    agent: Any,
    selected_skill_names: list[str] | None,
) -> dict[str, Any]:
    runtime_context = plan.runtime_context
    return {
        "messages": plan.request_context.messages,
        "model": runtime_context.model_code,
        "temperature": agent.temperature,
        "max_tokens": agent.max_tokens,
        "top_p": agent.top_p or 1.0,
        "tools": plan.openai_tools,
        "tool_choice": plan.effective_tool_choice,
        "supports_vision": bool(runtime_context.is_vision),
        "supports_audio": bool(runtime_context.is_audio),
        "supports_video": bool(runtime_context.is_video),
        "selected_skill_names": list(selected_skill_names or []),
        "context_sources": plan.runtime_context_sources,
        "extra_kwargs": dict(plan.request_extra_kwargs),
    }


async def run_runtime_query_entrypoint(
    *,
    plan: ConversationRuntimeEntrypointPlan,
    agent: Any,
    selected_skill_names: list[str] | None = None,
) -> ChatResponse:
    return await plan.query_engine.run_chat_turn(
        **_build_query_engine_call_kwargs(
            plan=plan,
            agent=agent,
            selected_skill_names=selected_skill_names,
        )
    )


async def iterate_runtime_stream_entrypoint(
    *,
    plan: ConversationRuntimeEntrypointPlan,
    agent: Any,
    selected_skill_names: list[str] | None = None,
) -> AsyncIterator[ChatChunk]:
    iter_stream_turn = getattr(plan.query_engine, "iter_stream_turn", None)
    if not callable(iter_stream_turn):
        raise RuntimeError("Runtime query engine must implement iter_stream_turn.")

    runtime_chunk_iter = iter_stream_turn(
        **_build_query_engine_call_kwargs(
            plan=plan,
            agent=agent,
            selected_skill_names=selected_skill_names,
        )
    )
    async for chunk in runtime_chunk_iter:
        yield chunk


__all__ = [
    "iterate_runtime_stream_entrypoint",
    "run_runtime_query_entrypoint",
]
