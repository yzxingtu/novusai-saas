"""Retry orchestration collaborator for AIGateway facade."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from app.ai.retry_service import RetryService
from app.models.ai import AIProvider, ProviderApiKey

_T = TypeVar("_T")


class GatewayRetryOrchestrator:
    """Delegate retry/key-rotation orchestration behind a narrow interface."""

    def __init__(self, retry_service: RetryService):
        self._retry_service = retry_service

    async def execute_with_retry(
        self,
        *,
        provider: AIProvider,
        api_key: ProviderApiKey,
        model: str,
        call_fn: Callable[[Any], Awaitable[_T]],
        tenant_id: int | None = None,
        log_key: str = "ai.log.gateway_chat_call",
        adapter_extra: dict[str, Any] | None = None,
        max_retries: int | None = None,
    ) -> tuple[_T, int, ProviderApiKey]:
        return await self._retry_service.execute_with_retry(
            provider=provider,
            api_key=api_key,
            model=model,
            call_fn=call_fn,
            tenant_id=tenant_id,
            log_key=log_key,
            adapter_extra=adapter_extra,
            max_retries=max_retries,
        )
