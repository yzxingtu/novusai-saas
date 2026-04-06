"""
Builtin Tool Executor / 内置工具执行器

Provides safe built-in functions (datetime, math, etc.) without external calls.
提供安全的内置函数（datetime、math 等），不涉及外部调用。
"""

import ast
import json
import operator
import time
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

from app.ai.tools.executors.base import BaseToolExecutor
from app.ai.tools.types import ToolDefinition, ToolResult
from app.ai.web_search.orchestrator import run_web_search as orchestrated_run_web_search
from app.ai.web_search.types import (
    STATUS_NO_RESULTS as WS_STATUS_NO_RESULTS,
    STATUS_SUCCESS as WS_STATUS_SUCCESS,
    WebSearchExecution as OrchestratedWebSearchExecution,
)
from app.core.config import settings
from app.core.i18n import _
from app.core.logging import LogManager
from app.core.response import build_public_error_text

if TYPE_CHECKING:
    from app.ai.tools.types import ExecutionContext

logger = LogManager.get_logger("ai.tool.builtin")

# Built-in function type / 内置函数类型
BuiltinFunc = Callable[..., Coroutine[Any, Any, str]]


# SSRF protection: block access to intranet/cloud metadata hostnames
# SSRF 防护：阻止访问内网/云元数据的主机名
_SSRF_BLOCKED_HOSTS = frozenset(
    {
        "localhost",
        "127.0.0.1",
        "0.0.0.0",
        "::1",
        "169.254.169.254",
        "metadata.google.internal",
        "metadata.google",
        "100.100.100.200",
    }
)
# Private IP range prefixes (quick check, not exact CIDR)
# 内网 IP 段前缀（快速检查，非精确 CIDR）
_SSRF_PRIVATE_PREFIXES = (
    "10.",
    "172.16.",
    "172.17.",
    "172.18.",
    "172.19.",
    "172.20.",
    "172.21.",
    "172.22.",
    "172.23.",
    "172.24.",
    "172.25.",
    "172.26.",
    "172.27.",
    "172.28.",
    "172.29.",
    "172.30.",
    "172.31.",
    "192.168.",
    "fd",
    "fc",
)

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
_MAIN_CONTENT_SELECTORS = (
    "main",
    "article",
    "[role='main']",
    "#main",
    "#content",
    "#main-content",
    ".main-content",
    ".article-content",
    ".entry-content",
    ".post-content",
    ".markdown-body",
    ".docMainContainer",
    ".docs-body",
)
_TEXT_BLOCK_TAGS = (
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "p",
    "li",
    "blockquote",
    "pre",
    "td",
    "th",
)
_NOISE_TAGS = (
    "script",
    "style",
    "noscript",
    "template",
    "svg",
    "canvas",
    "iframe",
    "form",
    "button",
    "input",
    "select",
    "textarea",
    "nav",
    "footer",
    "header",
    "aside",
)
_NOISE_HINTS = (
    "breadcrumb",
    "cookie",
    "footer",
    "header",
    "menu",
    "nav",
    "navbar",
    "pagination",
    "share",
    "sidebar",
    "social",
    "subscribe",
    "table-of-contents",
    "toc",
    "toolbar",
)

_SEARCH_PROVIDER_BAIDU = "baidu_public"
_SEARCH_PROVIDER_SO360 = "so360_public"
_SEARCH_STATUS_SUCCESS = "success"
_SEARCH_STATUS_NO_RESULTS = "no_results"
_SEARCH_STATUS_SOURCE_BLOCKED = "source_blocked"
_SEARCH_STATUS_SOURCE_CHALLENGED = "source_challenged"
_SEARCH_STATUS_SOURCE_UNAVAILABLE = "source_unavailable"
_SEARCH_STATUS_PARSER_MISS = "parser_miss"
_SEARCH_STATUS_LOW_CONFIDENCE = "low_confidence"

_SEARCH_ENGINE_HOSTS = frozenset({"www.baidu.com", "baidu.com", "www.so.com", "so.com"})
_GENERIC_SITE_LABELS = frozenset(
    {"www", "com", "org", "net", "gov", "cn", "en", "html", "htm"}
)

# Minimum fraction of query tokens that must appear in title+snippet for a hit to count as relevant.
# 查询词在标题+摘要中的覆盖比例下限（不依赖固定主题词表）。
_QUERY_RELEVANCE_MIN_RATIO = 0.28

# Per-process conversation provider health (best-effort; resets on worker restart).
_PROVIDER_FAIL_STREAK: dict[tuple[int, str], int] = {}
_PROVIDER_DISABLED: dict[int, set[str]] = {}
# Dedup web_search by normalized query within a conversation.
_SEARCH_QUERY_CACHE: dict[tuple[int, str], str] = {}


