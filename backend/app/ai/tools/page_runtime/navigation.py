from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.ai.navigation_semantics import (
    extract_navigation_catalog_entries,
    search_navigation_entries,
)


def _normalize_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def resolve_navigation_candidates(
    query: str,
    page_context: Mapping[str, Any] | None,
    *,
    limit: int = 5,
) -> list[dict[str, Any]]:
    if not isinstance(page_context, Mapping):
        return []
    normalized_query = _normalize_text(query)
    if not normalized_query:
        return []
    entries = extract_navigation_catalog_entries(page_context)
    if not entries:
        return []

    candidates: list[dict[str, Any]] = []
    for entry, score in search_navigation_entries(entries, normalized_query)[
        : max(limit, 1)
    ]:
        candidates.append(
            {
                "breadcrumb": list(entry.get("breadcrumb") or []),
                "page_key": _normalize_text(entry.get("page_key")) or None,
                "path": _normalize_text(entry.get("path")) or None,
                "score": score,
                "title": _normalize_text(entry.get("title")) or None,
            }
        )

    return candidates
