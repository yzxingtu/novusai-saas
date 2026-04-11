"""Thin orchestration helpers for native Responses web search."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Protocol

from app.ai.adapters.openai_compatible.support.native_web_search_request_builder import (
    build_native_web_search_request,
)
from app.ai.adapters.openai_compatible.support.native_web_search_result_builder import (
    build_native_web_search_error_run,
    build_native_web_search_items_result,
    build_native_web_search_unsupported_run,
)
from app.ai.adapters.openai_compatible.support.native_web_search_stream_runtime import (
    consume_native_web_search_stream,
)
from app.ai.exceptions import AIGatewayError
from app.ai.web_search.types import SearchProviderRun
from app.core.logging import LogManager

logger = LogManager.get_logger("ai")


class NativeWebSearchAdapterProtocol(Protocol):
    client: Any

    def _log_upstream_request(
        self,
        *,
        endpoint_path: str,
        model: str,
        stream: bool,
        wire_api: str | None = None,
    ) -> None: ...

    def _log_upstream_error(
        self,
        error: Exception,
        *,
        endpoint_path: str,
        model: str,
        wire_api: str | None = None,
    ) -> None: ...

    def _extract_responses_text(self, response: Any) -> str: ...

    @staticmethod
    def _extract_status_code(error: Exception) -> int | None: ...


async def native_web_search_via_stream(
    *,
    adapter: NativeWebSearchAdapterProtocol,
    query: str,
    max_results: int,
    locale: str | None,
    timeout_seconds: int,
    model: str,
    provider_label: str,
    backend_key: str,
    instructions: str,
    aclose_stream: Any,
    extract_items_from_text: Any,
    extract_usage: Any,
) -> SearchProviderRun | None:
    _ = locale
    try:
        stream = await adapter.client.responses.create(
            **build_native_web_search_request(
                model=model,
                query=query,
                instructions=instructions,
                timeout_seconds=timeout_seconds,
                stream=True,
            )
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Native web search stream fallback request failed: provider={} model={} error={}",
            provider_label,
            model,
            str(exc),
        )
        return None

    capture = await consume_native_web_search_stream(
        adapter=adapter,
        stream=stream,
        provider_label=provider_label,
        model=model,
        aclose_stream=aclose_stream,
    )
    if capture is None or not capture.saw_web_search_call:
        return None

    input_tokens, output_tokens, total_tokens = extract_usage(
        SimpleNamespace(usage=capture.response_usage)
    )
    items, saw_unverifiable_url = extract_items_from_text(
        capture.final_text,
        provider_label=provider_label,
        backend_key=backend_key,
        max_results=max_results,
    )
    return build_native_web_search_items_result(
        provider_label=provider_label,
        backend_key=backend_key,
        items=items,
        saw_unverifiable_url=saw_unverifiable_url,
        no_results_reason="native web search stream returned no candidate sources",
        parse_error_reason=(
            "native web search stream returned no verifiable absolute URLs"
        ),
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
    )


async def native_web_search_via_responses(
    *,
    adapter: NativeWebSearchAdapterProtocol,
    query: str,
    max_results: int,
    locale: str | None,
    timeout_seconds: int,
    model: str,
    provider_label: str,
    backend_key: str,
    aclose_stream: Any,
    render_prompt_contract_fn: Any,
    extract_items: Any,
    extract_items_from_text: Any,
    extract_request_count: Any,
    extract_usage: Any,
    map_error: Any,
    convert_openai_error_fn: Any,
) -> SearchProviderRun:
    instructions = render_prompt_contract_fn(
        "hosted_web_search_candidate_instructions",
        locale=locale,
    )
    try:
        adapter._log_upstream_request(
            endpoint_path="responses",
            model=model,
            stream=False,
            wire_api="responses",
        )
        response = await adapter.client.responses.create(
            **build_native_web_search_request(
                model=model,
                query=query,
                instructions=instructions,
                timeout_seconds=timeout_seconds,
                stream=False,
                include_sources=True,
            )
        )
        input_tokens, output_tokens, total_tokens = extract_usage(response)
        request_count = extract_request_count(response)
        items, saw_unverifiable_url = extract_items(
            response,
            provider_label=provider_label,
            backend_key=backend_key,
            max_results=max_results,
        )
        if items or saw_unverifiable_url:
            return build_native_web_search_items_result(
                provider_label=provider_label,
                backend_key=backend_key,
                items=items,
                saw_unverifiable_url=saw_unverifiable_url,
                no_results_reason="native web search returned no candidate sources",
                parse_error_reason=(
                    "native web search returned no verifiable absolute URLs"
                ),
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
            )
        if request_count <= 0:
            stream_fallback_run = await native_web_search_via_stream(
                adapter=adapter,
                query=query,
                max_results=max_results,
                locale=locale,
                timeout_seconds=timeout_seconds,
                model=model,
                provider_label=provider_label,
                backend_key=backend_key,
                instructions=instructions,
                aclose_stream=aclose_stream,
                extract_items_from_text=extract_items_from_text,
                extract_usage=extract_usage,
            )
            if stream_fallback_run is not None:
                return stream_fallback_run
            return build_native_web_search_unsupported_run(
                provider_label=provider_label,
                backend_key=backend_key,
                failure_reason=(
                    "provider responses runtime accepted native web search request "
                    "but did not execute hosted web_search"
                ),
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
            )
        return build_native_web_search_items_result(
            provider_label=provider_label,
            backend_key=backend_key,
            items=[],
            saw_unverifiable_url=False,
            no_results_reason="native web search returned no candidate sources",
            parse_error_reason="native web search returned no verifiable absolute URLs",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
        )
    except Exception as exc:  # noqa: BLE001
        adapter._log_upstream_error(
            exc,
            endpoint_path="responses",
            model=model,
            wire_api="responses",
        )
        converted = exc if isinstance(exc, AIGatewayError) else convert_openai_error_fn(
            exc,
            provider_code="openai",
            model_code=model,
        )
        return build_native_web_search_error_run(
            provider_label=provider_label,
            backend_key=backend_key,
            status=map_error(
                exc,
                extract_status_code=adapter._extract_status_code,
            ),
            failure_reason=str(converted),
        )


__all__ = [
    "NativeWebSearchAdapterProtocol",
    "native_web_search_via_responses",
    "native_web_search_via_stream",
]