@dataclass
class SearchProviderResponse:
    provider: str
    status: str
    results: list[dict[str, str]]
    error: str | None = None


@dataclass
class WebSearchExecution:
    output: str
    provider: str | None
    status: str
    items: list[dict[str, str]]
    failure_reason: str | None = None


def _normalize_text(text: str) -> str:
    """Collapse whitespace and trim text. / 折叠空白并裁剪文本。"""
    return " ".join((text or "").split())


def _truncate_text(text: str, max_length: int) -> tuple[str, bool]:
    """Truncate text at a readable boundary. / 在较自然的边界截断文本。"""
    if len(text) <= max_length:
        return text, False

    cut = text[:max_length].rstrip()
    breakpoints = [
        cut.rfind("\n\n"),
        cut.rfind(". "),
        cut.rfind("。"),
        cut.rfind("! "),
        cut.rfind("? "),
        cut.rfind("; "),
    ]
    last_break = max(breakpoints)
    if last_break >= max_length // 2:
        cut = cut[: last_break + 1].rstrip()
    return f"{cut}... [truncated]", True


def _clean_search_snippet(text: str, title: str) -> str:
    normalized = _normalize_text(text)
    normalized_title = _normalize_text(title)
    if normalized_title and normalized.startswith(normalized_title):
        normalized = _normalize_text(normalized[len(normalized_title) :])
    return normalized


def _extract_baidu_public_results(html: str, max_results: int) -> list[dict[str, str]]:
    """Parse Baidu public search result page. / 解析百度公共搜索结果页。"""
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
    """Parse 360 public search result page. / 解析 360 公共搜索结果页。"""
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


def _build_search_output_text(
    query: str,
    results: list[dict[str, str]],
) -> str:
    """Format search results for tool output. / 格式化搜索结果输出。"""
    lines = [f"Search results for: {query}\n"]
    any_redirect = any(
        _search_engine_redirect_note(item.get("url") or "") for item in results
    )
    if any_redirect:
        lines.append(
            "Note: Some URLs below are search-engine redirect links; use fetch_url to load "
            "the final page content (redirects are followed automatically).\n"
        )
    for i, item in enumerate(results, 1):
        lines.append(f"{i}. {item['title']}")
        lines.append(f"   URL: {item['url']}")
        if item["snippet"]:
            lines.append(f"   {item['snippet']}")
        lines.append("")
    return "\n".join(lines)


def _build_search_summary_payload(
    execution: OrchestratedWebSearchExecution,
) -> dict[str, Any]:
    items = [
        item.to_summary_item() if hasattr(item, "to_summary_item") else dict(item)
        for item in execution.items
    ]
    meta = execution.meta
    payload: dict[str, Any] = {
        "provider": meta.provider,
        "provider_mode": meta.provider_mode,
        "provider_chain": list(meta.provider_chain or []),
        "attempted_backends": list(meta.attempted_backends or []),
        "selected_backend": meta.selected_backend,
        "used_fallback": bool(meta.used_fallback),
        "status": meta.status,
        "result_count": len(items),
        "cache_hit": bool(meta.cache_hit),
        "items": items,
    }
    if meta.failure_reason:
        payload["failure_reason"] = meta.failure_reason
    return payload


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


def _query_tokens_for_relevance(query: str) -> set[str]:
    """Tokens from the query (site: host stripped) for overlap scoring — no fixed topic lexicon."""
    scrubbed = _strip_site_filters(query)
    return _scan_search_tokens(scrubbed.lower())


def _result_text_tokens(result: dict[str, str], *, include_url: bool) -> set[str]:
    parts = [str(result.get("title") or ""), str(result.get("snippet") or "")]
    if include_url:
        parts.append(str(result.get("url") or ""))
    hay = _normalize_text(" ".join(parts)).lower()
    return _scan_search_tokens(hay)


def _result_passes_relevance(query: str, result: dict[str, str]) -> bool:
    """
    True if query tokens overlap title+snippet (and URL if needed) enough — language-agnostic token Jaccard coverage.
    """
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


