"""
OpenAI Compatible Adapter / OpenAI 兼容适配器

Supports OpenAI official API and all compatible services
(e.g. DeepSeek, Zhipu, Tongyi Qianwen and other domestic LLMs).
支持 OpenAI 官方 API 及所有兼容服务（如 DeepSeek、智谱、通义千问等国产大模型）。
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from app.ai.adapters.base import BaseAdapter
from app.ai.adapters.openai_compatible import (
    OpenAIProtocolCapabilities,
    build_openai_client,
)
from app.ai.adapters.openai_compatible.support import (
    SUPPORTS_NATIVE_AUDIO,
    OpenAIAdapterGatewayEntrypointsMixin,
    OpenAIAdapterModelRequestMixin,
    OpenAIAdapterMultimodalMixin,
    OpenAIAdapterNonChatRuntimeMixin,
    OpenAIAdapterProtocolEntrypointsMixin,
    OpenAIAdapterUpstreamRuntimeMixin,
    OpenAIAdapterUsageRuntimeMixin,
)
from app.ai.adapters.openai_compatible.support.protocol_bridge import (
    OpenAIAdapterProtocolBridgeMixin,
)
from app.ai.exceptions import ProviderError
from app.ai.types import ChatChunk, ChatMessage, ChatResponse


class OpenAIAdapter(
    OpenAIAdapterModelRequestMixin,
    OpenAIAdapterUpstreamRuntimeMixin,
    OpenAIAdapterProtocolEntrypointsMixin,
    OpenAIAdapterProtocolBridgeMixin,
    OpenAIAdapterGatewayEntrypointsMixin,
    OpenAIAdapterUsageRuntimeMixin,
    OpenAIAdapterMultimodalMixin,
    OpenAIAdapterNonChatRuntimeMixin,
    BaseAdapter,
):
    """
    OpenAI Compatible Adapter / OpenAI 兼容适配器

    Supports OpenAI official API and all compatible services.
    支持 OpenAI 官方 API 及所有兼容服务。
    """

    def __init__(self, api_key: str, base_url: str | None = None, **kwargs):
        super().__init__(api_key, base_url, **kwargs)

        provider_config = self.config.get("provider_config")
        self.provider_config = (
            provider_config.copy() if isinstance(provider_config, dict) else {}
        )
        self.base_url = self._clean_base_url(base_url)
        self.protocol_capabilities = OpenAIProtocolCapabilities.from_provider_config(
            provider_config=self.provider_config,
            configured_wire_api=None,
        )
        self.wire_api = self.protocol_capabilities.primary_wire_api

        self.client = build_openai_client(api_key=api_key, base_url=self.base_url)

    @staticmethod
    def _resolve_public_entrypoint_wire_api(kwargs: dict[str, Any]) -> Any:
        explicit_wire_api = kwargs.pop("wire_api", None)
        if explicit_wire_api is not None and str(explicit_wire_api).strip():
            raise ProviderError(
                message=(
                    "Public wire_api override is retired; use runtime protocol "
                    "planning instead"
                ),
                provider_code="openai_compatible",
                error_code="invalid_protocol_contract",
            )
        return kwargs.get("_runtime_force_wire_api")

    async def chat(
        self,
        messages: list[ChatMessage],
        model: str,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        top_p: float = 1.0,
        stream: bool = False,
        tools: list[dict] | None = None,
        tool_choice: str | None = None,
        **kwargs,
    ) -> ChatResponse:
        """
        Chat conversation (synchronous mode) / 聊天对话（同步模式）

        The public facade is protocol-safe by default and must not implicitly
        bypass runtime protocol planning.
        """
        _ = stream
        return await self.chat_protocol_safe(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
            tools=tools,
            tool_choice=tool_choice,
            wire_api=self._resolve_public_entrypoint_wire_api(kwargs),
            **kwargs,
        )

    async def stream_chat(
        self,
        messages: list[ChatMessage],
        model: str,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        top_p: float = 1.0,
        tools: list[dict] | None = None,
        tool_choice: str | None = None,
        **kwargs,
    ) -> AsyncIterator[ChatChunk]:
        """
        Chat conversation (streaming mode) / 聊天对话（流式模式）

        The public facade is protocol-safe by default and must not implicitly
        bypass runtime protocol planning.
        """
        async for chunk in self.stream_chat_protocol_safe(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
            tools=tools,
            tool_choice=tool_choice,
            wire_api=self._resolve_public_entrypoint_wire_api(kwargs),
            **kwargs,
        ):
            yield chunk


__all__ = [
    "OpenAIAdapter",
    "SUPPORTS_NATIVE_AUDIO",
]
