"""Tool-result helpers extracted from RecoveryManager."""

from __future__ import annotations

import re

from app.ai.tools.types import ToolResult
from app.ai.types import ChatMessage

from .recovery_result_normalizer import RecoveryResultNormalizer
from .types import IntentPlan

_TERMINAL_PUNCTUATION = ("。", "！", "？", ".", "!", "?")
_TRUNCATION_MARKERS = ("[truncated]",)
_LINE_END_QUOTES = "\"'”’)]）】》』」"
_FETCH_BODY_NOISE_LINES = {
    "报告详情",
    "点击查看更多",
    "查看更多",
    "相关阅读",
    "相关阅读推荐",
    "相关推荐",
    "相关链接",
    "相关文章",
    "更多内容",
    "阅读更多",
    "返回首页",
    "首页",
    "目录",
    "导航",
    "overview",
    "relatedarticles",
    "readmore",
}
_FETCH_BODY_RANKED_LINE_RE = re.compile(
    r"^\s*[❒■□●○◆◇•*·\-–—]*\s*(?:第\s*)?\d{1,2}(?:\s*[.、:：)]|\s+)\s*\S+"
)
_FETCH_BODY_INLINE_SECTION_BOUNDARY_RE = re.compile(
    r"(?<!\S)(?=(?:[❒■□●○◆◇•*·\-–—]*\s*)?(?:第\s*)?(?:(?:0?[1-9]|1[0-9])\s*[.、:：)](?!\d)|(?:0[1-9]|1[0-9])\s+)\s*\S)"
)
_FETCH_BODY_LIST_HEADING_RE = re.compile(
    r"(?:top\s*\d+|排行榜|排名|榜单|战力榜|综合top)",
    re.IGNORECASE,
)
_GENERIC_FETCH_SUMMARY_RE = re.compile(r"^\s*fetched\s+https?://\S+\s*$", re.I)
DEFAULT_RECOVERY_RESULT_MAX_LENGTH = 500
FETCH_URL_RECOVERY_RESULT_MAX_LENGTH = 2000


def intent_recovery_result_max_length(intent: IntentPlan) -> int:
    if str(intent.family or "").strip() == "web_research" and "fetch_url" in set(
        intent.completed_by_tool_names or []
    ):
        return FETCH_URL_RECOVERY_RESULT_MAX_LENGTH
    return DEFAULT_RECOVERY_RESULT_MAX_LENGTH


def _has_terminal_punctuation(text: str) -> bool:
    normalized = str(text or "").strip().rstrip(_LINE_END_QUOTES)
    return normalized.endswith(_TERMINAL_PUNCTUATION)


def _looks_truncated(text: str) -> bool:
    normalized = str(text or "").strip().casefold()
    return bool(
        normalized.endswith(("...", "…"))
        or any(marker in normalized for marker in _TRUNCATION_MARKERS)
    )


def _is_generic_fetch_summary(text: str) -> bool:
    return bool(_GENERIC_FETCH_SUMMARY_RE.match(str(text or "").strip()))


def _fetch_url_payload_is_accepted_for_web_research(
    summary_payload: dict[str, object],
) -> bool:
    if summary_payload.get("ok") is False:
        return False
    top_level_failure_kind = str(summary_payload.get("failure_kind") or "").strip()
    if top_level_failure_kind == "low_query_relevance":
        return False
    if str(summary_payload.get("relevance_status") or "").strip() == "low_relevance":
        return False
    if (
        str(summary_payload.get("relevance_reason") or "").strip()
        == "low_query_relevance"
    ):
        return False
    top_level_answer_source = str(summary_payload.get("answer_source") or "").strip()
    top_level_evidence_quality = str(
        summary_payload.get("evidence_quality") or ""
    ).strip()
    if top_level_answer_source == "none" or top_level_evidence_quality == "none":
        return False
    top_level_rejected_urls = summary_payload.get("rejected_urls")
    top_level_fetched_urls = summary_payload.get("fetched_urls")
    if (
        isinstance(top_level_rejected_urls, list)
        and top_level_rejected_urls
        and not top_level_fetched_urls
    ):
        return False

    evidence = summary_payload.get("web_research_evidence")
    if not isinstance(evidence, dict):
        return True

    diagnostics = (
        evidence.get("diagnostics")
        if isinstance(evidence.get("diagnostics"), dict)
        else {}
    )
    answer_quality = str(evidence.get("answer_quality") or "").strip()
    answer_source = str(diagnostics.get("answer_source") or "").strip()
    failure_kind = str(
        diagnostics.get("failure_kind") or evidence.get("failure_kind") or ""
    ).strip()
    rejected_urls = diagnostics.get("rejected_urls")
    fetched_urls = diagnostics.get("fetched_urls")
    if answer_quality == "none" or answer_source == "none":
        return False
    if failure_kind == "low_query_relevance":
        return False
    return not (isinstance(rejected_urls, list) and rejected_urls and not fetched_urls)


