"""Run legacy entrypoint dispatch with a focused error boundary."""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

from app.ai.adapters.openai_compatible.compat.legacy_context_builder import (
    LegacyEntrypointAdapterProtocol,
    LegacyEntrypointPlan,
)
from app.ai.adapters.openai_compatible.compat.legacy_entrypoint_errors import (
    LegacyEntrypointErrorContext,
)
from app.ai.adapters.openai_compatible.compat.legacy_protocol_execution import (
    execute_legacy_chat,
    execute_legacy_stream,
)
from app.ai.adapters.openai_compatible.response_mapper import attach_protocol_metadata
from app.ai.exceptions import AIGatewayError
from app.ai.types import ChatChunk, ChatMessage, ChatResponse
from app.core.logging import LogManager

logger = LogManager.get_logger("ai")

ChatDispatch = Callable[
    ...,
    Awaitable[tuple[LegacyEntrypointPlan, ChatResponse]],
]
StreamDispatch = Callable[
    ...,
    Awaitable[tuple[LegacyEntrypointPlan, AsyncIterator[ChatChunk]]],
]
ErrorContextBuilder = Callable[..., LegacyEntrypointErrorContext]
PlannedContextBuilder = Callable[[LegacyEntrypointPlan], LegacyEntrypointErrorContext]
RaiseError = Callable[..., None]
DispatchErrorType = type[Exception]


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
        guard_snapshot=plan.context.guard_snapshot,
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
        guard_snapshot=plan.context.guard_snapshot,
        request_params=plan.request_params,
        sync_request_params=plan.sync_request_params or {},
        responses_kwargs=plan.responses_kwargs,
    ):
        chunk.metadata = adapter._augment_request_metadata(
            getattr(chunk, "metadata", None),
            effective_request=plan.context.effective_request,
        )
        yield chunk


async def execute_legacy_adapter_chat_entrypoint(
    *,
    adapter: LegacyEntrypointAdapterProtocol,
    messages: list[ChatMessage],
    model: str,
    temperature: float = 0.7,
    max_tokens: int | None = None,
    top_p: float = 1.0,
    tools: list[dict] | None = None,
    tool_choice: str | None = None,
    kwargs: dict[str, Any],
    dispatch_chat: ChatDispatch,
    dispatch_error_type: DispatchErrorType,
    default_error_context: ErrorContextBuilder,
    planned_error_context: PlannedContextBuilder,
    raise_error: RaiseError,
) -> ChatResponse:
    error_context = default_error_context(
        adapter=adapter,
        model=model,
    )
    try:
        _, response = await dispatch_chat(
            adapter=adapter,
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
            tools=tools,
            tool_choice=tool_choice,
            kwargs=kwargs,
        )
        return response
    except AIGatewayError:
        raise
    except dispatch_error_type as exc:
        logger.error("Chat error: model={} error={}", model, str(exc.cause))
        raise_error(
            adapter=adapter,
            error=exc.cause,
            context=planned_error_context(exc.plan),
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("Chat error: model={} error={}", model, str(exc))
        raise_error(
            adapter=adapter,
            error=exc,
            context=error_context,
        )


async def execute_legacy_adapter_stream_entrypoint(
    *,
    adapter: LegacyEntrypointAdapterProtocol,
    messages: list[ChatMessage],
    model: str,
    temperature: float = 0.7,
    max_tokens: int | None = None,
    top_p: float = 1.0,
    tools: list[dict] | None = None,
    tool_choice: str | None = None,
    kwargs: dict[str, Any],
    dispatch_stream: StreamDispatch,
    dispatch_error_type: DispatchErrorType,
    default_error_context: ErrorContextBuilder,
    planned_error_context: PlannedContextBuilder,
    raise_error: RaiseError,
) -> AsyncIterator[ChatChunk]:
    error_context = default_error_context(
        adapter=adapter,
        model=model,
    )
    try:
        plan, stream_iter = await dispatch_stream(
            adapter=adapter,
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
            tools=tools,
            tool_choice=tool_choice,
            kwargs=kwargs,
        )
        error_context = planned_error_context(plan)
        async for chunk in stream_iter:
            yield chunk
    except AIGatewayError:
        raise
    except dispatch_error_type as exc:
        logger.error("Stream chat error: model={} error={}", model, str(exc.cause))
        raise_error(
            adapter=adapter,
            error=exc.cause,
            context=planned_error_context(exc.plan),
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("Stream chat error: model={} error={}", model, str(exc))
        raise_error(
            adapter=adapter,
            error=exc,
            context=error_context,
        )


__all__ = [
    "execute_legacy_adapter_chat_entrypoint",
    "execute_legacy_adapter_stream_entrypoint",
    "run_legacy_chat_plan",
    "run_legacy_stream_plan",
]
