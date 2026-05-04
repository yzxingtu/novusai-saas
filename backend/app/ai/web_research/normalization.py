"""
Deterministic normalization helpers for WebResearch evidence.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from app.ai.web_research.evidence import (
    AnswerQuality,
    AnswerSource,
    CitationEvidence,
    EvidenceStatus,
    PageEvidence,
    PageStatus,
    SearchEvidenceItem,
    SearchResultSet,
    WebResearchDiagnostics,
    WebResearchEvidence,
)


def normalize_search_item(
    *,
    title: str,
    url: str,
    snippet: str,
    rank: int,
    provider: str,
    allow_snippet_quality: bool = False,
    raw: Mapping[str, Any] | None = None,
) -> SearchEvidenceItem:
    return SearchEvidenceItem(
        title=title.strip(),
        url=url.strip(),
        snippet=snippet.strip(),
        rank=rank,
        provider=provider,
        answer_quality=_search_answer_quality(snippet, allow_snippet_quality),
        raw=raw,
    )


def normalize_page_evidence(
    *,
    url: str,
    status: PageStatus,
    title: str,
    body_text: str,
    summary: str,
    description: str,
    provider: str,
    failure_kind: str | None = None,
    raw: Mapping[str, Any] | None = None,
) -> PageEvidence:
    return PageEvidence(
        url=url.strip(),
        status=status,
        title=title.strip(),
        body_text=body_text.strip(),
        summary=summary.strip(),
        description=description.strip(),
        answer_quality=_page_answer_quality(status, body_text, summary),
        provider=provider,
        failure_kind=failure_kind,
        raw=raw,
    )


def build_web_research_evidence(
    *,
    query: str,
    search_results: SearchResultSet,
    fetched_pages: Sequence[PageEvidence],
    fetch_provider: str,
    pipeline_id: str,
    candidate_urls: Sequence[str],
    require_fetch: bool,
    provider_disable_reason: str | None = None,
    raw_diagnostics: Mapping[str, Any] | None = None,
) -> WebResearchEvidence:
    pages = list(fetched_pages)
    quality = determine_evidence_answer_quality(
        search_results.items,
        pages,
        require_fetch=require_fetch,
    )
    status = determine_evidence_status(
        search_results=search_results,
        fetched_pages=pages,
        answer_quality=quality,
        require_fetch=require_fetch,
    )
    failure_kind = determine_failure_kind(
        search_results=search_results,
        fetched_pages=pages,
        answer_quality=quality,
        status=status,
        require_fetch=require_fetch,
    )
    fetched_urls = [page.url for page in pages if page.status == "completed"]
    diagnostics = WebResearchDiagnostics(
        pipeline_id=pipeline_id,
        search_provider=search_results.provider,
        fetch_provider=fetch_provider,
        evidence_status=status,
        candidate_urls=list(candidate_urls),
        fetched_urls=fetched_urls,
        evidence_quality=quality,
        answer_source=answer_source_for_quality(quality),
        failure_kind=failure_kind,
        provider_disable_reason=provider_disable_reason,
        raw=dict(raw_diagnostics or {}),
    )
    return WebResearchEvidence(
        query=query,
        status=status,
        search_provider=search_results.provider,
        fetch_provider=fetch_provider,
        search_results=list(search_results.items),
        fetched_pages=pages,
        citations=build_citations(
            search_results.items,
            pages,
            allow_search_result_citations=quality == "snippet",
        ),
        answer_quality=quality,
        failure_kind=failure_kind,
        diagnostics=diagnostics,
    )


def determine_evidence_answer_quality(
    search_results: Sequence[SearchEvidenceItem],
    fetched_pages: Sequence[PageEvidence],
    *,
    require_fetch: bool = False,
) -> AnswerQuality:
    page_qualities = [page.answer_quality for page in fetched_pages]
    if "body" in page_qualities:
        return "body"
    if "summary" in page_qualities:
        return "summary"
    if require_fetch:
        return "none"
    if any(item.answer_quality == "snippet" for item in search_results):
        return "snippet"
    return "none"


def determine_evidence_status(
    *,
    search_results: SearchResultSet,
    fetched_pages: Sequence[PageEvidence],
    answer_quality: AnswerQuality,
    require_fetch: bool,
) -> EvidenceStatus:
    if search_results.status == "failed" and not search_results.items:
        return "failed"
    if answer_quality == "none":
        return "partial" if search_results.items else "failed"
    if require_fetch and fetched_pages:
        return "completed" if _all_pages_completed(fetched_pages) else "partial"
    if require_fetch and not fetched_pages:
        return "partial"
    return "completed" if search_results.status == "completed" else "partial"


def determine_failure_kind(
    *,
    search_results: SearchResultSet,
    fetched_pages: Sequence[PageEvidence],
    answer_quality: AnswerQuality,
    status: EvidenceStatus,
    require_fetch: bool,
) -> str | None:
    if status == "completed":
        return None
    if search_results.status == "failed" and not search_results.items:
        return search_results.failure_kind or "search_failed"
    failed_pages = [page for page in fetched_pages if page.status != "completed"]
    if failed_pages:
        return failed_pages[0].failure_kind or f"fetch_{failed_pages[0].status}"
    if require_fetch and not fetched_pages and search_results.items:
        return "fetch_not_attempted"
    if answer_quality == "none":
        return "no_answer_quality_evidence"
    return search_results.failure_kind


def build_citations(
    search_results: Sequence[SearchEvidenceItem],
    fetched_pages: Sequence[PageEvidence],
    *,
    allow_search_result_citations: bool = True,
) -> list[CitationEvidence]:
    page_citations = [
        CitationEvidence(
            title=page.title or page.url,
            url=page.url,
            provider=page.provider,
            source="page",
        )
        for page in fetched_pages
        if page.status == "completed" and page.answer_quality in {"body", "summary"}
    ]
    if page_citations:
        return page_citations

    if not allow_search_result_citations:
        return []

    return [
        CitationEvidence(
            title=item.title or item.url,
            url=item.url,
            provider=item.provider,
            source="search_result",
            rank=item.rank,
        )
        for item in search_results
        if item.answer_quality == "snippet"
    ]


def answer_source_for_quality(answer_quality: AnswerQuality) -> AnswerSource:
    if answer_quality == "body":
        return "fetched_body"
    if answer_quality == "summary":
        return "fetched_summary"
    if answer_quality == "snippet":
        return "search_snippet"
    return "none"


def _page_answer_quality(
    status: PageStatus,
    body_text: str,
    summary: str,
) -> AnswerQuality:
    if status != "completed":
        return "none"
    if body_text.strip():
        return "body"
    if summary.strip():
        return "summary"
    return "none"


def _search_answer_quality(
    snippet: str,
    allow_snippet_quality: bool,
) -> AnswerQuality:
    if allow_snippet_quality and snippet.strip():
        return "snippet"
    return "none"


def _all_pages_completed(fetched_pages: Sequence[PageEvidence]) -> bool:
    return all(page.status == "completed" for page in fetched_pages)


__all__ = [
    "answer_source_for_quality",
    "build_citations",
    "build_web_research_evidence",
    "determine_evidence_answer_quality",
    "determine_evidence_status",
    "determine_failure_kind",
    "normalize_page_evidence",
    "normalize_search_item",
]