def _looks_historical_query(query: str) -> bool:
    normalized = _normalize_text(query).lower()
    if not normalized:
        return False
    if any(
        term in normalized for term in ("年代", "朝代", "古代", "战时", "世纪", "历史")
    ):
        return True

    tokens = normalized.split()
    for idx, token in enumerate(tokens):
        if token in {
            "history",
            "historical",
            "era",
            "ancient",
            "medieval",
            "wartime",
            "dynasty",
        }:
            return True
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
    """Replace stale calendar years in web_search queries unless the query is clearly historical."""
    if not query:
        return query
    if _looks_historical_query(query):
        return query
    try:
        current_year = datetime.now(settings.tz).year
    except Exception:
        current_year = datetime.now(timezone.utc).year
    return _replace_recent_years(query, current_year)


def _search_engine_redirect_note(url: str) -> bool:
    try:
        host = (urlparse(url).hostname or "").lower()
    except Exception:
        return False
    return (
        host in _SEARCH_ENGINE_HOSTS
        or host.endswith(".baidu.com")
        or host.endswith(".so.com")
    )


def _result_is_search_wrapper(url: str) -> bool:
    try:
        host = (urlparse(url).hostname or "").lower()
    except Exception:
        return False
    return host in _SEARCH_ENGINE_HOSTS


def _filter_low_confidence_results(
    query: str,
    results: list[dict[str, str]],
) -> list[dict[str, str]]:
    return [result for result in results if _result_passes_relevance(query, result)]


def _classify_baidu_public_html(html: str) -> str:
    if not html:
        return _SEARCH_STATUS_SOURCE_UNAVAILABLE
    if "百度安全验证" in html or "安全验证" in _extract_title_from_html(html):
        return _SEARCH_STATUS_SOURCE_CHALLENGED
    if _extract_baidu_public_results(html, 1):
        return _SEARCH_STATUS_SUCCESS
    if (
        "抱歉，没有找到与" in html
        or "没有找到该URL" in html
        or "未找到相关结果" in html
    ):
        return _SEARCH_STATUS_NO_RESULTS
    if _html_may_contain_search_results(html):
        return _SEARCH_STATUS_PARSER_MISS
    return _SEARCH_STATUS_SOURCE_UNAVAILABLE


def _classify_so360_public_html(html: str) -> str:
    if not html:
        return _SEARCH_STATUS_SOURCE_UNAVAILABLE
    title = _extract_title_from_html(html)
    normalized = _normalize_text(html)
    if "安全验证" in title or "请输入验证码" in normalized:
        return _SEARCH_STATUS_SOURCE_CHALLENGED
    if _extract_so360_public_results(html, 1):
        return _SEARCH_STATUS_SUCCESS
    if (
        "没有找到相关结果" in normalized
        or "相关结果约0个" in normalized
        or "未找到相关搜索结果" in normalized
        or "抱歉，未找到相关搜索结果" in normalized
    ):
        return _SEARCH_STATUS_NO_RESULTS
    if _html_may_contain_search_results(html):
        return _SEARCH_STATUS_PARSER_MISS
    return _SEARCH_STATUS_SOURCE_UNAVAILABLE


async def _search_with_baidu_public(
    query: str,
    max_results: int,
) -> SearchProviderResponse:
    import httpx

    try:
        timeout = httpx.Timeout(20.0, connect=10.0)
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
            return SearchProviderResponse(
                provider=_SEARCH_PROVIDER_BAIDU,
                status=_SEARCH_STATUS_SOURCE_BLOCKED,
                results=[],
                error=f"HTTP {resp.status_code}",
            )

        status = _classify_baidu_public_html(resp.text)
        if status == _SEARCH_STATUS_SUCCESS:
            results = _extract_baidu_public_results(resp.text, max_results)
            filtered_results = _filter_low_confidence_results(query, results)
            if filtered_results:
                return SearchProviderResponse(
                    provider=_SEARCH_PROVIDER_BAIDU,
                    status=status,
                    results=filtered_results,
                )
            return SearchProviderResponse(
                provider=_SEARCH_PROVIDER_BAIDU,
                status=_SEARCH_STATUS_LOW_CONFIDENCE,
                results=[],
                error="returned low-confidence results",
            )
        return SearchProviderResponse(
            provider=_SEARCH_PROVIDER_BAIDU,
            status=status,
            results=[],
            error=(
                "returned safety verification"
                if status == _SEARCH_STATUS_SOURCE_CHALLENGED
                else "returned no results"
                if status == _SEARCH_STATUS_NO_RESULTS
                else "result parser missed current page structure"
                if status == _SEARCH_STATUS_PARSER_MISS
                else "returned low-confidence results"
                if status == _SEARCH_STATUS_LOW_CONFIDENCE
                else "returned an unreadable page"
            ),
        )
    except httpx.TimeoutException:
        return SearchProviderResponse(
            provider=_SEARCH_PROVIDER_BAIDU,
            status=_SEARCH_STATUS_SOURCE_UNAVAILABLE,
            results=[],
            error="timeout",
        )
    except Exception as exc:
        logger.warning("Baidu public search failed: {}", exc)
        return SearchProviderResponse(
            provider=_SEARCH_PROVIDER_BAIDU,
            status=_SEARCH_STATUS_SOURCE_UNAVAILABLE,
            results=[],
            error=str(exc),
        )


