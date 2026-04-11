"""Compatibility facade for native Responses web-search execution."""

from __future__ import annotations

from typing import Any

from app.ai.adapters.openai_compatible.support.native_web_search_parser import (
    extract_native_web_search_items,
    extract_native_web_search_items_from_text,
    extract_native_web_search_request_count,
    extract_native_web_search_usage,
)
from app.ai.adapters.openai_compatible.support.native_web_search_policy import (
    map_native_web_search_error,
)
from app.ai.adapters.openai_compatible.support.native_web_search_runner import (
    NativeWebSearchAdapterProtocol,
)
from app.ai.adapters.openai_compatible.support.native_web_search_runner import (
    native_web_search_via_responses as native_web_search_via_responses_impl,
)
from app.ai.adapters.openai_compatible.support.native_web_search_runner import (
    native_web_search_via_stream as native_web_search_via_stream_impl,
)
from app.ai.exceptions import convert_openai_error
from app.ai.prompt_contracts import render_prompt_contract
from app.ai.web_search.types import SearchProviderRun


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
) -> SearchProviderRun | None:
    return await native_web_search_via_stream_impl(
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
        extract_items_from_text=extract_native_web_search_items_from_text,
        extract_usage=extract_native_web_search_usage,
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
) -> SearchProviderRun:
    return await native_web_search_via_responses_impl(
        adapter=adapter,
        query=query,
        max_results=max_results,
        locale=locale,
        timeout_seconds=timeout_seconds,
        model=model,
        provider_label=provider_label,
        backend_key=backend_key,
        aclose_stream=aclose_stream,
        render_prompt_contract_fn=render_prompt_contract,
        extract_items=extract_native_web_search_items,
        extract_items_from_text=extract_native_web_search_items_from_text,
        extract_request_count=extract_native_web_search_request_count,
        extract_usage=extract_native_web_search_usage,
        map_error=map_native_web_search_error,
        convert_openai_error_fn=convert_openai_error,
    )


__all__ = [
    "NativeWebSearchAdapterProtocol",
    "native_web_search_via_responses",
    "native_web_search_via_stream",
]
