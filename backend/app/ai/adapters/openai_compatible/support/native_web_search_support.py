"""Native web-search helpers for OpenAI-compatible adapters."""

from __future__ import annotations

from typing import Any

from app.ai.adapters.openai_compatible.support.native_web_search_parser import (
    extract_native_web_search_items,
    extract_native_web_search_items_from_text,
    extract_native_web_search_request_count,
    extract_native_web_search_usage,
)
from app.ai.adapters.openai_compatible.support.native_web_search_policy import (
    map_native_web_search_error as map_native_web_search_error_impl,
)
from app.ai.adapters.openai_compatible.support.native_web_search_policy import (
    supports_native_web_search_model,
)
from app.ai.adapters.openai_compatible.support.native_web_search_runner import (
    native_web_search_via_responses as native_web_search_via_responses_impl,
)
from app.ai.adapters.openai_compatible.support.native_web_search_runner import (
    native_web_search_via_stream as native_web_search_via_stream_impl,
)
from app.ai.adapters.openai_compatible.support.stream_cleanup import (
    aclose_openai_stream,
)
from app.ai.exceptions import convert_openai_error
from app.ai.prompt_contracts import render_prompt_contract
from app.ai.web_search.types import (
    PROVIDER_MODE_NATIVE,
    STATUS_UNSUPPORTED,
    SearchProviderRun,
)


class OpenAIAdapterNativeWebSearchMixin:
    """Thin native web-search facade that delegates to support modules."""

    @classmethod
    def _supports_native_web_search_model(cls, model: str) -> bool:
        return supports_native_web_search_model(model)

    def _native_web_search_effective_request(self, model: str) -> dict[str, Any]:
        return self.resolve_effective_model_request(
            model=model,
            model_config=self.config.get("model_config"),
            wire_api="responses",
        )

    def _native_web_search_upstream_model(self, model: str) -> str:
        effective_request = self._native_web_search_effective_request(model)
        return str(effective_request.get("upstream_model") or model).strip()

    async def _native_web_search_via_stream(
        self,
        *,
        query: str,
        max_results: int,
        locale: str | None,
        timeout_seconds: int,
        model: str,
        provider_label: str,
        backend_key: str,
        instructions: str,
    ) -> SearchProviderRun | None:
        return await native_web_search_via_stream_impl(
            adapter=self,
            query=query,
            max_results=max_results,
            locale=locale,
            timeout_seconds=timeout_seconds,
            model=model,
            provider_label=provider_label,
            backend_key=backend_key,
            instructions=instructions,
            aclose_stream=aclose_openai_stream,
            extract_items_from_text=extract_native_web_search_items_from_text,
            extract_usage=extract_native_web_search_usage,
        )

    def _map_native_web_search_error(self, error: Exception) -> str:
        return map_native_web_search_error_impl(
            error,
            extract_status_code=self._extract_status_code,
        )

    def supports_native_web_search(self, model: str) -> bool:
        capabilities = getattr(self, "protocol_capabilities", None)
        if capabilities is not None:
            supports_responses = bool(capabilities.supports_wire_api("responses"))
        else:
            supports_responses = bool(self._use_responses_api())
        if not supports_responses:
            return False
        upstream_model = self._native_web_search_upstream_model(model)
        return self._supports_native_web_search_model(upstream_model)

    async def native_web_search(
        self,
        *,
        query: str,
        max_results: int,
        locale: str | None,
        timeout_seconds: int,
        model: str | None = None,
        provider_label: str | None = None,
        backend_key: str | None = None,
    ) -> SearchProviderRun:
        logical_model = str(model or "").strip()
        effective_model = self._native_web_search_upstream_model(logical_model)
        effective_provider = str(provider_label or "openai_compatible")
        effective_backend_key = (
            backend_key or f"native:{effective_provider}:{effective_model}"
        )
        if not self.supports_native_web_search(logical_model):
            return SearchProviderRun(
                provider=effective_provider,
                provider_mode=PROVIDER_MODE_NATIVE,
                backend_key=effective_backend_key,
                status=STATUS_UNSUPPORTED,
                items=[],
                failure_reason="responses api or model family does not support native web search",
                attempted_backends=[effective_backend_key],
            )

        return await self._native_web_search_via_responses(
            query=query,
            max_results=max_results,
            locale=locale,
            timeout_seconds=timeout_seconds,
            model=effective_model,
            provider_label=effective_provider,
            backend_key=effective_backend_key,
        )

    async def _native_web_search_via_responses(
        self,
        *,
        query: str,
        max_results: int,
        locale: str | None,
        timeout_seconds: int,
        model: str,
        provider_label: str,
        backend_key: str,
    ) -> SearchProviderRun:
        return await native_web_search_via_responses_impl(
            adapter=self,
            query=query,
            max_results=max_results,
            locale=locale,
            timeout_seconds=timeout_seconds,
            model=model,
            provider_label=provider_label,
            backend_key=backend_key,
            aclose_stream=aclose_openai_stream,
            render_prompt_contract_fn=render_prompt_contract,
            extract_items=extract_native_web_search_items,
            extract_items_from_text=extract_native_web_search_items_from_text,
            extract_request_count=extract_native_web_search_request_count,
            extract_usage=extract_native_web_search_usage,
            map_error=map_native_web_search_error_impl,
            convert_openai_error_fn=convert_openai_error,
        )


__all__ = ["OpenAIAdapterNativeWebSearchMixin"]
