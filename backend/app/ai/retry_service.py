"""
AI Retry Service / AI 重试服务

Handles exponential backoff retry and API Key rotation logic.
Extracted from AIGateway to reduce God Object complexity.
负责指数退避重试、API Key 轮换逻辑。
从 AIGateway 提取，降低 God Object 复杂度。
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from app.ai.adapters import AdapterRegistry
from app.ai.exceptions import (
    AIGatewayError,
    ProviderError,
    is_retryable,
)
from app.core.i18n import _
from app.core.logging import LogManager
from app.models.ai import AIProvider, ProviderApiKey
from app.repositories.ai import ProviderApiKeyRepository

logger = LogManager.get_logger("ai")

# Retry configuration / 重试配置
MAX_RETRIES = 3
RETRY_BASE_DELAY = 1.0  # Base delay (seconds) / 基础延迟（秒）
RETRY_MULTIPLIER = 2.0  # Exponential multiplier / 指数倍数

_T = TypeVar("_T")


class RetryService:
    """
    AI Call Retry Service / AI 调用重试服务

    Responsibilities / 职责：
    - Exponential backoff retry / 指数退避重试
    - API Key rotation / API Key 轮换
    - Adapter creation / 适配器创建
    """

    def __init__(self, api_key_repo: ProviderApiKeyRepository) -> None:
        self._api_key_repo = api_key_repo

    async def execute_with_retry(
        self,
        provider: AIProvider,
        api_key: ProviderApiKey,
        model: str,
        call_fn: Callable[[Any], Awaitable[_T]],
        tenant_id: int | None = None,
        log_key: str = "ai.log.gateway_chat_call",
    ) -> tuple[_T, int, ProviderApiKey]:
        """
        Generic exponential backoff retry.
        通用指数退避重试。

        Create adapter → call call_fn(adapter) → handle exceptions/retry/Key rotation.
        创建适配器 → 调用 call_fn(adapter) → 处理异常/重试/Key 轮换。

        Args:
            provider: AI provider / AI 供应商
            api_key: Current API Key / 当前 API Key
            model: Model name / 模型名称
            call_fn: Async function that receives adapter and returns result / 接收 adapter 实例并返回结果的异步函数
            tenant_id: Tenant ID (for getting backup Key) / 企业 ID（用于获取备用 Key）
            log_key: Log i18n key / 日志 i18n key

        Returns:
            (response, retry_count, used_api_key) tuple / 元组

        Raises:
            AIGatewayError: Raises the last exception after all retries fail / 所有重试均失败后抛出最后一个异常
        """
        current_key = api_key
        last_error: AIGatewayError | None = None

        for attempt in range(MAX_RETRIES + 1):
            try:
                adapter = AdapterRegistry.create_adapter(
                    provider_type=provider.type,
                    api_key=current_key.decrypt_key(),
                    base_url=provider.base_url,
                    provider_config=provider.config,
                )

                logger.info(
                    "AI call: provider={} model={} attempt={} log_key={}",
                    provider.code,
                    model,
                    attempt,
                    log_key,
                )

                response = await call_fn(adapter)

                if attempt > 0:
                    logger.info(
                        "Retry succeeded: provider={} model={} attempt={}",
                        provider.code, model, attempt,
                    )

                return response, attempt, current_key

            except AIGatewayError as e:
                last_error = e

                if not is_retryable(e):
                    logger.error(
                        "Non-retryable error: provider={} model={} code={} error={}",
                        provider.code, model, e.error_code, str(e),
                    )
                    raise

                if attempt >= MAX_RETRIES:
                    logger.error(
                        "Max retries exhausted: provider={} model={} attempts={} error={}",
                        provider.code, model, attempt + 1, str(e),
                    )
                    raise

                delay = RETRY_BASE_DELAY * (RETRY_MULTIPLIER ** attempt)
                if e.retry_after and e.retry_after > delay:
                    delay = float(e.retry_after)

                logger.warning(
                    "Retrying after error: provider={} model={} attempt={} delay={}s code={} error={}",
                    provider.code, model, attempt, delay, e.error_code, str(e),
                )

                next_key = await self.get_next_api_key(
                    provider_id=provider.id,
                    current_key_id=current_key.id,
                    tenant_id=tenant_id,
                )
                if next_key:
                    logger.info(
                        "Switching API key: provider={} old_key={} new_key={}",
                        provider.code, current_key.id, next_key.id,
                    )
                    current_key = next_key

                await asyncio.sleep(delay)

            except Exception as e:
                logger.error(
                    "Unexpected error: provider={} model={} error={}",
                    provider.code, model, str(e),
                )
                raise ProviderError(
                    message=str(e),
                    provider_code=provider.code,
                    model_code=model,
                    original_error=e,
                )

        if last_error:
            raise last_error
        raise ProviderError(
            message=_("ai.request_failed"),
            provider_code=provider.code,
            model_code=model,
        )

    async def get_next_api_key(
        self,
        provider_id: int,
        current_key_id: int,
        tenant_id: int | None = None,
    ) -> ProviderApiKey | None:
        """
        Get next available API Key (for rotation on retry).
        获取下一个可用的 API Key（用于重试时轮换）。

        Prioritizes same-level Keys (same tenant_id),
        falls back to platform-level Key if none found.
        优先查找同级别（同 tenant_id）的其他 Key，
        如果没有则回退到平台级 Key。

        Args:
            provider_id: Provider ID / 供应商 ID
            current_key_id: Current Key ID (excluded) / 当前 Key 的 ID（排除）
            tenant_id: Tenant ID / 企业 ID

        Returns:
            Next available API Key, or None / 下一个可用的 API Key，如果没有则返回 None
        """
        return await self._api_key_repo.get_next_available_key(
            provider_id=provider_id,
            exclude_key_id=current_key_id,
            tenant_id=tenant_id,
        )


__all__ = ["RetryService", "MAX_RETRIES", "RETRY_BASE_DELAY", "RETRY_MULTIPLIER"]
