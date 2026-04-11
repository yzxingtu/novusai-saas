"""Run prepared legacy adapter entrypoint plans."""

from __future__ import annotations

from collections.abc import AsyncIterator

from app.ai.adapters.openai_compatible.compat.legacy_context_builder import (
    LegacyEntrypointAdapterProtocol,
    LegacyEntrypointPlan,
)
from app.ai.adapters.openai_compatible.compat.legacy_protocol_execution import (
    execute_legacy_chat,
    execute_legacy_stream,
)
from app.ai.adapters.openai_compatible.response_mapper import attach_protocol_metadata
from app.ai.types import ChatChunk, ChatMessage, ChatResponse


async def run_legacy_chat_plan(
    *,
    adapter: LegacyEntrypointAdapterProtocol,
    plan: LegacyEntrypointPlan,
    messages: list[ChatMessage],
    model: str,
    tools: list[dict] | None,
    tool_choice: str | None,
) -> ChatResponse:
    execution_state = {
        "active_endpoint_path": plan.context.active_endpoint_path,
        "active_wire_api": plan.context.active_wire_api,
    }
    response = await execute_legacy_chat(
        adapter=adapter,
        execution_state=execution_state,
        messages=messages,
        model=model,
        tools=tools,
        tool_choice=tool_choice,
        use_responses_api=plan.context.active_wire_api == "responses",
        runtime_disable_cross_protocol_fallback=(
            plan.context.runtime_disable_cross_protocol_fallback
        ),
        request_params=plan.request_params,
        responses_kwargs=plan.responses_kwargs,
    )
    response.metadata = attach_protocol_metadata(
        response.metadata,
        protocol_path=execution_state["active_wire_api"],
    )
    response.metadata = adapter._augment_request_metadata(
        response.metadata,
        effective_request=plan.context.effective_request,
    )
    return response


async def run_legacy_stream_plan(
    *,
    adapter: LegacyEntrypointAdapterProtocol,
    plan: LegacyEntrypointPlan,
    messages: list[ChatMessage],
    model: str,
    tools: list[dict] | None,
    tool_choice: str | None,
) -> AsyncIterator[ChatChunk]:
    execution_state = {
        "active_endpoint_path": plan.context.active_endpoint_path,
        "active_wire_api": plan.context.active_wire_api,
    }
    async for chunk in execute_legacy_stream(
        adapter=adapter,
        execution_state=execution_state,
        messages=messages,
        model=model,
        tools=tools,
        tool_choice=tool_choice,
        use_responses_api=plan.context.active_wire_api == "responses",
        runtime_disable_cross_protocol_fallback=(
            plan.context.runtime_disable_cross_protocol_fallback
        ),
        runtime_disable_sync_rescue=plan.context.runtime_disable_sync_rescue,
        request_params=plan.request_params,
        sync_request_params=plan.sync_request_params or {},
        responses_kwargs=plan.responses_kwargs,
    ):
        chunk.metadata = adapter._augment_request_metadata(
            getattr(chunk, "metadata", None),
            effective_request=plan.context.effective_request,
        )
        yield chunk


__all__ = [
    "run_legacy_chat_plan",
    "run_legacy_stream_plan",
]
