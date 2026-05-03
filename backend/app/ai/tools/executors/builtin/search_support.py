"""
Search helpers for builtin tools.
内置工具的搜索辅助函数。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.ai.web_search.types import WebSearchExecution
from app.core.config import settings


def _normalize_text(text: str) -> str:
    """Collapse whitespace and trim text. / 折叠空白并裁剪文本。"""
    return " ".join((text or "").split())


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


def _wants_current_results(query: str) -> bool:
    normalized = _normalize_text(query).lower()
    if not normalized:
        return False
    return any(
        term in normalized
        for term in (
            "最新",
            "今年",
            "当前",
            "现在",
            "近期",
            "今天",
            "今日",
            "latest",
            "recent",
            "current",
            "today",
            "now",
            "this year",
        )
    )


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


def correct_query_year(query: str) -> str:
    """Replace stale calendar years in web_search queries unless the query is clearly historical."""
    if not query:
        return query
    if _looks_historical_query(query):
        return query
    if not _wants_current_results(query):
        return query
    try:
        current_year = datetime.now(settings.tz).year
    except Exception:
        current_year = datetime.now(timezone.utc).year
    return _replace_recent_years(query, current_year)


def build_search_summary_payload(
    execution: WebSearchExecution,
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
    if meta.fallback_reason:
        payload["fallback_reason"] = meta.fallback_reason
    if meta.native_failure_kind:
        payload["native_failure_kind"] = meta.native_failure_kind
    return payload


__all__ = ["build_search_summary_payload", "correct_query_year"]
