from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def _normalize_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _score_candidate(candidate: Mapping[str, Any], query: str) -> int:
    normalized_query = query.lower()
    score = 0
    for field in (
        candidate.get("title"),
        candidate.get("description"),
        candidate.get("category"),
        " ".join(candidate.get("keywords") or []),
        " ".join(candidate.get("breadcrumb") or []),
    ):
        text = _normalize_text(field).lower()
        if not text:
            continue
        if text == normalized_query:
            score = max(score, 100)
        elif text.startswith(normalized_query):
            score = max(score, 80)
        elif normalized_query in text:
            score = max(score, 60)
    return score


def resolve_navigation_candidates(
    query: str,
    page_context: Mapping[str, Any] | None,
    *,
    limit: int = 5,
) -> list[dict[str, Any]]:
    if not isinstance(page_context, Mapping):
        return []
    page_data = page_context.get("page_data")
    if not isinstance(page_data, Mapping):
        return []
    menus = page_data.get("available_menus")
    if not isinstance(menus, list):
        return []
    normalized_query = _normalize_text(query)
    if not normalized_query:
        return []

    candidates: list[dict[str, Any]] = []
    for menu in menus:
        if not isinstance(menu, Mapping):
            continue
        score = _score_candidate(menu, normalized_query)
        if score <= 0:
            continue
        candidates.append(
            {
                "breadcrumb": list(menu.get("breadcrumb") or []),
                "page_key": _normalize_text(menu.get("page_key")) or None,
                "path": _normalize_text(menu.get("path")) or None,
                "score": score,
                "title": _normalize_text(menu.get("title")) or None,
            }
        )

    candidates.sort(key=lambda item: (-int(item["score"]), str(item.get("title") or "")))
    return candidates[: max(limit, 1)]
