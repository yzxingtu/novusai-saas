from __future__ import annotations

from typing import Any

from app.ai.tools.types import ToolResult

from .execution_state_machine import get_current_execution_state_machine


def active_intent() -> Any | None:
    state = get_current_execution_state_machine()
    if state is None:
        return None
    for intent in state.intent_plan:
        if intent.status in {"completed", "failed", "skipped"}:
            continue
        if intent.family == "none" or not intent.requires_tools:
            continue
        return intent
    return None


def _normalized_url_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    normalized: list[str] = []
    for item in value:
        url = str(item or "").strip()
        if url and url not in normalized:
            normalized.append(url)
    return normalized


def intent_url_list(intent: Any | None, key: str) -> list[str]:
    metadata = dict(getattr(intent, "metadata", {}) or {}) if intent is not None else {}
    return _normalized_url_list(metadata.get(key))


def intent_pinned_url(intent: Any | None) -> str:
    if intent is None:
        return ""
    metadata = dict(getattr(intent, "metadata", {}) or {})
    return str(metadata.get("explicit_url") or "").strip()


def _set_intent_url_list(intent: Any | None, key: str, values: list[str]) -> None:
    if intent is None:
        return
    metadata = dict(getattr(intent, "metadata", {}) or {})
    metadata[key] = _normalized_url_list(values)
    intent.metadata = metadata


def mark_fetch_url_attempt(
    intent: Any | None,
    url: str,
    *,
    blocked: bool = False,
) -> None:
    normalized_url = str(url or "").strip()
    if not normalized_url or intent is None:
        return
    attempted_urls = intent_url_list(intent, "fetch_url_attempted_urls")
    if normalized_url not in attempted_urls:
        attempted_urls.append(normalized_url)
    _set_intent_url_list(intent, "fetch_url_attempted_urls", attempted_urls)
    if blocked:
        blocked_urls = intent_url_list(intent, "fetch_url_blocked_urls")
        if normalized_url not in blocked_urls:
            blocked_urls.append(normalized_url)
        _set_intent_url_list(intent, "fetch_url_blocked_urls", blocked_urls)


def is_blocked_fetch_url_result(result: ToolResult) -> bool:
    if str(result.error_type or "").strip() == "blocked_url":
        return True
    error_text = str(result.error or "").lower()
    if not error_text:
        return False
    return any(marker in error_text for marker in ("http 401", "http 403", "http 429")) or (
        "page may block automated access" in error_text
        or "该页面可能被站点拦截" in error_text
    )


def resolve_fetch_url_candidates(
    *,
    intent: Any | None,
    requested_url: str,
) -> tuple[str | None, list[str], str]:
    normalized_requested_url = str(requested_url or "").strip()
    pinned_url = intent_pinned_url(intent)
    if pinned_url:
        return pinned_url, [], normalized_requested_url
    candidate_urls = intent_url_list(intent, "fetch_url_candidate_urls")
    if not candidate_urls:
        return None, [], normalized_requested_url

    attempted_urls = set(intent_url_list(intent, "fetch_url_attempted_urls"))
    requested_is_candidate = normalized_requested_url in candidate_urls
    remaining_urls = [url for url in candidate_urls if url not in attempted_urls]
    selected_url = normalized_requested_url
    fallback_urls: list[str] = []

    if requested_is_candidate and normalized_requested_url not in attempted_urls:
        selected_url = normalized_requested_url
        fallback_urls = [url for url in remaining_urls if url != normalized_requested_url]
    elif remaining_urls:
        selected_url = remaining_urls[0]
        fallback_urls = remaining_urls[1:]
    elif requested_is_candidate:
        selected_url = normalized_requested_url
        fallback_urls = [url for url in candidate_urls if url != normalized_requested_url]
    else:
        selected_url = ""
        fallback_urls = []

    return (
        selected_url or None,
        fallback_urls,
        normalized_requested_url,
    )
