from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def _normalize_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _score_match(haystack: str, needle: str) -> int:
    normalized_haystack = haystack.lower()
    normalized_needle = needle.lower()
    if normalized_haystack == normalized_needle:
        return 100
    if normalized_haystack.startswith(normalized_needle):
        return 80
    if normalized_needle in normalized_haystack:
        return 60
    return 0


def search_runtime_snapshot(
    snapshot: Mapping[str, Any] | None,
    query: str,
    *,
    limit: int = 10,
) -> list[dict[str, Any]]:
    if not isinstance(snapshot, Mapping):
        return []
    normalized_query = _normalize_text(query)
    if not normalized_query:
        return []

    hits: list[dict[str, Any]] = []
    for node in snapshot.get("nodes") or []:
        if not isinstance(node, Mapping):
            continue
        text_parts = [
            _normalize_text(node.get("summary")),
            _normalize_text(node.get("content")),
            _normalize_text(node.get("text")),
            _normalize_text(node.get("label")),
        ]
        combined = " ".join(part for part in text_parts if part)
        score = _score_match(combined, normalized_query)
        if score <= 0:
            continue
        hits.append(
            {
                "kind": str(node.get("kind") or "unknown"),
                "locator": str(node.get("locator") or "").strip() or None,
                "score": score,
                "surface_id": str(node.get("surface_id") or "").strip() or None,
                "text": combined[:240],
            }
        )

    hits.sort(key=lambda item: (-int(item["score"]), str(item.get("locator") or "")))
    return hits[: max(limit, 1)]
