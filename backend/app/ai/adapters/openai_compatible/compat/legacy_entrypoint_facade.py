"""Thin facade over the legacy entrypoint runner."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from app.ai.adapters.openai_compatible.compat.legacy_context_builder import (
    LegacyEntrypointAdapterProtocol,
)
from app.ai.adapters.openai_compatible.compat.legacy_entrypoint_dispatch import (
    LegacyEntrypointDispatchError,
    dispatch_legacy_chat_entrypoint,
    dispatch_legacy_stream_entrypoint,
)
from app.ai.adapters.openai_compatible.compat.legacy_entrypoint_errors import (
    LegacyEntrypointErrorContext,
    default_legacy_entrypoint_error_context,
    planned_legacy_entrypoint_error_context,
    raise_legacy_entrypoint_error,
)
from app.ai.adapters.openai_compatible.compat.legacy_entrypoint_runner import (
    execute_legacy_adapter_chat_entrypoint as _execute_legacy_adapter_chat_entrypoint,
)
from app.ai.adapters.openai_compatible.compat.legacy_entrypoint_runner import (
    execute_legacy_adapter_stream_entrypoint as _execute_legacy_adapter_stream_entrypoint,
)
from app.ai.types import ChatChunk, ChatMessage, ChatResponse


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
    return await _execute_legacy_adapter_chat_entrypoint(
        adapter=adapter,
        messages=messages,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        top_p=top_p,
        tools=tools,
        tool_choice=tool_choice,
        kwargs=kwargs,
        dispatch_chat=dispatch_legacy_chat_entrypoint,
        dispatch_error_type=LegacyEntrypointDispatchError,
        default_error_context=default_legacy_entrypoint_error_context,
        planned_error_context=planned_legacy_entrypoint_error_context,
        raise_error=raise_legacy_entrypoint_error,
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
    async for chunk in _execute_legacy_adapter_stream_entrypoint(
        adapter=adapter,
        messages=messages,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        top_p=top_p,
        tools=tools,
        tool_choice=tool_choice,
        kwargs=kwargs,
        dispatch_stream=dispatch_legacy_stream_entrypoint,
        dispatch_error_type=LegacyEntrypointDispatchError,
        default_error_context=default_legacy_entrypoint_error_context,
        planned_error_context=planned_legacy_entrypoint_error_context,
        raise_error=raise_legacy_entrypoint_error,
    ):
        yield chunk


__all__ = [
    "LegacyEntrypointErrorContext",
    "default_legacy_entrypoint_error_context",
    "execute_legacy_adapter_chat_entrypoint",
    "execute_legacy_adapter_stream_entrypoint",
    "planned_legacy_entrypoint_error_context",
    "raise_legacy_entrypoint_error",
]
