"""
Facade mixins for the AI gateway.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from app.ai.gateway_support.call_log_bridge import GatewayCallLogBridge
from app.ai.gateway_support.protocol_adapter_bridge import (
    call_chat_adapter as call_chat_adapter_impl,
)
from app.ai.gateway_support.protocol_adapter_bridge import (
    stream_chat_adapter as stream_chat_adapter_impl,
)
from app.ai.types import ChatChunk, ChatMessage, ChatResponse
from app.core.i18n import _
from app.exceptions import BusinessException, NotFoundException
from app.models.ai import AIModel, AIProvider, ProviderApiKey


class GatewayFacadeMixin:
    async def _execute_with_retry(self, **kwargs: Any) -> Any:
        orchestrator = getattr(self, "retry_orchestrator", None)
        if orchestrator is not None:
            return await orchestrator.execute_with_retry(**kwargs)
        return await self.retry_service.execute_with_retry(**kwargs)

    @staticmethod
    def _build_request_log_data(
        *,
        messages: list[ChatMessage],
        temperature: float,
        max_tokens: int | None,
        top_p: float,
        tools: list[dict] | None,
        tool_choice: str | None,
        all_tool_names: list[str] | None = None,
        retry_count: int = 0,
        tool_use_policy_family: str | None = None,
        tool_use_policy_mode: str | None = None,
        allowed_tool_names: list[str] | None = None,
        breach_retry_result: str | None = None,
        stream: bool = False,
    ) -> dict[str, object]:
        return GatewayCallLogBridge.build_request_log_data(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
            tools=tools,
            tool_choice=tool_choice,
            all_tool_names=all_tool_names,
            retry_count=retry_count,
            tool_use_policy_family=tool_use_policy_family,
            tool_use_policy_mode=tool_use_policy_mode,
            allowed_tool_names=allowed_tool_names,
            breach_retry_result=breach_retry_result,
            stream=stream,
        )

    @staticmethod
    def _merge_model_provider_snapshots(
        billing_context: dict | None,
        *,
        provider: AIProvider | None,
        ai_model: AIModel | None,
    ) -> dict[str, object | None]:
        return GatewayCallLogBridge.merge_model_provider_snapshots(
            billing_context,
            provider=provider,
            ai_model=ai_model,
        )

    async def _call_chat_adapter(
        self,
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
        return await call_chat_adapter_impl(
            messages=messages,
            adapter=adapter,
            provider=provider,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
            stream=stream,
            tools=tools,
            tool_choice=tool_choice,
            extra_kwargs=extra_kwargs,
        )

    async def _stream_chat_adapter(
        self,
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
        async for chunk in stream_chat_adapter_impl(
            adapter=adapter,
            provider=provider,
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
            tools=tools,
            tool_choice=tool_choice,
            extra_kwargs=extra_kwargs,
        ):
            yield chunk

    async def get_provider_and_key(
        self,
        provider_code: str,
        tenant_id: int | None = None,
    ) -> tuple[AIProvider, ProviderApiKey]:
        """
        Get provider and available API Key.
        获取供应商和可用的 API Key。

        Args:
            provider_code: Provider code / 供应商代码
            tenant_id: Tenant ID / 企业 ID

        Returns:
            (provider, API Key) tuple / (供应商, API Key) 元组

        Raises:
            NotFoundException: Provider not found / 供应商不存在
            BusinessException: No available API Key / 没有可用的 API Key
        """
        dispatcher = getattr(self, "dispatcher", None)
        if dispatcher is not None:
            return await dispatcher.resolve_provider_and_key(
                provider_code=provider_code,
                tenant_id=tenant_id,
            )

        provider = await self.provider_repo.get_by_code(provider_code)
        if not provider or not provider.is_active:
            raise NotFoundException(message=_("ai.provider_not_found"))

        api_key = await self.api_key_repo.get_available_key(
            provider_id=provider.id,
            tenant_id=tenant_id,
        )
        if not api_key:
            raise BusinessException(message=_("ai.no_api_key"))
        if not api_key.is_available():
            raise BusinessException(message=_("ai.api_key_unavailable"))
        return provider, api_key

    async def _get_model(self, model_name: str, provider_id: int) -> AIModel | None:
        """
        Get model information.
        获取模型信息。

        Args:
            model_name: Model name / 模型名称
            provider_id: Provider ID / 供应商 ID

        Returns:
            AIModel instance, or None if not found / AIModel 实例，如果不存在则返回 None
        """
        dispatcher = getattr(self, "dispatcher", None)
        if dispatcher is not None:
            return await dispatcher.resolve_model(
                model_name=model_name,
                provider_id=provider_id,
            )

        model = await self.model_repo.get_active_by_code_and_provider(
            model_name,
            provider_id,
        )
        if model is not None:
            return model
        return await self.model_repo.get_active_by_name_and_provider(
            model_name,
            provider_id,
        )


__all__ = ["GatewayFacadeMixin"]
