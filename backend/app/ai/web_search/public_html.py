"""
Public HTML search fallback provider. / 公共 HTML 搜索回退提供器。
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.ai.web_search import public_html_parsing as _parsing
from app.ai.web_search import public_html_policy as _policy
from app.ai.web_search import public_html_state as _state
from app.ai.web_search import public_html_transport as _transport
from app.ai.web_search.types import (
    PROVIDER_MODE_PUBLIC,
    STATUS_NO_RESULTS,
    STATUS_PARSE_ERROR,
    STATUS_POLICY_FILTERED,
    STATUS_SUCCESS,
    STATUS_TIMEOUT,
    STATUS_UPSTREAM_ERROR,
    SearchProviderRun,
    SearchResultItem,
)
from app.core.logging import LogManager

if TYPE_CHECKING:
    from app.ai.tools.types import ExecutionContext

logger = LogManager.get_logger("ai.web_search")

PUBLIC_PROVIDER_BAIDU = "baidu"

_BACKEND_FAIL_STREAK = _state._BACKEND_FAIL_STREAK
_BACKEND_DISABLED = _state._BACKEND_DISABLED
_BACKEND_QUERY_CACHE = _state._BACKEND_QUERY_CACHE


@dataclass
class _HtmlSearchAttempt:
    backend_key: str
    status: str
    items: list[SearchResultItem]
    error: str | None = None


class BaseSearchProvider(ABC):
    @abstractmethod
    async def search(
        self,
        *,
        query: str,
        max_results: int,
        locale: str | None,
        timeout_seconds: int,
        context: ExecutionContext | None = None,
        strategy: str | None = None,
        runtime_provider_label: str | None = None,
        runtime_model_code: str | None = None,
    ) -> SearchProviderRun:
        raise NotImplementedError


def _normalize_text(text: str) -> str:
    return _parsing.normalize_text(text)


def _correct_query_year(query: str) -> str:
    return _policy.correct_query_year(query)


def _extract_baidu_public_results(html: str, max_results: int) -> list[dict[str, str]]:
    return _parsing.extract_baidu_public_results(html, max_results)


async def _search_with_baidu_public(
    query: str,
    max_results: int,
    *,
    timeout_seconds: int,
) -> _HtmlSearchAttempt:
    backend_key = "public:baidu"
    try:
        resp = await _transport.fetch_public_html(
            "https://www.baidu.com/s",
            params={"wd": query},
            timeout_seconds=timeout_seconds,
        )
        if resp.status_code >= 400:
            return _HtmlSearchAttempt(
                backend_key=backend_key,
                status=STATUS_UPSTREAM_ERROR,
                items=[],
                error=f"HTTP {resp.status_code}",
            )

        status = _parsing.classify_baidu_public_html(resp.text)
        if status == STATUS_SUCCESS:
            results = _parsing.extract_baidu_public_results(resp.text, max_results)
            filtered_results = _policy.filter_low_confidence_results(query, results)
            if filtered_results:
                return _HtmlSearchAttempt(
                    backend_key=backend_key,
                    status=status,
                    items=_parsing.make_items(
                        provider="baidu_public",
                        backend_key=backend_key,
                        raw_results=filtered_results,
                    ),
                )
            return _HtmlSearchAttempt(
                backend_key=backend_key,
                status=STATUS_POLICY_FILTERED,
                items=[],
                error="returned low-confidence results",
            )
        return _HtmlSearchAttempt(
            backend_key=backend_key,
            status=status,
            items=[],
            error=(
                "returned safety verification"
                if status == STATUS_POLICY_FILTERED
                else "returned no results"
                if status == STATUS_NO_RESULTS
                else "result parser missed current page structure"
                if status == STATUS_PARSE_ERROR
                else "returned an unreadable page"
            ),
        )
    except _transport.PublicHtmlTransportTimeout:
        return _HtmlSearchAttempt(
            backend_key=backend_key,
            status=STATUS_TIMEOUT,
            items=[],
            error="timeout",
        )
    except _transport.PublicHtmlTransportError as exc:
        logger.warning("Baidu public search failed: {}", exc)
        return _HtmlSearchAttempt(
            backend_key=backend_key,
            status=STATUS_UPSTREAM_ERROR,
            items=[],
            error=str(exc),
        )


def _build_failure_reason(attempts: list[_HtmlSearchAttempt]) -> str:
    parts: list[str] = []
    for attempt in attempts:
        detail = attempt.error or attempt.status
        if detail.startswith("returned ") or detail.startswith("HTTP "):
            parts.append(f"{attempt.backend_key} {detail}")
        else:
            parts.append(f"{attempt.backend_key} returned {detail}")
    return "; ".join(parts)


class PublicHtmlSearchProvider(BaseSearchProvider):
    def __init__(
        self,
        *,
        providers: list[str] | tuple[str, ...] | None = None,
    ) -> None:
        normalized = [str(item or "").strip().lower() for item in (providers or [])]
        self.providers = [
            item
            for item in normalized
            if item == PUBLIC_PROVIDER_BAIDU
        ]
        if not self.providers:
            self.providers = [PUBLIC_PROVIDER_BAIDU]

    async def search(
        self,
        *,
        query: str,
        max_results: int,
        locale: str | None,
        timeout_seconds: int,
        context: ExecutionContext | None = None,
        strategy: str | None = None,
        runtime_provider_label: str | None = None,
        runtime_model_code: str | None = None,
    ) -> SearchProviderRun:
        start = time.perf_counter()
        deadline = start + max(0.1, float(timeout_seconds))
        rewritten_query = _normalize_text(_correct_query_year(query))
        conv_id = _state.conv_id(context)
        attempts: list[_HtmlSearchAttempt] = []
        attempted_backends: list[str] = []

        provider_map = {
            PUBLIC_PROVIDER_BAIDU: _search_with_baidu_public,
        }

        for provider_name in self.providers:
            backend_key = f"public:{provider_name}"
            cache_key = _state.backend_cache_key(
                backend_key=backend_key,
                query=rewritten_query,
                strategy=strategy,
                runtime_provider_label=runtime_provider_label,
                runtime_model_code=runtime_model_code,
                locale=locale,
                max_results=max_results,
                context=context,
            )
            cached = _state.get_backend_cache(cache_key)
            if cached is not None:
                return SearchProviderRun(
                    provider=cached.provider,
                    provider_mode=cached.provider_mode,
                    backend_key=cached.backend_key,
                    status=cached.status,
                    items=list(cached.items),
                    failure_reason=cached.failure_reason,
                    latency_ms=int((time.perf_counter() - start) * 1000),
                    attempted_backends=[backend_key],
                    cache_hit=True,
                )

            if _state.backend_is_disabled(conv_id, backend_key):
                logger.info(
                    "web_search skip cooled-down public backend={} conv_id={} query={}",
                    backend_key,
                    conv_id,
                    rewritten_query[:80],
                )
                continue

            attempted_backends.append(backend_key)
            search_func = provider_map[provider_name]
            remaining_timeout = deadline - time.perf_counter()
            if remaining_timeout <= 0:
                attempts.append(
                    _HtmlSearchAttempt(
                        backend_key=backend_key,
                        status=STATUS_TIMEOUT,
                        items=[],
                        error="overall timeout budget exhausted",
                    )
                )
                logger.info(
                    "web_search public budget exhausted: backend={} conv_id={} query={}",
                    backend_key,
                    conv_id,
                    rewritten_query[:120],
                )
                break
            attempt = await search_func(
                rewritten_query,
                max_results,
                timeout_seconds=max(0.1, remaining_timeout),
            )
            attempts.append(attempt)
            _state.record_backend_outcome(conv_id, backend_key, attempt.status)
            logger.info(
                "web_search public attempt: backend={} status={} result_count={} query={}",
                backend_key,
                attempt.status,
                len(attempt.items),
                rewritten_query[:120],
            )
            if attempt.status == STATUS_SUCCESS and attempt.items:
                result = SearchProviderRun(
                    provider=attempt.items[0].provider,
                    provider_mode=PROVIDER_MODE_PUBLIC,
                    backend_key=backend_key,
                    status=STATUS_SUCCESS,
                    items=list(attempt.items),
                    latency_ms=int((time.perf_counter() - start) * 1000),
                    attempted_backends=list(attempted_backends),
                )
                _state.set_backend_cache(cache_key, result)
                return result

        latency_ms = int((time.perf_counter() - start) * 1000)
        if attempts and all(attempt.status == STATUS_NO_RESULTS for attempt in attempts):
            return SearchProviderRun(
                provider=None,
                provider_mode=PROVIDER_MODE_PUBLIC,
                backend_key=attempted_backends[-1] if attempted_backends else None,
                status=STATUS_NO_RESULTS,
                items=[],
                failure_reason=_build_failure_reason(attempts),
                latency_ms=latency_ms,
                attempted_backends=list(attempted_backends),
            )

        if attempts and any(attempt.status == STATUS_POLICY_FILTERED for attempt in attempts):
            status = STATUS_POLICY_FILTERED
        elif attempts and any(attempt.status == STATUS_PARSE_ERROR for attempt in attempts):
            status = STATUS_PARSE_ERROR
        elif attempts and any(attempt.status == STATUS_TIMEOUT for attempt in attempts):
            status = STATUS_TIMEOUT
        else:
            status = STATUS_UPSTREAM_ERROR

        return SearchProviderRun(
            provider=None,
            provider_mode=PROVIDER_MODE_PUBLIC,
            backend_key=attempted_backends[-1] if attempted_backends else None,
            status=status,
            items=[],
            failure_reason=(
                _build_failure_reason(attempts)
                if attempts
                else "all public search backends temporarily skipped"
            ),
            latency_ms=latency_ms,
            attempted_backends=list(attempted_backends),
        )


__all__ = [
    "BaseSearchProvider",
    "PUBLIC_PROVIDER_BAIDU",
    "PublicHtmlSearchProvider",
    "_extract_baidu_public_results",
    "_search_with_baidu_public",
]
