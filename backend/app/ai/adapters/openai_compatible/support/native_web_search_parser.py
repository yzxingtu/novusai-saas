"""Payload parsers for native Responses web search results."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

from app.ai.web_search.types import (
    PROVIDER_MODE_NATIVE,
    SearchResultItem,
)


def native_web_search_field(value: Any, name: str) -> Any:
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def coerce_int(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def is_verifiable_native_web_search_url(url: str) -> bool:
    parsed = urlparse(str(url or "").strip())
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def normalize_native_web_search_snippet(
    text: str,
    *,
    title: str,
    start_index: int | None,
    end_index: int | None,
    limit: int = 240,
) -> str:
    source_text = str(text or "")
    if start_index is not None and end_index is not None and end_index > start_index:
        left = max(0, start_index - 100)
        right = min(len(source_text), end_index + 120)
        source_text = source_text[left:right]
    normalized = " ".join(source_text.split())
    normalized_title = " ".join(str(title or "").split())
    if normalized_title and normalized.startswith(normalized_title):
        normalized = normalized[len(normalized_title) :].strip(" -:;,")
    if len(normalized) > limit:
        normalized = normalized[:limit].rstrip() + "..."
    return normalized


def extract_native_web_search_items(
    response: Any,
    *,
    provider_label: str,
    backend_key: str,
    max_results: int,
) -> tuple[list[SearchResultItem], bool]:
    items: list[SearchResultItem] = []
    seen_urls: set[str] = set()
    saw_unverifiable_url = False

    for item in native_web_search_field(response, "output") or []:
        if native_web_search_field(item, "type") != "message":
            continue
        for content in native_web_search_field(item, "content") or []:
            if native_web_search_field(content, "type") != "output_text":
                continue
            text = str(native_web_search_field(content, "text") or "")
            for annotation in native_web_search_field(content, "annotations") or []:
                if native_web_search_field(annotation, "type") != "url_citation":
                    continue
                url = str(native_web_search_field(annotation, "url") or "").strip()
                if not is_verifiable_native_web_search_url(url):
                    saw_unverifiable_url = True
                    continue
                if url in seen_urls:
                    continue
                title = (
                    str(native_web_search_field(annotation, "title") or "").strip()
                    or url
                )
                items.append(
                    SearchResultItem(
                        title=title,
                        url=url,
                        snippet=normalize_native_web_search_snippet(
                            text,
                            title=title,
                            start_index=coerce_int(
                                native_web_search_field(annotation, "start_index")
                            ),
                            end_index=coerce_int(
                                native_web_search_field(annotation, "end_index")
                            ),
                        ),
                        source=backend_key,
                        provider=provider_label,
                        provider_mode=PROVIDER_MODE_NATIVE,
                        rank=len(items) + 1,
                    )
                )
                seen_urls.add(url)
                if len(items) >= max_results:
                    return items, saw_unverifiable_url

    for item in native_web_search_field(response, "output") or []:
        if native_web_search_field(item, "type") != "web_search_call":
            continue
        action = native_web_search_field(item, "action")
        for source in native_web_search_field(action, "sources") or []:
            url = str(native_web_search_field(source, "url") or "").strip()
            if not is_verifiable_native_web_search_url(url):
                saw_unverifiable_url = True
                continue
            if url in seen_urls:
                continue
            items.append(
                SearchResultItem(
                    title=(urlparse(url).netloc or url).strip(),
                    url=url,
                    snippet="",
                    source=backend_key,
                    provider=provider_label,
                    provider_mode=PROVIDER_MODE_NATIVE,
                    rank=len(items) + 1,
                )
            )
            seen_urls.add(url)
            if len(items) >= max_results:
                return items, saw_unverifiable_url

    return items, saw_unverifiable_url


def extract_native_web_search_usage(response: Any) -> tuple[int, int, int]:
    usage = native_web_search_field(response, "usage")
    input_tokens = coerce_int(native_web_search_field(usage, "input_tokens")) or 0
    output_tokens = coerce_int(native_web_search_field(usage, "output_tokens")) or 0
    total_tokens = coerce_int(native_web_search_field(usage, "total_tokens"))
    if total_tokens is None:
        total_tokens = input_tokens + output_tokens
    return input_tokens, output_tokens, total_tokens


def extract_native_web_search_request_count(response: Any) -> int:
    tool_usage = native_web_search_field(response, "tool_usage")
    web_search_usage = native_web_search_field(tool_usage, "web_search")
    request_count = coerce_int(native_web_search_field(web_search_usage, "num_requests"))
    return int(request_count or 0)


def extract_urls_from_native_web_search_text(text: str) -> list[tuple[str, int, int]]:
    matches: list[tuple[str, int, int]] = []
    source_text = str(text or "")
    if not source_text:
        return matches
    for match in re.finditer(r"https?://[^\s<>\]\)\"']+", source_text):
        url = str(match.group(0) or "").rstrip(".,;:!?)]")
        if not url:
            continue
        matches.append((url, match.start(), match.start() + len(url)))
    return matches


def extract_native_web_search_items_from_text(
    text: str,
    *,
    provider_label: str,
    backend_key: str,
    max_results: int,
) -> tuple[list[SearchResultItem], bool]:
    items: list[SearchResultItem] = []
    seen_urls: set[str] = set()
    saw_unverifiable_url = False
    for url, start_index, end_index in extract_urls_from_native_web_search_text(text):
        if not is_verifiable_native_web_search_url(url):
            saw_unverifiable_url = True
            continue
        if url in seen_urls:
            continue
        title = (urlparse(url).netloc or url).strip() or url
        items.append(
            SearchResultItem(
                title=title,
                url=url,
                snippet=normalize_native_web_search_snippet(
                    text,
                    title=title,
                    start_index=start_index,
                    end_index=end_index,
                ),
                source=backend_key,
                provider=provider_label,
                provider_mode=PROVIDER_MODE_NATIVE,
                rank=len(items) + 1,
            )
        )
        seen_urls.add(url)
        if len(items) >= max_results:
            break
    return items, saw_unverifiable_url


__all__ = [
    "coerce_int",
    "extract_native_web_search_items",
    "extract_native_web_search_items_from_text",
    "extract_native_web_search_request_count",
    "extract_native_web_search_usage",
    "extract_urls_from_native_web_search_text",
    "is_verifiable_native_web_search_url",
    "native_web_search_field",
    "normalize_native_web_search_snippet",
]
