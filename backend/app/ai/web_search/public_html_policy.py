"""
Public HTML query correction and relevance policy helpers.
公共 HTML 查询修正与相关性策略支持。
"""

from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import urlparse

from app.ai.web_search.public_html_parsing import normalize_text
from app.core.config import settings

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


def is_cjk(char: str) -> bool:
    return "\u4e00" <= char <= "\u9fff"


def scan_search_tokens(text: str) -> set[str]:
    tokens: set[str] = set()
    idx = 0
    length = len(text)
    while idx < length:
        char = text[idx]
        if is_cjk(char):
            start = idx
            while idx < length and is_cjk(text[idx]):
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


def strip_site_filters(query: str) -> str:
    tokens = []
    for token in (query or "").split():
        if token.lower().startswith("site:"):
            continue
        tokens.append(token)
    return " ".join(tokens)


def query_tokens_for_relevance(query: str) -> set[str]:
    scrubbed = strip_site_filters(query)
    return scan_search_tokens(scrubbed.lower())


def result_text_tokens(result: dict[str, str], *, include_url: bool) -> set[str]:
    parts = [str(result.get("title") or ""), str(result.get("snippet") or "")]
    if include_url:
        parts.append(str(result.get("url") or ""))
    hay = normalize_text(" ".join(parts)).lower()
    return scan_search_tokens(hay)


def result_is_search_wrapper(url: str) -> bool:
    try:
        host = (urlparse(url).hostname or "").lower()
    except Exception:  # noqa: BLE001
        return False
    return host in _SEARCH_ENGINE_HOSTS


def result_passes_relevance(query: str, result: dict[str, str]) -> bool:
    q_tokens = query_tokens_for_relevance(query)
    url = str(result.get("url") or "")
    if not q_tokens:
        return not result_is_search_wrapper(url)

    ts_tokens = result_text_tokens(result, include_url=False)
    ts_hits = len(q_tokens & ts_tokens)
    ts_ratio = ts_hits / len(q_tokens)
    if ts_ratio >= _QUERY_RELEVANCE_MIN_RATIO or ts_hits >= max(
        1, (len(q_tokens) + 1) // 2
    ):
        return True

    if result_is_search_wrapper(url):
        return False

    all_tokens = result_text_tokens(result, include_url=True)
    all_hits = len(q_tokens & all_tokens)
    return all_hits / len(q_tokens) >= _QUERY_RELEVANCE_MIN_RATIO


def filter_low_confidence_results(
    query: str,
    results: list[dict[str, str]],
) -> list[dict[str, str]]:
    return [result for result in results if result_passes_relevance(query, result)]


def looks_historical_query(query: str) -> bool:
    normalized = normalize_text(query).lower()
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


def replace_recent_years(query: str, current_year: int) -> str:
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


def correct_query_year(query: str) -> str:
    if not query or looks_historical_query(query):
        return query
    try:
        current_year = datetime.now(settings.tz).year
    except Exception:  # noqa: BLE001
        current_year = datetime.now(timezone.utc).year
    return replace_recent_years(query, current_year)


__all__ = [
    "correct_query_year",
    "filter_low_confidence_results",
    "looks_historical_query",
    "query_tokens_for_relevance",
    "replace_recent_years",
    "result_passes_relevance",
    "scan_search_tokens",
    "strip_site_filters",
]
