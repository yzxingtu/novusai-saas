"""
Public HTML search fallback provider. / 公共 HTML 搜索回退提供器。
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

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
from app.core.config import settings
from app.core.logging import LogManager

if TYPE_CHECKING:
    from app.ai.tools.types import ExecutionContext

logger = LogManager.get_logger("ai.web_search")

_DEFAULT_WEB_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "text/plain;q=0.8,*/*;q=0.7"
    ),
    "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
}

PUBLIC_PROVIDER_BAIDU = "baidu"
PUBLIC_PROVIDER_SO360 = "so360"

_SEARCH_ENGINE_HOSTS = frozenset({"www.baidu.com", "baidu.com", "www.so.com", "so.com"})
_QUERY_RELEVANCE_MIN_RATIO = 0.28
_HISTORY_QUERY_TERMS = frozenset(
    {
        "历史",
        "history",
        "historical",
        "年代",
        "era",
        "古代",
        "ancient",
        "世纪",
        "战时",
    }
)

_BACKEND_FAIL_STREAK: dict[tuple[int, str], int] = {}
_BACKEND_DISABLED: dict[int, set[str]] = {}
_BACKEND_QUERY_CACHE: dict[
    tuple[int, str, str, str, str, str, str, int],
    SearchProviderRun,
] = {}


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
        context: "ExecutionContext | None" = None,
        strategy: str | None = None,
        runtime_provider_label: str | None = None,
        runtime_model_code: str | None = None,
    ) -> SearchProviderRun:
        raise NotImplementedError


def _normalize_text(text: str) -> str:
    return " ".join((text or "").split())


def _clean_search_snippet(text: str, title: str) -> str:
    normalized = _normalize_text(text)
    normalized_title = _normalize_text(title)
    if normalized_title and normalized.startswith(normalized_title):
        normalized = _normalize_text(normalized[len(normalized_title) :])
    return normalized


def _extract_baidu_public_results(html: str, max_results: int) -> list[dict[str, str]]:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "lxml")
    results: list[dict[str, str]] = []
    seen_urls: set[str] = set()

    for container in soup.select("div.result.c-container, div.c-container"):
        title_link = container.select_one("h3 a")
        if title_link is None:
            continue

        href = (title_link.get("href") or "").strip()
        title = _normalize_text(title_link.get_text(" ", strip=True))
        if not href or not title or href in seen_urls:
            continue

        snippet = _clean_search_snippet(
            container.get_text(" ", strip=True),
            title,
        )
        results.append({"title": title, "url": href, "snippet": snippet})
        seen_urls.add(href)
        if len(results) >= max_results:
            break

    return results


def _extract_so360_public_results(html: str, max_results: int) -> list[dict[str, str]]:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "lxml")
    results: list[dict[str, str]] = []
    seen_urls: set[str] = set()

    selectors = (
        "li.res-list",
        "div.res-list",
        "li[class*='result']",
        "div[class*='result']",
        "div[class*='res-list']",
    )
    containers = []
    for selector in selectors:
        containers = soup.select(selector)
        if containers:
            break

    for container in containers:
        title_link = container.select_one("h3 a")
        if title_link is None:
            continue

        href = (title_link.get("href") or "").strip()
        title = _normalize_text(title_link.get_text(" ", strip=True))
        if not href or not title or href in seen_urls:
            continue

        snippet = _clean_search_snippet(
            container.get_text(" ", strip=True),
            title,
        )
        results.append({"title": title, "url": href, "snippet": snippet})
        seen_urls.add(href)
        if len(results) >= max_results:
            break

    return results


def _extract_title_from_html(html: str) -> str:
    lowered = (html or "").lower()
    start = lowered.find("<title")
    if start < 0:
        return ""
    start = lowered.find(">", start)
    if start < 0:
        return ""
    end = lowered.find("</title>", start + 1)
    if end < 0:
        return ""
    return _normalize_text((html or "")[start + 1 : end])


def _html_may_contain_search_results(html: str) -> bool:
    lowered = (html or "").lower()
    return any(
        hint in lowered
        for hint in (
            "res-title",
            "res-desc",
            "res-link",
            "res-list",
            "result-item",
            "result-card",
            "c-container",
            "title-box",
        )
    )


def _classify_baidu_public_html(html: str) -> str:
    if not html:
        return STATUS_UPSTREAM_ERROR
    if "百度安全验证" in html or "安全验证" in _extract_title_from_html(html):
        return STATUS_POLICY_FILTERED
    if _extract_baidu_public_results(html, 1):
        return STATUS_SUCCESS
    if (
        "抱歉，没有找到与" in html
        or "没有找到该URL" in html
        or "未找到相关结果" in html
    ):
        return STATUS_NO_RESULTS
    if _html_may_contain_search_results(html):
        return STATUS_PARSE_ERROR
    return STATUS_UPSTREAM_ERROR


def _classify_so360_public_html(html: str) -> str:
    if not html:
        return STATUS_UPSTREAM_ERROR
    title = _extract_title_from_html(html)
    normalized = _normalize_text(html)
    if "安全验证" in title or "请输入验证码" in normalized:
        return STATUS_POLICY_FILTERED
    if _extract_so360_public_results(html, 1):
        return STATUS_SUCCESS
    if (
        "没有找到相关结果" in normalized
        or "相关结果约0个" in normalized
        or "未找到相关搜索结果" in normalized
        or "抱歉，未找到相关搜索结果" in normalized
    ):
        return STATUS_NO_RESULTS
    if _html_may_contain_search_results(html):
        return STATUS_PARSE_ERROR
    return STATUS_UPSTREAM_ERROR


def _is_cjk(char: str) -> bool:
    return "\u4e00" <= char <= "\u9fff"


def _scan_search_tokens(text: str) -> set[str]:
    tokens: set[str] = set()
    idx = 0
    length = len(text)
    while idx < length:
        char = text[idx]
        if _is_cjk(char):
            start = idx
            while idx < length and _is_cjk(text[idx]):
                idx += 1
            segment = text[start:idx]
            if len(segment) >= 2:
                tokens.add(segment)
            continue
        if char.isdigit():
            start = idx
            while idx < length and text[idx].isdigit():
                idx += 1
            segment = text[start:idx]
            if len(segment) == 4:
                tokens.add(segment)
            continue
        if char.isalpha():
            start = idx
            while idx < length and text[idx].isalpha():
                idx += 1
            segment = text[start:idx]
            if len(segment) >= 2:
                tokens.add(segment)
            continue
        idx += 1
    return tokens


def _strip_site_filters(query: str) -> str:
    tokens = []
    for token in (query or "").split():
        if token.lower().startswith("site:"):
            continue
        tokens.append(token)
    return " ".join(tokens)


def _query_tokens_for_relevance(query: str) -> set[str]:
    scrubbed = _strip_site_filters(query)
    return _scan_search_tokens(scrubbed.lower())


def _result_text_tokens(result: dict[str, str], *, include_url: bool) -> set[str]:
    parts = [str(result.get("title") or ""), str(result.get("snippet") or "")]
    if include_url:
        parts.append(str(result.get("url") or ""))
    hay = _normalize_text(" ".join(parts)).lower()
    return _scan_search_tokens(hay)


def _result_is_search_wrapper(url: str) -> bool:
    try:
        host = (urlparse(url).hostname or "").lower()
    except Exception:
        return False
    return host in _SEARCH_ENGINE_HOSTS


def _result_passes_relevance(query: str, result: dict[str, str]) -> bool:
    q_tokens = _query_tokens_for_relevance(query)
    url = str(result.get("url") or "")
    if not q_tokens:
        return not _result_is_search_wrapper(url)

    ts_tokens = _result_text_tokens(result, include_url=False)
    ts_hits = len(q_tokens & ts_tokens)
    ts_ratio = ts_hits / len(q_tokens)
    if ts_ratio >= _QUERY_RELEVANCE_MIN_RATIO or ts_hits >= max(
        1, (len(q_tokens) + 1) // 2
    ):
        return True

    if _result_is_search_wrapper(url):
        return False

    all_tokens = _result_text_tokens(result, include_url=True)
    all_hits = len(q_tokens & all_tokens)
    return all_hits / len(q_tokens) >= _QUERY_RELEVANCE_MIN_RATIO


def _filter_low_confidence_results(
    query: str,
    results: list[dict[str, str]],
) -> list[dict[str, str]]:
    return [result for result in results if _result_passes_relevance(query, result)]


def _looks_historical_query(query: str) -> bool:
    normalized = _normalize_text(query).lower()
    if not normalized:
        return False
    if any(term in normalized for term in _HISTORY_QUERY_TERMS):
        return True

    tokens = normalized.split()
    for idx, token in enumerate(tokens):
        if token.endswith("s") and token[:-1].isdigit() and len(token[:-1]) >= 3:
            return True
        if token.isdigit() and idx + 1 < len(tokens) and tokens[idx + 1] == "century":
            return True
    return False


def _replace_recent_years(query: str, current_year: int) -> str:
    chars = list(query)
    result: list[str] = []
    idx = 0
    length = len(chars)
    while idx < length:
        if (
            idx + 4 <= length
            and "".join(chars[idx : idx + 4]).isdigit()
            and (idx == 0 or not chars[idx - 1].isalnum())
            and (idx + 4 == length or not chars[idx + 4].isalnum())
        ):
            year_text = "".join(chars[idx : idx + 4])
            year_value = int(year_text)
            if year_value != current_year and 2000 <= year_value <= current_year + 1:
                result.append(str(current_year))
                idx += 4
                continue
        result.append(chars[idx])
        idx += 1
    return "".join(result)


def _correct_query_year(query: str) -> str:
    if not query or _looks_historical_query(query):
        return query
    try:
        current_year = datetime.now(settings.tz).year
    except Exception:
        current_year = datetime.now(timezone.utc).year
    return _replace_recent_years(query, current_year)


def _conv_id(context: "ExecutionContext | None") -> int:
    if context is None or context.conversation_id is None:
        return 0
    return int(context.conversation_id)


def _backend_cache_key(
    *,
    backend_key: str,
    query: str,
    strategy: str | None,
    runtime_provider_label: str | None,
    runtime_model_code: str | None,
    locale: str | None,
    max_results: int,
    context: "ExecutionContext | None",
) -> tuple[int, str, str, str, str, str, str, int]:
    return (
        _conv_id(context),
        backend_key,
        _normalize_text(query).lower(),
        str(strategy or "").strip().lower(),
        str(runtime_provider_label or "").strip().lower(),
        str(runtime_model_code or "").strip().lower(),
        str(locale or ""),
        int(max_results),
    )


def _record_backend_outcome(conv_id: int, backend_key: str, status: str) -> None:
    key = (conv_id, backend_key)
    if status in {STATUS_SUCCESS, STATUS_NO_RESULTS}:
        _BACKEND_FAIL_STREAK.pop(key, None)
        if conv_id:
            _BACKEND_DISABLED.setdefault(conv_id, set()).discard(backend_key)
        return
    _BACKEND_FAIL_STREAK[key] = _BACKEND_FAIL_STREAK.get(key, 0) + 1
    if conv_id and _BACKEND_FAIL_STREAK[key] >= 2:
        _BACKEND_DISABLED.setdefault(conv_id, set()).add(backend_key)
        logger.info(
            "web_search backend cooling down: backend={} conv_id={} streak={}",
            backend_key,
            conv_id,
            _BACKEND_FAIL_STREAK[key],
        )


def _backend_is_disabled(conv_id: int, backend_key: str) -> bool:
    return bool(conv_id) and backend_key in _BACKEND_DISABLED.get(conv_id, set())


def _make_items(
    *,
    provider: str,
    backend_key: str,
    raw_results: list[dict[str, str]],
) -> list[SearchResultItem]:
    items: list[SearchResultItem] = []
    for index, result in enumerate(raw_results, start=1):
        items.append(
            SearchResultItem(
                title=str(result.get("title") or ""),
                url=str(result.get("url") or ""),
                snippet=str(result.get("snippet") or ""),
                source=backend_key,
                provider=provider,
                provider_mode=PROVIDER_MODE_PUBLIC,
                rank=index,
            )
        )
    return items


async def _search_with_baidu_public(
    query: str,
    max_results: int,
    *,
    timeout_seconds: int,
) -> _HtmlSearchAttempt:
    import httpx

    backend_key = "public:baidu"
    try:
        timeout = httpx.Timeout(float(timeout_seconds), connect=min(10.0, float(timeout_seconds)))
        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True,
            headers=_DEFAULT_WEB_HEADERS,
        ) as client:
            resp = await client.get(
                "https://www.baidu.com/s",
                params={"wd": query},
            )
        if resp.status_code >= 400:
            return _HtmlSearchAttempt(
                backend_key=backend_key,
                status=STATUS_UPSTREAM_ERROR,
                items=[],
                error=f"HTTP {resp.status_code}",
            )

        status = _classify_baidu_public_html(resp.text)
        if status == STATUS_SUCCESS:
            results = _extract_baidu_public_results(resp.text, max_results)
            filtered_results = _filter_low_confidence_results(query, results)
            if filtered_results:
                return _HtmlSearchAttempt(
                    backend_key=backend_key,
                    status=status,
                    items=_make_items(
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
    except httpx.TimeoutException:
        return _HtmlSearchAttempt(
            backend_key=backend_key,
            status=STATUS_TIMEOUT,
            items=[],
            error="timeout",
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Baidu public search failed: {}", exc)
        return _HtmlSearchAttempt(
            backend_key=backend_key,
            status=STATUS_UPSTREAM_ERROR,
            items=[],
            error=str(exc),
        )


async def _search_with_so360_public(
    query: str,
    max_results: int,
    *,
    timeout_seconds: int,
) -> _HtmlSearchAttempt:
    import httpx

    backend_key = "public:so360"
    try:
        timeout = httpx.Timeout(float(timeout_seconds), connect=min(10.0, float(timeout_seconds)))
        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True,
            headers=_DEFAULT_WEB_HEADERS,
        ) as client:
            resp = await client.get(
                "https://www.so.com/s",
                params={"q": query},
            )
        if resp.status_code >= 400:
            return _HtmlSearchAttempt(
                backend_key=backend_key,
                status=STATUS_UPSTREAM_ERROR,
                items=[],
                error=f"HTTP {resp.status_code}",
            )

        status = _classify_so360_public_html(resp.text)
        if status == STATUS_SUCCESS:
            results = _extract_so360_public_results(resp.text, max_results)
            filtered_results = _filter_low_confidence_results(query, results)
            if filtered_results:
                return _HtmlSearchAttempt(
                    backend_key=backend_key,
                    status=status,
                    items=_make_items(
                        provider="so360_public",
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
    except httpx.TimeoutException:
        return _HtmlSearchAttempt(
            backend_key=backend_key,
            status=STATUS_TIMEOUT,
            items=[],
            error="timeout",
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("360 public search failed: {}", exc)
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
            if item in {PUBLIC_PROVIDER_BAIDU, PUBLIC_PROVIDER_SO360}
        ]
        if not self.providers:
            self.providers = [PUBLIC_PROVIDER_BAIDU, PUBLIC_PROVIDER_SO360]

    async def search(
        self,
        *,
        query: str,
        max_results: int,
        locale: str | None,
        timeout_seconds: int,
        context: "ExecutionContext | None" = None,
        strategy: str | None = None,
        runtime_provider_label: str | None = None,
        runtime_model_code: str | None = None,
    ) -> SearchProviderRun:
        start = time.perf_counter()
        rewritten_query = _normalize_text(_correct_query_year(query))
        conv_id = _conv_id(context)
        attempts: list[_HtmlSearchAttempt] = []
        attempted_backends: list[str] = []

        provider_map: dict[str, Callable[..., Any]] = {
            PUBLIC_PROVIDER_BAIDU: _search_with_baidu_public,
            PUBLIC_PROVIDER_SO360: _search_with_so360_public,
        }

        for provider_name in self.providers:
            backend_key = f"public:{provider_name}"
            cache_key = _backend_cache_key(
                backend_key=backend_key,
                query=rewritten_query,
                strategy=strategy,
                runtime_provider_label=runtime_provider_label,
                runtime_model_code=runtime_model_code,
                locale=locale,
                max_results=max_results,
                context=context,
            )
            if cache_key in _BACKEND_QUERY_CACHE:
                cached = _BACKEND_QUERY_CACHE[cache_key]
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

            if _backend_is_disabled(conv_id, backend_key):
                logger.info(
                    "web_search skip cooled-down public backend={} conv_id={} query={}",
                    backend_key,
                    conv_id,
                    rewritten_query[:80],
                )
                continue

            attempted_backends.append(backend_key)
            search_func = provider_map[provider_name]
            attempt = await search_func(
                rewritten_query,
                max_results,
                timeout_seconds=timeout_seconds,
            )
            attempts.append(attempt)
            _record_backend_outcome(conv_id, backend_key, attempt.status)
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
                _BACKEND_QUERY_CACHE[cache_key] = result
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
    "PUBLIC_PROVIDER_SO360",
    "PublicHtmlSearchProvider",
    "_extract_baidu_public_results",
    "_extract_so360_public_results",
    "_search_with_baidu_public",
    "_search_with_so360_public",
]
