"""
Public HTML parsing and formatting helpers. / 公共 HTML 解析与清洗支持。
"""

from __future__ import annotations

from app.ai.web_search.types import (
    PROVIDER_MODE_PUBLIC,
    STATUS_NO_RESULTS,
    STATUS_PARSE_ERROR,
    STATUS_POLICY_FILTERED,
    STATUS_SUCCESS,
    STATUS_UPSTREAM_ERROR,
    SearchResultItem,
)


def normalize_text(text: str) -> str:
    return " ".join((text or "").split())


def clean_search_snippet(text: str, title: str) -> str:
    normalized = normalize_text(text)
    normalized_title = normalize_text(title)
    if normalized_title and normalized.startswith(normalized_title):
        normalized = normalize_text(normalized[len(normalized_title) :])
    return normalized


def extract_baidu_public_results(html: str, max_results: int) -> list[dict[str, str]]:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "lxml")
    results: list[dict[str, str]] = []
    seen_urls: set[str] = set()

    for container in soup.select("div.result.c-container, div.c-container"):
        title_link = container.select_one("h3 a")
        if title_link is None:
            continue

        href = (title_link.get("href") or "").strip()
        title = normalize_text(title_link.get_text(" ", strip=True))
        if not href or not title or href in seen_urls:
            continue

        snippet = clean_search_snippet(
            container.get_text(" ", strip=True),
            title,
        )
        results.append({"title": title, "url": href, "snippet": snippet})
        seen_urls.add(href)
        if len(results) >= max_results:
            break

    return results


def extract_so360_public_results(html: str, max_results: int) -> list[dict[str, str]]:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "lxml")
    results: list[dict[str, str]] = []
    seen_urls: set[str] = set()

    for container in soup.select("li.res-list, div.res-list"):
        title_link = container.select_one("h3.res-title a, a")
        if title_link is None:
            continue

        href = (title_link.get("href") or "").strip()
        title = normalize_text(title_link.get_text(" ", strip=True))
        if not href or not title or href in seen_urls:
            continue

        snippet = clean_search_snippet(
            container.get_text(" ", strip=True),
            title,
        )
        results.append({"title": title, "url": href, "snippet": snippet})
        seen_urls.add(href)
        if len(results) >= max_results:
            break

    return results


def extract_title_from_html(html: str) -> str:
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
    return normalize_text((html or "")[start + 1 : end])


def html_may_contain_search_results(html: str) -> bool:
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


def classify_baidu_public_html(html: str) -> str:
    if not html:
        return STATUS_UPSTREAM_ERROR
    if "百度安全验证" in html or "安全验证" in extract_title_from_html(html):
        return STATUS_POLICY_FILTERED
    if extract_baidu_public_results(html, 1):
        return STATUS_SUCCESS
    if (
        "抱歉，没有找到与" in html
        or "没有找到该URL" in html
        or "未找到相关结果" in html
    ):
        return STATUS_NO_RESULTS
    if html_may_contain_search_results(html):
        return STATUS_PARSE_ERROR
    return STATUS_UPSTREAM_ERROR


def make_items(
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


__all__ = [
    "classify_baidu_public_html",
    "clean_search_snippet",
    "extract_baidu_public_results",
    "extract_so360_public_results",
    "extract_title_from_html",
    "html_may_contain_search_results",
    "make_items",
    "normalize_text",
]
