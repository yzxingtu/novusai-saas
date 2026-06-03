from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from app.ai.exceptions import ProviderError
from app.ai.types import ChatChunk, ChatMessage, ChatResponse
from app.models.ai import AIProvider


def resolve_gateway_protocol_wire_api(
    provider: AIProvider,
    *,
    extra_kwargs: dict[str, Any] | None = None,
) -> str | None:
    runtime_kwargs = dict(extra_kwargs or {})
    runtime_force_wire_api = runtime_kwargs.get("_runtime_force_wire_api")
    if runtime_force_wire_api is not None:
        return str(runtime_force_wire_api)
    return None


def resolve_adapter_protocol_wire_api(
    adapter: Any,
    *,
    wire_api: str | None,
) -> str:
    protocol_wire_api_resolver = getattr(
        adapter,
        "resolve_protocol_safe_wire_api",
        None,
    )
    if callable(protocol_wire_api_resolver):
        return protocol_wire_api_resolver(wire_api=wire_api)

    protocol_capabilities = getattr(adapter, "protocol_capabilities", None)
    if protocol_capabilities is not None:
        runtime_wire_api_resolver = getattr(
            protocol_capabilities,
            "resolve_runtime_wire_api",
            None,
        )
        if callable(runtime_wire_api_resolver):
            return runtime_wire_api_resolver(wire_api)

    raise ProviderError(
        message=(
            "OpenAI-compatible adapter is missing protocol_capabilities; "
            "runtime protocol selection cannot proceed"
        ),
        provider_code="openai_compatible",
        error_code="invalid_protocol_contract",
    )


async def call_chat_adapter(
    *,
    adapter: Any,
    provider: AIProvider,
    messages: list[ChatMessage],
    model: str,
    temperature: float,
    max_tokens: int | None,
    top_p: float,
    stream: bool,
    tools: list[dict] | None,
    tool_choice: str | None,
    extra_kwargs: dict[str, Any] | None = None,
) -> ChatResponse:
    adapter_kwargs = dict(extra_kwargs or {})
    protocol_wire_api = resolve_gateway_protocol_wire_api(
        provider,
        extra_kwargs=adapter_kwargs,
    )

    protocol_chat = getattr(adapter, "chat_protocol_safe", None)
    if getattr(provider, "type", None) == "openai_compatible" and callable(
        protocol_chat
    ):
        return await protocol_chat(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
            tools=tools,
            tool_choice=tool_choice,
            wire_api=protocol_wire_api,
            **adapter_kwargs,
        )

    execute_protocol_chat = getattr(adapter, "execute_protocol_chat", None)
    if getattr(provider, "type", None) == "openai_compatible" and callable(
        execute_protocol_chat
    ):
        return await execute_protocol_chat(
            wire_api=resolve_adapter_protocol_wire_api(
                adapter,
                wire_api=protocol_wire_api,
            ),
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
            tools=tools,
            tool_choice=tool_choice,
            **adapter_kwargs,
        )

    return await adapter.chat(
        messages=messages,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        top_p=top_p,
        stream=stream,
        tools=tools,
        tool_choice=tool_choice,
        **adapter_kwargs,
    )


async def stream_chat_adapter(
    *,
    adapter: Any,
    provider: AIProvider,
    messages: list[ChatMessage],
    model: str,
    temperature: float,
    max_tokens: int | None,
    top_p: float,
    tools: list[dict] | None,
    tool_choice: str | None,
    extra_kwargs: dict[str, Any] | None = None,
) -> AsyncIterator[ChatChunk]:
    adapter_kwargs = dict(extra_kwargs or {})
    protocol_wire_api = resolve_gateway_protocol_wire_api(
        provider,
        extra_kwargs=adapter_kwargs,
    )

    protocol_stream = getattr(adapter, "stream_chat_protocol_safe", None)
    if getattr(provider, "type", None) == "openai_compatible" and callable(
        protocol_stream
    ):
        async for chunk in protocol_stream(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
            tools=tools,
            tool_choice=tool_choice,
            wire_api=protocol_wire_api,
            **adapter_kwargs,
        ):
            yield chunk
        return

    execute_protocol_stream = getattr(adapter, "execute_protocol_stream", None)
    if getattr(provider, "type", None) == "openai_compatible" and callable(
        execute_protocol_stream
    ):
        async for chunk in execute_protocol_stream(
            wire_api=resolve_adapter_protocol_wire_api(
                adapter,
                wire_api=protocol_wire_api,
            ),
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
            tools=tools,
            tool_choice=tool_choice,
            **adapter_kwargs,
        ):
            yield chunk
        return

    async for chunk in adapter.stream_chat(
        messages=messages,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        top_p=top_p,
        tools=tools,
        tool_choice=tool_choice,
        **adapter_kwargs,
    ):
        yield chunk