def _is_useful_fetch_body_line(
    line: str,
    *,
    normalized_title: str,
    normalized_description: str,
) -> bool:
    normalized_line = RecoveryResultNormalizer._normalize_comparison_text(line)
    if not normalized_line:
        return False
    if normalized_line in _FETCH_BODY_NOISE_LINES:
        return False
    if len(line) <= 4 and not any(ch.isdigit() for ch in line):
        return False
    if normalized_title and normalized_line == normalized_title:
        return False
    return not (normalized_description and normalized_line == normalized_description)


def _is_fetch_body_ranked_line(line: str) -> bool:
    normalized = str(line or "").strip()
    if re.match(r"^\s*0\d\s+", normalized) and _is_fetch_body_list_heading(normalized):
        return False
    return bool(_FETCH_BODY_RANKED_LINE_RE.match(normalized))


def _is_fetch_body_list_heading(line: str) -> bool:
    normalized = str(line or "").strip()
    if not normalized:
        return False
    return bool(_FETCH_BODY_LIST_HEADING_RE.search(normalized))


def _split_fetch_body_logical_lines(line: str) -> list[str]:
    normalized = re.sub(r"\s+", " ", str(line or "").strip())
    if not normalized:
        return []
    boundary_indexes = [
        match.start()
        for match in _FETCH_BODY_INLINE_SECTION_BOUNDARY_RE.finditer(normalized)
        if match.start() > 0
    ]
    if not boundary_indexes:
        return [normalized]
    starts = [0, *boundary_indexes]
    ends = [*boundary_indexes, len(normalized)]
    return [
        normalized[start:end].strip()
        for start, end in zip(starts, ends, strict=False)
        if normalized[start:end].strip()
    ]


def _join_fetch_body_preview_parts(
    parts: list[str],
    *,
    max_length: int,
) -> str:
    preview_parts: list[str] = []
    used = 0
    for raw_part in parts:
        part = str(raw_part or "").strip()
        if not part:
            continue
        separator_len = 1 if preview_parts else 0
        next_used = used + separator_len + len(part)
        if next_used > max_length:
            if not preview_parts:
                return part[:max_length].rstrip()
            break
        preview_parts.append(part)
        used = next_used
    return "\n".join(preview_parts)


