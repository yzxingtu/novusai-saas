"""SearchProviderRun builders for native web-search execution."""

from __future__ import annotations

from app.ai.web_search.types import (
    PROVIDER_MODE_NATIVE,
    STATUS_NO_RESULTS,
    STATUS_PARSE_ERROR,
    STATUS_SUCCESS,
    STATUS_UNSUPPORTED,
    SearchProviderRun,
    SearchResultItem,
)


def build_native_web_search_run(
    *,
    provider_label: str,
    backend_key: str,
    status: str,
    items: list[SearchResultItem],
    failure_reason: str | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    total_tokens: int | None = None,
) -> SearchProviderRun:
    return SearchProviderRun(
        provider=provider_label,
        provider_mode=PROVIDER_MODE_NATIVE,
        backend_key=backend_key,
        status=status,
        items=items,
        failure_reason=failure_reason,
        attempted_backends=[backend_key],
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
    )


def build_native_web_search_items_result(
    *,
    provider_label: str,
    backend_key: str,
    items: list[SearchResultItem],
    saw_unverifiable_url: bool,
    no_results_reason: str,
    parse_error_reason: str,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    total_tokens: int | None = None,
) -> SearchProviderRun:
    if items:
        return build_native_web_search_run(
            provider_label=provider_label,
            backend_key=backend_key,
            status=STATUS_SUCCESS,
            items=items,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
        )
    if saw_unverifiable_url:
        return build_native_web_search_run(
            provider_label=provider_label,
            backend_key=backend_key,
            status=STATUS_PARSE_ERROR,
            items=[],
            failure_reason=parse_error_reason,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
        )
    return build_native_web_search_run(
        provider_label=provider_label,
        backend_key=backend_key,
        status=STATUS_NO_RESULTS,
        items=[],
        failure_reason=no_results_reason,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
    )


def build_native_web_search_unsupported_run(
    *,
    provider_label: str,
    backend_key: str,
    failure_reason: str,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    total_tokens: int | None = None,
) -> SearchProviderRun:
    return build_native_web_search_run(
        provider_label=provider_label,
        backend_key=backend_key,
        status=STATUS_UNSUPPORTED,
        items=[],
        failure_reason=failure_reason,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
    )


def build_native_web_search_error_run(
    *,
    provider_label: str,
    backend_key: str,
    status: str,
    failure_reason: str,
) -> SearchProviderRun:
    return build_native_web_search_run(
        provider_label=provider_label,
        backend_key=backend_key,
        status=status,
        items=[],
        failure_reason=failure_reason,
    )


__all__ = [
    "build_native_web_search_error_run",
    "build_native_web_search_items_result",
    "build_native_web_search_run",
    "build_native_web_search_unsupported_run",
]
