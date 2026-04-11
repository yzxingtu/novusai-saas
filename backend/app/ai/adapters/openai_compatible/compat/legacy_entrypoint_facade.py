"""Compose legacy entrypoint dispatch with a focused error boundary."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

from app.ai.adapters.openai_compatible.compat.legacy_context_builder import (
    LegacyEntrypointAdapterProtocol,
    LegacyEntrypointPlan,
)
from app.ai.adapters.openai_compatible.compat.legacy_entrypoint_dispatch import (
    LegacyEntrypointDispatchError,
    dispatch_legacy_chat_entrypoint,
    dispatch_legacy_stream_entrypoint,
)
from app.ai.adapters.openai_compatible.request_builder import resolve_chat_endpoint_path
from app.ai.exceptions import AIGatewayError, convert_openai_error
from app.ai.types import ChatChunk, ChatMessage, ChatResponse
from app.core.logging import LogManager

logger = LogManager.get_logger("ai")


@dataclass(frozen=True)
class LegacyEntrypointErrorContext:
    endpoint_path: str
    wire_api: str
    effective_error_model: str


def default_legacy_entrypoint_error_context(
    *,
    adapter: LegacyEntrypointAdapterProtocol,
    model: str,
) -> LegacyEntrypointErrorContext:
    return LegacyEntrypointErrorContext(
        endpoint_path=resolve_chat_endpoint_path(wire_api=adapter.wire_api),
        wire_api=adapter.wire_api,
        effective_error_model=model,
    )


def planned_legacy_entrypoint_error_context(
    plan: LegacyEntrypointPlan,
) -> LegacyEntrypointErrorContext:
    return LegacyEntrypointErrorContext(
        endpoint_path=plan.context.active_endpoint_path,
        wire_api=plan.context.active_wire_api,
        effective_error_model=plan.context.effective_error_model,
    )


def raise_legacy_entrypoint_error(
    *,
    adapter: LegacyEntrypointAdapterProtocol,
    error: Exception,
    context: LegacyEntrypointErrorContext,
) -> None:
    adapter._log_upstream_error(
        error,
        endpoint_path=context.endpoint_path,
        model=context.effective_error_model,
        wire_api=context.wire_api,
    )
    raise convert_openai_error(
        error,
        provider_code="openai",
        model_code=context.effective_error_model,
    ) from error


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
    **kwargs: Any,
) -> ChatResponse:
    error_context = default_legacy_entrypoint_error_context(
        adapter=adapter,
        model=model,
    )
    try:
        _, response = await dispatch_legacy_chat_entrypoint(
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
    except LegacyEntrypointDispatchError as exc:
        logger.error("Chat error: model={} error={}", model, str(exc.cause))
        raise_legacy_entrypoint_error(
            adapter=adapter,
            error=exc.cause,
            context=planned_legacy_entrypoint_error_context(exc.plan),
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("Chat error: model={} error={}", model, str(exc))
        raise_legacy_entrypoint_error(
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
    **kwargs: Any,
) -> AsyncIterator[ChatChunk]:
    error_context = default_legacy_entrypoint_error_context(
        adapter=adapter,
        model=model,
    )
    try:
        plan, stream_iter = await dispatch_legacy_stream_entrypoint(
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
        error_context = planned_legacy_entrypoint_error_context(plan)
        async for chunk in stream_iter:
            yield chunk
    except AIGatewayError:
        raise
    except LegacyEntrypointDispatchError as exc:
        logger.error("Stream chat error: model={} error={}", model, str(exc.cause))
        raise_legacy_entrypoint_error(
            adapter=adapter,
            error=exc.cause,
            context=planned_legacy_entrypoint_error_context(exc.plan),
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("Stream chat error: model={} error={}", model, str(exc))
        raise_legacy_entrypoint_error(
            adapter=adapter,
            error=exc,
            context=error_context,
        )


__all__ = [
    "LegacyEntrypointErrorContext",
    "default_legacy_entrypoint_error_context",
    "execute_legacy_adapter_chat_entrypoint",
    "execute_legacy_adapter_stream_entrypoint",
    "planned_legacy_entrypoint_error_context",
    "raise_legacy_entrypoint_error",
]
