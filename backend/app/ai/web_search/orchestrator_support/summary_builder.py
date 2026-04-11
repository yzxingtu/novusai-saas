from __future__ import annotations

from urllib.parse import urlparse

from app.ai.web_search.types import SearchResultItem


def has_search_wrapper_url(
    items: list[SearchResultItem],
    *,
    search_engine_hosts: frozenset[str],
) -> bool:
    for item in items:
        try:
            host = (urlparse(item.url).hostname or "").lower()
        except Exception:
            continue
        if host in search_engine_hosts or host.endswith(".baidu.com") or host.endswith(
            ".so.com"
        ):
            return True
    return False


def build_search_output_text(
    query: str,
    items: list[SearchResultItem],
    *,
    search_engine_hosts: frozenset[str],
) -> str:
    lines = [f"Search results for: {query}\n"]
    if has_search_wrapper_url(items, search_engine_hosts=search_engine_hosts):
        lines.append(
            "Note: Some URLs below are search-engine redirect links; use fetch_url to load "
            "the final page content (redirects are followed automatically).\n"
        )
    for index, item in enumerate(items, start=1):
        lines.append(f"{index}. {item.title}")
        lines.append(f"   URL: {item.url}")
        if item.snippet:
            lines.append(f"   {item.snippet}")
        lines.append("")
    return "\n".join(lines).rstrip()

