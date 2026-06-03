"""Gateway-facing protocol-safe entrypoints for OpenAI-compatible adapters."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from app.ai.exceptions import ProviderError
from app.ai.types import ChatChunk, ChatMessage, ChatResponse


class OpenAIAdapterGatewayEntrypointsMixin:
    """Thin facade that exposes protocol-safe chat entrypoints to gateway callers."""

    def resolve_protocol_safe_wire_api(self, *, wire_api: Any = None) -> str:
        capabilities = getattr(self, "protocol_capabilities", None)
        if capabilities is not None:
            return capabilities.resolve_runtime_wire_api(wire_api)
        raise ProviderError(
            message=(
                "OpenAI-compatible adapter is missing protocol_capabilities; "
                "runtime protocol selection cannot proceed"
            ),
            provider_code="openai_compatible",
            error_code="invalid_protocol_contract",
        )

    async def chat_protocol_safe(
        self,
        *,
        messages: list[ChatMessage],
        model: str,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        top_p: float = 1.0,
        tools: list[dict] | None = None,
        tool_choice: str | None = None,
        wire_api: str | None = None,
        **kwargs: Any,
    ) -> ChatResponse:
        return await self.execute_protocol_chat(
            wire_api=self.resolve_protocol_safe_wire_api(wire_api=wire_api),
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
            tools=tools,
            tool_choice=tool_choice,
            **kwargs,
        )

    async def stream_chat_protocol_safe(
        self,
        *,
        messages: list[ChatMessage],
        model: str,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        top_p: float = 1.0,
        tools: list[dict] | None = None,
        tool_choice: str | None = None,
        wire_api: str | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[ChatChunk]:
        async for chunk in self.execute_protocol_stream(
            wire_api=self.resolve_protocol_safe_wire_api(wire_api=wire_api),
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
            tools=tools,
            tool_choice=tool_choice,
            **kwargs,
        ):
            yield chunk


__all__ = ["OpenAIAdapterGatewayEntrypointsMixin"]