async def _search_with_so360_public(
    query: str,
    max_results: int,
) -> SearchProviderResponse:
    import httpx

    try:
        timeout = httpx.Timeout(20.0, connect=10.0)
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
            return SearchProviderResponse(
                provider=_SEARCH_PROVIDER_SO360,
                status=_SEARCH_STATUS_SOURCE_BLOCKED,
                results=[],
                error=f"HTTP {resp.status_code}",
            )

        status = _classify_so360_public_html(resp.text)
        if status == _SEARCH_STATUS_SUCCESS:
            results = _extract_so360_public_results(resp.text, max_results)
            filtered_results = _filter_low_confidence_results(query, results)
            if filtered_results:
                return SearchProviderResponse(
                    provider=_SEARCH_PROVIDER_SO360,
                    status=status,
                    results=filtered_results,
                )
            return SearchProviderResponse(
                provider=_SEARCH_PROVIDER_SO360,
                status=_SEARCH_STATUS_LOW_CONFIDENCE,
                results=[],
                error="returned low-confidence results",
            )
        return SearchProviderResponse(
            provider=_SEARCH_PROVIDER_SO360,
            status=status,
            results=[],
            error=(
                "returned safety verification"
                if status == _SEARCH_STATUS_SOURCE_CHALLENGED
                else "returned no results"
                if status == _SEARCH_STATUS_NO_RESULTS
                else "result parser missed current page structure"
                if status == _SEARCH_STATUS_PARSER_MISS
                else "returned low-confidence results"
                if status == _SEARCH_STATUS_LOW_CONFIDENCE
                else "returned an unreadable page"
            ),
        )
    except httpx.TimeoutException:
        return SearchProviderResponse(
            provider=_SEARCH_PROVIDER_SO360,
            status=_SEARCH_STATUS_SOURCE_UNAVAILABLE,
            results=[],
            error="timeout",
        )
    except Exception as exc:
        logger.warning("360 public search failed: {}", exc)
        return SearchProviderResponse(
            provider=_SEARCH_PROVIDER_SO360,
            status=_SEARCH_STATUS_SOURCE_UNAVAILABLE,
            results=[],
            error=str(exc),
        )


def _build_public_search_failure_reason(
    attempts: list[SearchProviderResponse],
) -> str:
    parts: list[str] = []
    for attempt in attempts:
        detail = attempt.error or attempt.status
        if detail.startswith("returned ") or detail.startswith("HTTP "):
            parts.append(f"{attempt.provider} {detail}")
        else:
            parts.append(f"{attempt.provider} returned {detail}")
    return "; ".join(parts)


def _web_search_conv_id(context: "ExecutionContext | None") -> int:
    if context is None or context.conversation_id is None:
        return 0
    return int(context.conversation_id)


def _record_provider_outcome(conv_id: int, provider: str, status: str) -> None:
    key = (conv_id, provider)
    if status == _SEARCH_STATUS_SUCCESS:
        _PROVIDER_FAIL_STREAK.pop(key, None)
        if conv_id:
            _PROVIDER_DISABLED.setdefault(conv_id, set()).discard(provider)
        return
    if status in (
        _SEARCH_STATUS_SOURCE_CHALLENGED,
        _SEARCH_STATUS_SOURCE_UNAVAILABLE,
        _SEARCH_STATUS_SOURCE_BLOCKED,
    ):
        _PROVIDER_FAIL_STREAK[key] = _PROVIDER_FAIL_STREAK.get(key, 0) + 1
        if conv_id and _PROVIDER_FAIL_STREAK[key] >= 2:
            _PROVIDER_DISABLED.setdefault(conv_id, set()).add(provider)
            logger.info(
                "web_search provider cooling down: provider={} conv_id={} streak={}",
                provider,
                conv_id,
                _PROVIDER_FAIL_STREAK[key],
            )


def _provider_is_skipped(conv_id: int, provider: str) -> bool:
    return bool(conv_id) and provider in _PROVIDER_DISABLED.get(conv_id, set())


async def _run_web_search(
    query: str,
    max_results: int,
    *,
    context: "ExecutionContext | None" = None,
) -> OrchestratedWebSearchExecution:
    return await orchestrated_run_web_search(
        query,
        max_results,
        context=context,
    )


