"""Utility helpers extracted from RecoveryManager."""

from __future__ import annotations

from typing import Any

from app.ai.tools.types import ToolResult


def normalize_comparison_text(text: str) -> str:
    return "".join(ch for ch in str(text or "").casefold() if ch.isalnum())


def normalized_url_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    normalized: list[str] = []
    for item in value:
        url = str(item or "").strip()
        if url and url not in normalized:
            normalized.append(url)
    return normalized


def extract_fetch_url_candidate_urls(tool_results: list[ToolResult] | None) -> list[str]:
    candidate_urls: list[str] = []
    for result in tool_results or []:
        if not result.success or str(result.name or "").strip() != "web_search":
            continue
        payload = result.summary_payload if isinstance(result.summary_payload, dict) else {}
        items = payload.get("items")
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            url = str(item.get("url") or "").strip()
            if url and url not in candidate_urls:
                candidate_urls.append(url)
    return candidate_urls

