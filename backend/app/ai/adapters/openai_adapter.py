"""
OpenAI Compatible Adapter / OpenAI 兼容适配器

Supports OpenAI official API and all compatible services
(e.g. DeepSeek, Zhipu, Tongyi Qianwen and other domestic LLMs).
支持 OpenAI 官方 API 及所有兼容服务（如 DeepSeek、智谱、通义千问等国产大模型）。
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from openai import AsyncOpenAI

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
    OpenAIAdapterNativeWebSearchMixin,
    OpenAIAdapterNonChatRuntimeMixin,
    OpenAIAdapterProtocolEntrypointsMixin,
    OpenAIAdapterUpstreamRuntimeMixin,
    OpenAIAdapterUsageRuntimeMixin,
)
from app.ai.adapters.openai_compatible.support.protocol_bridge import (
    OpenAIAdapterProtocolBridgeMixin,
)
from app.ai.types import ChatChunk, ChatMessage, ChatResponse


class OpenAIAdapter(
    OpenAIAdapterModelRequestMixin,
    OpenAIAdapterUpstreamRuntimeMixin,
    OpenAIAdapterProtocolEntrypointsMixin,
    OpenAIAdapterProtocolBridgeMixin,
    OpenAIAdapterGatewayEntrypointsMixin,
    OpenAIAdapterUsageRuntimeMixin,
    OpenAIAdapterNativeWebSearchMixin,
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
            configured_wire_api=self.provider_config.get("wire_api"),
        )
        self.wire_api = self.protocol_capabilities.primary_wire_api

        self.client = build_openai_client(api_key=api_key, base_url=self.base_url)
        self._chat_completions_v1_retry_client: AsyncOpenAI | Any | None = None
        self._chat_completions_v1_retry_base_url: str | None = None

    @staticmethod
    def _resolve_public_entrypoint_wire_api(kwargs: dict[str, Any]) -> Any:
        explicit_wire_api = kwargs.pop("wire_api", None)
        if explicit_wire_api is not None:
            return explicit_wire_api
        return kwargs.get("_runtime_force_wire_api")

    @staticmethod
    def _legacy_chat_entrypoint():
        from app.ai.adapters.openai_compatible.legacy_entrypoints import (
            execute_legacy_adapter_chat_entrypoint,
        )

        return execute_legacy_adapter_chat_entrypoint

    @staticmethod
    def _legacy_stream_entrypoint():
        from app.ai.adapters.openai_compatible.legacy_entrypoints import (
            execute_legacy_adapter_stream_entrypoint,
        )

        return execute_legacy_adapter_stream_entrypoint

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
        re-enter the legacy planner/fallback path.
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
        re-enter the legacy planner/fallback path.
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

    async def chat_legacy_compat(
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
        Explicit compatibility entrypoint for legacy planner semantics.
        """
        _ = stream
        return await self._legacy_chat_entrypoint()(
            adapter=self,
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
            tools=tools,
            tool_choice=tool_choice,
            **kwargs,
        )

    async def stream_chat_legacy_compat(
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
        Explicit compatibility entrypoint for legacy streaming semantics.
        """
        async for chunk in self._legacy_stream_entrypoint()(
            adapter=self,
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


__all__ = [
    "OpenAIAdapter",
    "SUPPORTS_NATIVE_AUDIO",
]