def _remove_noise_nodes(soup: Any) -> None:
    """Drop common non-content nodes. / 删除常见非正文节点。"""
    for tag in soup(_NOISE_TAGS):
        tag.decompose()

    for node in soup.find_all(True):
        if not isinstance(getattr(node, "attrs", None), dict):
            continue

        if node.has_attr("hidden") or node.get("aria-hidden") == "true":
            node.decompose()
            continue

        style = (node.get("style") or "").lower()
        if "display:none" in style or "visibility:hidden" in style:
            node.decompose()
            continue

        if node.name not in {"div", "section", "ul", "ol"}:
            continue

        hints = " ".join(
            [
                node.get("id", ""),
                " ".join(node.get("class", [])),
            ]
        ).lower()
        if hints and any(noise in hints for noise in _NOISE_HINTS):
            node.decompose()


def _score_content_node(node: Any) -> int:
    """Rough heuristic for selecting the main content container. / 粗略评分主内容容器。"""
    paragraph_texts = [
        _normalize_text(item.get_text(" ", strip=True))
        for item in node.find_all(["p", "li"], limit=80)
    ]
    paragraph_chars = sum(len(text) for text in paragraph_texts if text)
    heading_count = len(node.find_all(["h1", "h2", "h3"], limit=16))
    link_chars = sum(
        len(_normalize_text(link.get_text(" ", strip=True)))
        for link in node.find_all("a", limit=120)
    )
    total_text = len(_normalize_text(node.get_text(" ", strip=True)))
    return (
        paragraph_chars
        + (heading_count * 40)
        + min(total_text, 1600)
        - (link_chars // 3)
    )


def _pick_main_content_node(soup: Any) -> Any:
    """Pick the most likely main-content node. / 选择最可能的正文节点。"""
    body = soup.find("body") or soup

    for selector in _MAIN_CONTENT_SELECTORS:
        node = body.select_one(selector)
        if node is not None and _score_content_node(node) >= 200:
            return node

    best_node = body
    best_score = _score_content_node(body)
    for node in body.find_all(["article", "main", "section", "div"], limit=240):
        score = _score_content_node(node)
        if score > best_score:
            best_node = node
            best_score = score

    return best_node


def _collect_text_blocks(node: Any, *, max_blocks: int = 120) -> list[str]:
    """Extract readable text blocks from an HTML node. / 从 HTML 节点提取可读文本块。"""
    blocks: list[str] = []
    seen: set[str] = set()

    for element in node.find_all(_TEXT_BLOCK_TAGS):
        text = _normalize_text(element.get_text(" ", strip=True))
        if not text or len(text) < 3 or text in seen:
            continue

        # Skip menus or one-word chrome fragments that still slip through.
        if element.name in {"li", "td", "th"} and len(text) < 8:
            continue

        blocks.append(text)
        seen.add(text)
        if len(blocks) >= max_blocks:
            break

    if not blocks:
        fallback = _normalize_text(node.get_text("\n", strip=True))
        if fallback:
            blocks.append(fallback)

    return blocks


def _extract_meta_description(soup: Any) -> str:
    """Read meta description / 提取 meta description。"""
    for attrs in (
        {"name": "description"},
        {"property": "og:description"},
        {"name": "twitter:description"},
    ):
        tag = soup.find("meta", attrs=attrs)
        content = _normalize_text(tag.get("content", "")) if tag else ""
        if content:
            return content
    return ""


def _extract_readable_page(html: str) -> dict[str, Any]:
    """Extract title, headings and main body from HTML. / 从 HTML 提取标题、要点标题与正文。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "lxml")
    _remove_noise_nodes(soup)

    title = ""
    if soup.title and soup.title.string:
        title = _normalize_text(soup.title.string)

    description = _extract_meta_description(soup)
    content_node = _pick_main_content_node(soup)
    headings: list[str] = []
    if content_node is not None:
        for heading in content_node.find_all(["h1", "h2", "h3"], limit=8):
            text = _normalize_text(heading.get_text(" ", strip=True))
            if text and text not in headings:
                headings.append(text)

    blocks = _collect_text_blocks(content_node)
    if title and blocks and blocks[0].lower() == title.lower():
        blocks = blocks[1:]
    body = "\n".join(blocks).strip()

    return {
        "title": title,
        "description": description,
        "headings": headings,
        "body": body,
    }


def _format_html_fetch_output(
    *,
    requested_url: str,
    final_url: str,
    page: dict[str, Any],
    max_length: int,
) -> str:
    """Format extracted page content for tool output. / 格式化页面提取结果。"""
    lines = [f"Content from {final_url}"]
    if final_url != requested_url:
        lines.append(f"Redirected from: {requested_url}")
    if page.get("title"):
        lines.append(f"Title: {page['title']}")
    if page.get("description"):
        lines.append(f"Description: {page['description']}")
    if page.get("headings"):
        lines.append(f"Key sections: {', '.join(page['headings'][:6])}")

    prefix = "\n".join(lines).strip()
    body = page.get("body", "") or ""
    if not body:
        return (
            f"Error: No readable main content found at {final_url}. "
            "The page may require JavaScript or block automated reading."
        )

    remaining = max(max_length - len(prefix) - 2, 200)
    excerpt, _ = _truncate_text(body, remaining)
    return f"{prefix}\n\n{excerpt}"


def _is_ssrf_blocked(url: str) -> str | None:
    """Check if URL points to intranet/cloud metadata, return error message or None. / 检查 URL 是否指向内网/云元数据，返回错误消息或 None。"""
    try:
        from urllib.parse import urlparse

        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
        if not host:
            return "Invalid URL: no hostname"
        if host in _SSRF_BLOCKED_HOSTS:
            return f"Blocked: requests to {host} are not allowed"
        if host.startswith(_SSRF_PRIVATE_PREFIXES):
            return f"Blocked: requests to private network ({host}) are not allowed"
        # Block non-HTTP(S) protocols / 阻止非 HTTP(S) 协议
        if parsed.scheme not in ("http", "https"):
            return f"Blocked: only http/https URLs are allowed, got {parsed.scheme}"
    except Exception:
        return "Invalid URL"
    return None


class BuiltinToolExecutor(BaseToolExecutor):
    """
    Built-in function tool executor. / 内置函数工具执行器。

    Maintains a safe function registry; all functions execute in-process.
    Any IO operations and dangerous calls are forbidden.
    维护一个安全函数注册表，所有函数在进程内执行。
    禁止任何 IO 操作和危险调用。
    """

    def __init__(self) -> None:
        self._functions: dict[str, BuiltinFunc] = {}
        self._register_defaults()

    def register_function(self, name: str, func: BuiltinFunc) -> None:
        """Register a built-in function / 注册一个内置函数"""
        self._functions[name] = func

    async def execute(
        self,
        definition: ToolDefinition,
        tool_call_id: str,
        arguments: dict[str, Any],
        context: "ExecutionContext | None" = None,
    ) -> ToolResult:
        """Execute a built-in function / 执行内置函数"""
        _ = context
        start = time.perf_counter()
        func_name = definition.name

        func = self._functions.get(func_name)
        if not func:
            return ToolResult(
                tool_call_id=tool_call_id,
                name=func_name,
                success=False,
                error=_("tool.builtin.not_found", name=func_name),
            )

        try:
            if func_name == "web_search":
                query = str(arguments.get("query") or "")
                max_results = int(arguments.get("max_results") or 5)
                execution = await _run_web_search(
                    query,
                    max_results,
                    context=context,
                )
                duration_ms = int((time.perf_counter() - start) * 1000)
                is_failure = execution.meta.status not in {
                    WS_STATUS_SUCCESS,
                    WS_STATUS_NO_RESULTS,
                }
                return ToolResult(
                    tool_call_id=tool_call_id,
                    name=func_name,
                    success=not is_failure,
                    output="" if is_failure else execution.output,
                    error=execution.output if is_failure else "",
                    summary=(
                        f"{execution.meta.provider or execution.meta.selected_backend or 'search'}: {len(execution.items)} result(s)"
                        if execution.meta.status in {WS_STATUS_SUCCESS, WS_STATUS_NO_RESULTS}
                        else execution.meta.failure_reason
                    ),
                    summary_payload=_build_search_summary_payload(execution),
                    duration_ms=duration_ms,
                )

            if func_name == "fetch_url":
                url = str(arguments.get("url") or "")
                max_length = int(arguments.get("max_length") or 5000)
                ok, payload = await BuiltinToolExecutor._fetch_url_result(
                    url, max_length
                )
                duration_ms = int((time.perf_counter() - start) * 1000)
                if not ok:
                    return ToolResult(
                        tool_call_id=tool_call_id,
                        name=func_name,
                        success=False,
                        error=payload,
                        summary="fetch_url failed",
                        summary_payload={"fetch_url": True, "ok": False},
                        duration_ms=duration_ms,
                    )
                return ToolResult(
                    tool_call_id=tool_call_id,
                    name=func_name,
                    success=True,
                    output=payload,
                    duration_ms=duration_ms,
                )

            output = await func(**arguments)
            duration_ms = int((time.perf_counter() - start) * 1000)

            return ToolResult(
                tool_call_id=tool_call_id,
                name=func_name,
                success=True,
                output=output,
                duration_ms=duration_ms,
            )

        except Exception as exc:
            duration_ms = int((time.perf_counter() - start) * 1000)
            logger.error(
                "Builtin tool error: {}: {}",
                func_name,
                str(exc),
                exc_info=True,
            )
            return ToolResult(
                tool_call_id=tool_call_id,
                name=func_name,
                success=False,
                error=build_public_error_text(
                    message="Builtin tool execution failed",
                    exc=exc,
                ),
                duration_ms=duration_ms,
            )

    async def validate(
        self,
        definition: ToolDefinition,
        arguments: dict[str, Any],
    ) -> bool:
        """Validate built-in function arguments / 校验内置函数参数"""
        func_name = definition.name
        if func_name not in self._functions:
            return False

        # Check required parameters / 检查必填参数
        for param in definition.parameters:
            if param.required and param.name not in arguments:
                return False

        return True

    # ========================================
    # Default built-in functions / 默认内置函数
    # ========================================

    def _register_defaults(self) -> None:
        """Register default built-in functions / 注册默认内置函数"""
        self.register_function("get_current_time", self._get_current_time)
        self.register_function("calculate", self._calculate)
        self.register_function("format_json", self._format_json)
        self.register_function("web_search", self._web_search)
        self.register_function("fetch_url", self._fetch_url)

    @staticmethod
    async def _get_current_time(
        timezone_name: str = settings.TIMEZONE,
        format: str = "%Y-%m-%d %H:%M:%S",
    ) -> str:
        """Get current time / 获取当前时间"""
        import zoneinfo

        try:
            tz = zoneinfo.ZoneInfo(timezone_name)
        except (KeyError, Exception):
            tz = timezone.utc

        now = datetime.now(tz)
        return now.strftime(format)

    @staticmethod
    async def _calculate(expression: str = "") -> str:
        """
        Safe mathematical calculation. / 安全的数学计算。

        Uses an AST parser, only allowing numeric constants and basic arithmetic operators.
        Function calls, attribute access, imports, or any other code execution are forbidden.
        使用 AST 解析器，仅允许数字常量和基本算术运算符。
        禁止函数调用、属性访问、导入或任何其他代码执行。
        """
        if not expression:
            return _("tool.builtin.empty_expression")

        try:
            result = _safe_eval_math(expression)
            return str(result)
        except (ValueError, SyntaxError, TypeError, ZeroDivisionError) as exc:
            return _("tool.builtin.calc_error").format(error=str(exc))

    @staticmethod
    async def _format_json(data: str = "") -> str:
        """Format JSON string / 格式化 JSON 字符串"""
        try:
            parsed = json.loads(data)
            return json.dumps(parsed, indent=2, ensure_ascii=False)
        except json.JSONDecodeError as exc:
            return f"Error: Invalid JSON - {exc}"

    @staticmethod
    async def _web_search(query: str = "", max_results: int = 5) -> str:
        """
        Web search: automatically choose a search source and return web results. / 联网搜索：自动选择搜索源并返回网页结果。

        Returns a list of search results (title + snippet + link).
        返回搜索结果列表（标题 + 摘要 + 链接）。
        """
        if not query:
            return "Error: query parameter is required"

        max_results = min(max(1, max_results), 10)
        return (await _run_web_search(query, max_results)).output

    @staticmethod
    async def _fetch_url_result(
        url: str = "", max_length: int = 5000
    ) -> tuple[bool, str]:
        """
        Fetch URL; returns (success, text).
        On failure, text is the error detail for ToolResult.error (no \"Error:\" prefix).
        """
        if not url:
            return False, "url parameter is required"

        ssrf_err = _is_ssrf_blocked(url)
        if ssrf_err:
            return False, ssrf_err

        import httpx

        max_length = min(max(500, max_length), 20000)
        hint = (
            " This page may block automated access; try another candidate URL from "
            "search results with fetch_url."
        )
        hint_zh = (
            " 该页面可能被站点拦截，请从搜索结果中换其他候选 URL 后用 fetch_url 重试。"
        )

        try:
            timeout = httpx.Timeout(20.0, connect=10.0)
            async with httpx.AsyncClient(
                timeout=timeout,
                follow_redirects=True,
                headers=_DEFAULT_WEB_HEADERS,
            ) as client:
                resp = await client.get(url)

            final_url = str(resp.url)
            content_type = (resp.headers.get("content-type") or "").lower()
            raw_text = resp.text or ""

            if resp.status_code >= 400:
                page = _extract_readable_page(raw_text) if raw_text else {}
                title = page.get("title") if page else ""
                message = f"HTTP {resp.status_code} while fetching {final_url}"
                if title:
                    message += f" (title: {title})"
                if resp.status_code in (401, 403, 429):
                    message += hint + hint_zh
                return False, message

            if "html" in content_type or "<html" in raw_text[:1000].lower():
                page = _extract_readable_page(raw_text)
                formatted = _format_html_fetch_output(
                    requested_url=url,
                    final_url=final_url,
                    page=page,
                    max_length=max_length,
                )
                if formatted.strip().startswith("Error:"):
                    return False, formatted.strip()[len("Error:") :].strip() + hint_zh
                return True, formatted

            text, _ = _truncate_text(_normalize_text(raw_text), max_length)
            if text:
                return True, f"Content from {final_url}:\n\n{text}"
            return False, f"No readable content found at {final_url}"

        except httpx.TimeoutException:
            return False, f"Request timed out for URL: {url}"
        except httpx.HTTPError as exc:
            logger.warning("fetch_url request error for {}: {}", url, exc)
            return False, f"Failed to fetch URL - {exc}"
        except Exception as exc:
            logger.warning("fetch_url failed for {}: {}", url, exc)
            return False, f"Failed to fetch URL - {exc}"

    @staticmethod
    async def _fetch_url(url: str = "", max_length: int = 5000) -> str:
        """
        Fetch web content (legacy string API for tests). / 抓取网页内容。
        """
        ok, text = await BuiltinToolExecutor._fetch_url_result(url, max_length)
        if ok:
            return text
        return f"Error: {text}"


# ========================================
# Safe Math Expression Parser / 安全数学表达式解析器
# ========================================

# Allowed binary operators / 允许的二元运算符
_SAFE_BINOPS: dict[type, Callable[..., object]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}

# Allowed unary operators / 允许的一元运算符
_SAFE_UNARYOPS: dict[type, Callable[..., object]] = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


def _safe_eval_node(node: ast.AST) -> int | float:
    """递归求值 AST 节点，仅允许安全的数学操作 / Recursively evaluate AST node, only allowing safe math operations."""
    if isinstance(node, ast.Expression):
        return _safe_eval_node(node.body)

    if (
        isinstance(node, ast.Constant)
        and isinstance(node.value, (int, float))
        and not isinstance(node.value, bool)
    ):
        return node.value

    if isinstance(node, ast.BinOp):
        op_func = _SAFE_BINOPS.get(type(node.op))
        if op_func is None:
            raise ValueError(f"Unsupported operator: {type(node.op).__name__}")
        left = _safe_eval_node(node.left)
        right = _safe_eval_node(node.right)
        # Prevent astronomical exponents (e.g. 10**10000) / 防止天文数字指数 (如 10**10000)
        if (
            isinstance(node.op, ast.Pow)
            and isinstance(right, (int, float))
            and abs(right) > 1000
        ):
            raise ValueError("Exponent too large (max 1000)")
        return op_func(left, right)

    if isinstance(node, ast.UnaryOp):
        op_func = _SAFE_UNARYOPS.get(type(node.op))
        if op_func is None:
            raise ValueError(f"Unsupported unary operator: {type(node.op).__name__}")
        return op_func(_safe_eval_node(node.operand))

    raise ValueError(
        f"Unsupported expression type: {type(node).__name__}. "
        "Only numbers and arithmetic operators (+, -, *, /, //, %, **) are allowed."
    )


def _safe_eval_math(expression: str) -> int | float:
    """Safely evaluate a math expression.
    安全地求值数学表达式。

    Uses ast.parse to parse the expression into an AST, then recursively evaluates it.
    Only numeric constants and basic arithmetic operators are allowed; any function calls,
    attribute access, variable references, or other code execution are forbidden.
    使用 ast.parse 将表达式解析为 AST，然后递归求值。
    仅允许数字常量和基本算术运算符，禁止任何函数调用、
    属性访问、变量引用或其他代码执行。

    Raises:
        ValueError: Expression contains unsafe operations / 表达式包含不安全的操作
        SyntaxError: Expression syntax error / 表达式语法错误
        ZeroDivisionError: Division by zero / 除零错误
    """
    tree = ast.parse(expression.strip(), mode="eval")
    return _safe_eval_node(tree)


__all__ = ["BuiltinToolExecutor"]
