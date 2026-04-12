"""Tool-result helpers extracted from RecoveryManager."""

from __future__ import annotations

from app.ai.tools.types import ToolResult
from app.ai.types import ChatMessage

from .recovery_result_normalizer import RecoveryResultNormalizer
from .types import IntentPlan


def extract_fetch_url_user_preview(
    result: ToolResult,
    *,
    max_length: int = 500,
) -> str | None:
    summary_payload = (
        dict(result.summary_payload) if isinstance(result.summary_payload, dict) else {}
    )
    if not summary_payload.get("fetch_url"):
        return None

    title = str(summary_payload.get("title") or "").strip()
    description = str(summary_payload.get("description") or "").strip()
    generic_summary = str(summary_payload.get("summary") or result.summary or "").strip()
    title_has_site_suffix = "|" in title or "_" in title
    normalized_title = RecoveryResultNormalizer._normalize_comparison_text(title)
    normalized_description = RecoveryResultNormalizer._normalize_comparison_text(description)
    normalized_summary = RecoveryResultNormalizer._normalize_comparison_text(generic_summary)
    summary_truncated = generic_summary.endswith(("...", "…"))
    description_truncated = description.endswith(("...", "…"))

    useful_lines: list[str] = []
    for raw_line in str(result.output or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith(
            (
                "Content from ",
                "Redirected from: ",
                "Title: ",
                "Description: ",
                "Key sections: ",
            )
        ):
            continue
        normalized_line = RecoveryResultNormalizer._normalize_comparison_text(line)
        if not normalized_line:
            continue
        if normalized_title and normalized_line == normalized_title:
            continue
        if normalized_description and normalized_line == normalized_description:
            continue
        useful_lines.append(line)
        if len(" ".join(useful_lines)) >= max_length:
            break

    if (
        generic_summary
        and normalized_summary != normalized_title
        and not summary_truncated
        and not title_has_site_suffix
    ):
        return RecoveryResultNormalizer._normalize_cached_result(
            generic_summary,
            max_length=max_length,
        )
    if useful_lines and (summary_truncated or description_truncated or title_has_site_suffix):
        preview_parts: list[str] = []
        if description and description not in useful_lines[:2]:
            preview_parts.append(description)
        preview_parts.extend(useful_lines[:2])
        preview = " ".join(part.strip() for part in preview_parts if part.strip())
        normalized_preview = RecoveryResultNormalizer._normalize_comparison_text(preview)
        if normalized_preview and normalized_preview != normalized_title:
            return RecoveryResultNormalizer._normalize_cached_result(
                preview,
                max_length=max_length,
            )
    if title and description and not title_has_site_suffix:
        return RecoveryResultNormalizer._normalize_cached_result(
            f"{title} - {description}",
            max_length=max_length,
        )
    if description:
        return RecoveryResultNormalizer._normalize_cached_result(
            description,
            max_length=max_length,
        )

    preview_parts: list[str] = []
    if description:
        preview_parts.append(description)
    if useful_lines:
        preview_parts.extend(useful_lines[:2])

    preview = " ".join(part.strip() for part in preview_parts if part.strip())
    normalized_preview = RecoveryResultNormalizer._normalize_comparison_text(preview)
    if normalized_preview and normalized_preview != normalized_title:
        return RecoveryResultNormalizer._normalize_cached_result(
            preview,
            max_length=max_length,
        )
    if title:
        return RecoveryResultNormalizer._normalize_cached_result(title, max_length=max_length)
    return None


def budgeted_web_research_response_candidates(
    tool_results: list[ToolResult] | None = None,
) -> list[str]:
    candidates: list[str] = []
    for result in tool_results or []:
        if not result.success or str(result.name or "").strip() != "fetch_url":
            continue
        payload = dict(result.summary_payload) if isinstance(result.summary_payload, dict) else {}
        raw_title = str(payload.get("title") or "").strip()
        description = str(payload.get("description") or "").strip()
        for candidate in (
            payload.get("summary"),
            f"{raw_title} - {description}" if raw_title and description else None,
            extract_fetch_url_user_preview(result),
            description,
            result.summary,
            raw_title,
        ):
            normalized = RecoveryResultNormalizer._normalize_cached_result(candidate)
            if normalized and normalized not in candidates:
                candidates.append(normalized)
    return candidates


def should_replace_budgeted_web_research_response(
    *,
    response_text: str,
    tool_results: list[ToolResult] | None = None,
) -> bool:
    raw_response = str(response_text or "").strip()
    if not raw_response:
        return True

    lowered_response = raw_response.casefold()
    if lowered_response.startswith(("content from ", "title: ", "description: ")):
        return True

    normalized_response = RecoveryResultNormalizer._normalize_comparison_text(raw_response)
    if not normalized_response:
        return True

    for candidate in budgeted_web_research_response_candidates(tool_results):
        normalized_candidate = RecoveryResultNormalizer._normalize_comparison_text(candidate)
        if normalized_candidate and normalized_response == normalized_candidate:
            return True
    return False


def successful_tool_names(
    messages: list[ChatMessage],
    tool_results: list[ToolResult] | None = None,
) -> list[str]:
    names: list[str] = []
    for result in tool_results or []:
        if result.success and result.name not in names:
            names.append(result.name)
    for message in messages:
        if message.role != "assistant" or not message.tool_calls:
            continue
        for tool_call in message.tool_calls:
            if tool_call.get("success") is not True:
                continue
            func = tool_call.get("function") or {}
            name = str(func.get("name") or tool_call.get("name") or "").strip()
            if name and name not in names:
                names.append(name)
    return names


def tool_attempted(
    messages: list[ChatMessage],
    tool_name: str,
    tool_results: list[ToolResult] | None = None,
) -> bool:
    normalized_name = str(tool_name or "").strip()
    if not normalized_name:
        return False
    for result in tool_results or []:
        if str(result.name or "").strip() == normalized_name:
            return True
    for message in messages:
        if message.role != "assistant" or not message.tool_calls:
            continue
        for tool_call in message.tool_calls:
            func = tool_call.get("function") or {}
            name = str(func.get("name") or tool_call.get("name") or "").strip()
            if name == normalized_name:
                return True
    return False


def extract_fetch_url_candidate_urls(
    tool_results: list[ToolResult] | None,
) -> list[str]:
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


def latest_successful_tool_result(
    tool_name: str,
    tool_results: list[ToolResult] | None = None,
) -> ToolResult | None:
    normalized_name = str(tool_name or "").strip()
    if not normalized_name:
        return None
    for result in reversed(tool_results or []):
        if result.success and str(result.name or "").strip() == normalized_name:
            return result
    return None


def web_search_result_count(tool_results: list[ToolResult] | None = None) -> int | None:
    result = latest_successful_tool_result("web_search", tool_results)
    if result is None:
        return None
    payload = result.summary_payload if isinstance(result.summary_payload, dict) else {}
    raw_count = payload.get("result_count")
    try:
        if raw_count is not None:
            return max(0, int(raw_count))
    except (TypeError, ValueError):
        pass
    items = payload.get("items")
    if isinstance(items, list):
        return len(items)
    return None


def intent_result_from_tool_results(
    intent: IntentPlan,
    tool_results: list[ToolResult] | None = None,
) -> str | None:
    if not tool_results:
        return None
    candidate_tool_names: list[str] = []
    prioritized_tool_names = list(intent.completed_by_tool_names or [])
    if not prioritized_tool_names:
        prioritized_tool_names = list(intent.completion_signals or []) + list(
            intent.allowed_tool_names or []
        )
    for tool_name in prioritized_tool_names:
        normalized_name = str(tool_name or "").strip()
        if normalized_name and normalized_name not in candidate_tool_names:
            candidate_tool_names.append(normalized_name)
    if (
        not intent.completed_by_tool_names
        and str(intent.family or "").strip() == "web_research"
        and "web_search" not in candidate_tool_names
    ):
        candidate_tool_names.append("web_search")
    if not candidate_tool_names:
        return None

    normalized_results: list[str] = []
    for name in candidate_tool_names:
        for result in tool_results:
            if not result.success or result.name != name:
                continue
            if (
                str(intent.family or "").strip() == "web_research"
                and str(result.name or "").strip() == "fetch_url"
            ):
                preview = extract_fetch_url_user_preview(result)
                if preview:
                    if preview not in normalized_results:
                        normalized_results.append(preview)
                    continue
            for candidate in (
                result.summary_payload,
                result.summary,
                result.output or result.error,
            ):
                normalized = RecoveryResultNormalizer._normalize_cached_result(candidate)
                if normalized:
                    if normalized not in normalized_results:
                        normalized_results.append(normalized)
                    break
    if not normalized_results:
        return None
    return "；".join(normalized_results[:2])


__all__ = [
    "budgeted_web_research_response_candidates",
    "extract_fetch_url_candidate_urls",
    "extract_fetch_url_user_preview",
    "intent_result_from_tool_results",
    "latest_successful_tool_result",
    "should_replace_budgeted_web_research_response",
    "successful_tool_names",
    "tool_attempted",
    "web_search_result_count",
]
