from __future__ import annotations

from app.ai.web_search.orchestrator_support.diagnostics import (
    decorate_duplicate_query_output,
)
from app.ai.web_search.orchestrator_support.summary_builder import (
    build_search_output_text,
)
from app.ai.web_search.types import (
    STATUS_NO_RESULTS,
    STATUS_PARSE_ERROR,
    STATUS_SUCCESS,
    STATUS_TIMEOUT,
    SearchResultItem,
    WebSearchExecution,
    WebSearchExecutionMeta,
)


def build_execution(
    *,
    query: str,
    items: list[SearchResultItem],
    meta: WebSearchExecutionMeta,
    duplicate_signature: tuple[int, str, str, str, str, str, int],
    search_engine_hosts: frozenset[str],
    seen_signatures: set[tuple[int, str, str, str, str, str, int]],
) -> WebSearchExecution:
    if meta.status == STATUS_SUCCESS and items:
        output = build_search_output_text(
            query,
            items,
            search_engine_hosts=search_engine_hosts,
        )
    elif meta.status == STATUS_NO_RESULTS:
        output = f"No results found for: {query}"
    elif meta.status == STATUS_TIMEOUT:
        output = f"Search source timed out: {meta.failure_reason or 'timeout'}"
    elif meta.status == STATUS_PARSE_ERROR:
        output = (
            f"Search parser unavailable: {meta.failure_reason or 'search result parsing failed'}"
        )
    else:
        output = f"Search source unavailable: {meta.failure_reason or 'search unavailable'}"

    output = decorate_duplicate_query_output(
        output=output,
        signature=duplicate_signature,
        status=meta.status,
        seen_signatures=seen_signatures,
    )
    return WebSearchExecution(output=output, items=items, meta=meta)


__all__ = ["build_execution"]
