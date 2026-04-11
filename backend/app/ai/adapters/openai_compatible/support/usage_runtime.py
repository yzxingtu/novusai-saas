"""Thin usage mixin that delegates to support-level usage helpers."""

from __future__ import annotations

from typing import Any

from app.ai.adapters.openai_compatible.support.usage_parser import (
    estimate_responses_stream_usage,
    extract_usage_int,
    extract_usage_tokens,
)
from app.ai.adapters.openai_compatible.support.usage_support import (
    build_terminal_stream_chunk,
    next_stream_event_with_timeout,
    retrieve_responses_usage,
)
from app.ai.adapters.openai_compatible.timeout_policy import normalize_timeout_seconds
from app.ai.exceptions import ProviderTimeoutError
from app.ai.types import ChatChunk, ChatMessage, ChatResponse
from app.core.i18n import _


class OpenAIAdapterUsageRuntimeMixin:
    """Shared usage and timeout behavior extracted from the adapter facade."""

    @staticmethod
    def _extract_usage_int(usage: Any, *field_names: str) -> int | None:
        return extract_usage_int(usage, *field_names)

    def _extract_usage_tokens(
        self,
        usage: Any,
    ) -> tuple[int | None, int | None, int | None]:
        return extract_usage_tokens(usage)

    async def _retrieve_responses_usage(
        self,
        response_id: str | None,
    ) -> tuple[int | None, int | None, int | None]:
        return await retrieve_responses_usage(
            client=self.client,
            response_id=response_id,
            extract_usage_tokens=self._extract_usage_tokens,
        )

    @staticmethod
    def _estimate_responses_stream_usage(
        messages: list[ChatMessage],
        output_text: str,
    ) -> tuple[int, int, int]:
        return estimate_responses_stream_usage(messages, output_text)

    @staticmethod
    def _normalize_timeout_seconds(value: Any) -> float | None:
        return normalize_timeout_seconds(value)

    async def _next_stream_event_with_timeout(
        self,
        stream: Any,
        *,
        timeout_seconds: float | None,
        model: str,
        wire_api: str,
    ) -> Any:
        return await next_stream_event_with_timeout(
            stream,
            timeout_seconds=timeout_seconds,
            model=model,
            wire_api=wire_api,
            timeout_error_factory=lambda: ProviderTimeoutError(
                message=_("ai.error.provider_timeout"),
                provider_code="openai",
                model_code=model,
            ),
        )

    def _chat_response_to_stream_chunk(self, response: ChatResponse) -> ChatChunk:
        return build_terminal_stream_chunk(response)


__all__ = ["OpenAIAdapterUsageRuntimeMixin"]
