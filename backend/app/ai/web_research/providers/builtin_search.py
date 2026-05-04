"""
Builtin web_search provider adapter for WebResearchRuntime.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any

from app.ai.web_research.contracts import SearchOptions
from app.ai.web_research.evidence import EvidenceStatus, SearchResultSet
from app.ai.web_research.normalization import normalize_search_item

if TYPE_CHECKING:
    from app.ai.tools.types import ExecutionContext
    from app.ai.web_search.types import WebSearchExecution

SearchRunner = Callable[
    [str, int, "ExecutionContext | None"],
    Awaitable["WebSearchExecution"],
]

BUILTIN_WEB_SEARCH_PROVIDER_ID = "builtin:web_search"
_COMPLETED_STATUSES = {"success", "no_results"}


class BuiltinWebSearchProvider:
    """Adapt the existing builtin web_search execution into SearchProvider."""

    def __init__(
        self,
        *,
        context: ExecutionContext | None = None,
        search_runner: SearchRunner | None = None,
        provider_id: str = BUILTIN_WEB_SEARCH_PROVIDER_ID,
    ) -> None:
        self._context = context
        self._search_runner = search_runner or _default_search_runner
        self._provider_id = provider_id

    @property
    def provider_id(self) -> str:
        return self._provider_id

    async def search(self, query: str, options: SearchOptions) -> SearchResultSet:
        normalized_query = str(query or "").strip()
        if not normalized_query:
            return SearchResultSet(
                query=normalized_query,
                provider=self.provider_id,
                status="failed",
                failure_kind="invalid_query",
                diagnostics={"error": "query parameter is required"},
            )

        max_results = min(max(1, int(options.max_results or 5)), 10)
        execution = await self._search_runner(
            normalized_query,
            max_results,
            self._context,
        )
        status: EvidenceStatus = (
            "completed" if execution.meta.status in _COMPLETED_STATUSES else "failed"
        )
        return SearchResultSet(
            query=normalized_query,
            provider=self.provider_id,
            items=[
                normalize_search_item(
                    title=str(getattr(item, "title", "") or ""),
                    url=str(getattr(item, "url", "") or ""),
                    snippet=str(getattr(item, "snippet", "") or ""),
                    rank=int(getattr(item, "rank", index) or index),
                    provider=self.provider_id,
                    allow_snippet_quality=options.allow_snippet_quality,
                    raw=_search_item_raw(item),
                )
                for index, item in enumerate(execution.items, start=1)
                if str(getattr(item, "url", "") or "").strip()
            ],
            status=status,
            failure_kind=(
                None
                if status == "completed"
                else _search_failure_kind(execution.meta.status)
            ),
            diagnostics=_search_diagnostics(execution),
        )


async def _default_search_runner(
    query: str,
    max_results: int,
    context: ExecutionContext | None,
) -> WebSearchExecution:
    from app.ai.tools.executors.builtin_executor import _run_web_search

    return await _run_web_search(query, max_results, context=context)


def _search_item_raw(item: Any) -> dict[str, Any]:
    if hasattr(item, "to_summary_item"):
        payload = item.to_summary_item()
    else:
        payload = {
            "title": getattr(item, "title", ""),
            "url": getattr(item, "url", ""),
            "snippet": getattr(item, "snippet", ""),
            "source": getattr(item, "source", ""),
            "provider": getattr(item, "provider", ""),
            "provider_mode": getattr(item, "provider_mode", ""),
            "rank": getattr(item, "rank", None),
        }
    return dict(payload)


def _search_diagnostics(execution: Any) -> dict[str, Any]:
    meta = execution.meta
    diagnostics: dict[str, Any] = {
        "builtin_tool": "web_search",
        "status": meta.status,
        "attempted_backends": list(meta.attempted_backends or []),
        "selected_backend": meta.selected_backend,
        "provider": meta.provider,
        "provider_mode": meta.provider_mode,
        "provider_chain": list(meta.provider_chain or []),
        "cache_hit": bool(meta.cache_hit),
        "latency_ms": int(meta.latency_ms or 0),
        "result_count": len(execution.items),
    }
    if meta.failure_reason:
        diagnostics["failure_reason"] = meta.failure_reason
    return diagnostics


def _search_failure_kind(status: str) -> str:
    normalized = str(status or "").strip() or "unknown"
    return f"search_{normalized}"


__all__ = [
    "BUILTIN_WEB_SEARCH_PROVIDER_ID",
    "BuiltinWebSearchProvider",
]