def _build_fetch_body_preview(
    useful_lines: list[str],
    *,
    max_length: int,
) -> str:
    if not useful_lines:
        return ""

    ranked_indexes = [
        index
        for index, line in enumerate(useful_lines)
        if _is_fetch_body_ranked_line(line)
    ]
    if ranked_indexes:
        first_ranked_index = ranked_indexes[0]
        preceding_window = useful_lines[
            max(0, first_ranked_index - 5) : first_ranked_index
        ]
        heading_candidates = [
            line for line in preceding_window if _is_fetch_body_list_heading(line)
        ]
        primary_heading_candidates = [
            line
            for line in heading_candidates
            if not str(line or "").strip().startswith(("(", "（"))
        ]
        preview_parts: list[str] = (
            primary_heading_candidates[-1:] or heading_candidates[-1:]
        )
        preview_parts.extend(useful_lines[index] for index in ranked_indexes[:10])
        return _join_fetch_body_preview_parts(
            preview_parts,
            max_length=max_length,
        )

    return _join_fetch_body_preview_parts(
        useful_lines,
        max_length=max_length,
    )


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
    if not _fetch_url_payload_is_accepted_for_web_research(summary_payload):
        return None

    title = str(summary_payload.get("title") or "").strip()
    description = str(summary_payload.get("description") or "").strip()
    generic_summary = str(
        summary_payload.get("summary") or result.summary or ""
    ).strip()
    title_has_site_suffix = "|" in title or "_" in title
    normalized_title = RecoveryResultNormalizer._normalize_comparison_text(title)
    normalized_description = RecoveryResultNormalizer._normalize_comparison_text(
        description
    )
    normalized_summary = RecoveryResultNormalizer._normalize_comparison_text(
        generic_summary
    )
    summary_truncated = _looks_truncated(generic_summary)
    description_truncated = _looks_truncated(description)
    summary_is_title_description = bool(
        normalized_title
        and normalized_description
        and normalized_summary
        == RecoveryResultNormalizer._normalize_comparison_text(
            f"{title} - {description}"
        )
    )
    summary_is_title_only = bool(
        normalized_title
        and normalized_summary
        and normalized_summary == normalized_title
    )
    summary_is_generic_fetch_status = _is_generic_fetch_summary(generic_summary)
    description_has_terminal_punctuation = _has_terminal_punctuation(description)
    description_incomplete = bool(
        description and not description_has_terminal_punctuation
    )

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
        for logical_line in _split_fetch_body_logical_lines(line):
            if not _is_useful_fetch_body_line(
                logical_line,
                normalized_title=normalized_title,
                normalized_description=normalized_description,
            ):
                continue
            useful_lines.append(logical_line)
            if len(useful_lines) >= 120:
                break
        if len(useful_lines) >= 120:
            break

    prefer_body_preview = bool(
        useful_lines
        and (
            summary_truncated
            or description_truncated
            or title_has_site_suffix
            or summary_is_title_description
            or summary_is_title_only
            or summary_is_generic_fetch_status
            or description_incomplete
        )
    )
    if prefer_body_preview:
        preview_parts: list[str] = []
        if (
            description
            and description_has_terminal_punctuation
            and description not in useful_lines[:2]
        ):
            preview_parts.append(description)
        body_preview = _build_fetch_body_preview(
            useful_lines,
            max_length=max_length,
        )
        if body_preview:
            preview_parts.append(body_preview)
        preview = _join_fetch_body_preview_parts(
            preview_parts,
            max_length=max_length,
        )
        normalized_preview = RecoveryResultNormalizer._normalize_comparison_text(
            preview
        )
        if normalized_preview and normalized_preview != normalized_title:
            return RecoveryResultNormalizer._normalize_cached_result(
                preview,
                max_length=max_length,
            )

    if (
        generic_summary
        and normalized_summary != normalized_title
        and not summary_truncated
        and not title_has_site_suffix
        and not summary_is_generic_fetch_status
    ):
        return RecoveryResultNormalizer._normalize_cached_result(
            generic_summary,
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
        body_preview = _build_fetch_body_preview(
            useful_lines,
            max_length=max_length,
        )
        if body_preview:
            preview_parts.append(body_preview)

    preview = _join_fetch_body_preview_parts(
        preview_parts,
        max_length=max_length,
    )
    normalized_preview = RecoveryResultNormalizer._normalize_comparison_text(preview)
    if normalized_preview and normalized_preview != normalized_title:
        return RecoveryResultNormalizer._normalize_cached_result(
            preview,
            max_length=max_length,
        )
    return None


def budgeted_web_research_response_candidates(
    tool_results: list[ToolResult] | None = None,
) -> list[str]:
    candidates: list[str] = []
    for result in tool_results or []:
        if not result.success or str(result.name or "").strip() != "fetch_url":
            continue
        payload = (
            dict(result.summary_payload)
            if isinstance(result.summary_payload, dict)
            else {}
        )
        if not _fetch_url_payload_is_accepted_for_web_research(payload):
            continue
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

    normalized_response = RecoveryResultNormalizer._normalize_comparison_text(
        raw_response
    )
    if not normalized_response:
        return True

    for candidate in budgeted_web_research_response_candidates(tool_results):
        normalized_candidate = RecoveryResultNormalizer._normalize_comparison_text(
            candidate
        )
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
        payload = (
            result.summary_payload if isinstance(result.summary_payload, dict) else {}
        )
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
                payload = (
                    dict(result.summary_payload)
                    if isinstance(result.summary_payload, dict)
                    else {}
                )
                if not _fetch_url_payload_is_accepted_for_web_research(payload):
                    continue
                preview = extract_fetch_url_user_preview(
                    result,
                    max_length=FETCH_URL_RECOVERY_RESULT_MAX_LENGTH,
                )
                if preview and preview not in normalized_results:
                    normalized_results.append(preview)
                continue
            for candidate in (
                result.summary_payload,
                result.summary,
                result.output or result.error,
            ):
                normalized = RecoveryResultNormalizer._normalize_cached_result(
                    candidate
                )
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
    "intent_recovery_result_max_length",
    "intent_result_from_tool_results",
    "latest_successful_tool_result",
    "should_replace_budgeted_web_research_response",
    "successful_tool_names",
    "tool_attempted",
    "web_search_result_count",
]
