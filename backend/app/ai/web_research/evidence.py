"""
Provider-neutral WebResearch evidence contracts.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

EvidenceStatus = Literal["completed", "partial", "failed"]
PageStatus = Literal["completed", "failed", "blocked", "skipped"]
AnswerQuality = Literal["body", "summary", "snippet", "none"]
AnswerSource = Literal["fetched_body", "fetched_summary", "search_snippet", "none"]
RelevanceStatus = Literal["relevant", "low_relevance", "unscored"]


@dataclass(frozen=True, slots=True)
class SearchEvidenceItem:
    title: str
    url: str
    snippet: str
    rank: int
    provider: str
    answer_quality: AnswerQuality = "none"
    raw: Mapping[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class SearchResultSet:
    query: str
    provider: str
    items: list[SearchEvidenceItem] = field(default_factory=list)
    status: EvidenceStatus = "completed"
    failure_kind: str | None = None
    diagnostics: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class PageEvidence:
    url: str
    status: PageStatus
    title: str
    body_text: str
    summary: str
    description: str
    answer_quality: AnswerQuality
    provider: str
    failure_kind: str | None = None
    raw: Mapping[str, Any] | None = None
    relevance_status: RelevanceStatus = "unscored"
    relevance_score: float = 0.0
    relevance_profile: str | None = None
    relevance_reason: str | None = None
    relevance_matched_terms: list[str] = field(default_factory=list)
    relevance_required_terms: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class CitationEvidence:
    title: str
    url: str
    provider: str
    source: Literal["page", "search_result"]
    rank: int | None = None


@dataclass(frozen=True, slots=True)
class WebResearchDiagnostics:
    pipeline_id: str
    search_provider: str
    fetch_provider: str
    evidence_status: EvidenceStatus
    candidate_urls: list[str]
    fetched_urls: list[str]
    rejected_urls: list[str]
    evidence_quality: AnswerQuality
    answer_source: AnswerSource
    failure_kind: str | None = None
    provider_disable_reason: str | None = None
    relevance_profile: str | None = None
    relevance_rejection_count: int = 0
    raw: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class WebResearchEvidence:
    query: str
    status: EvidenceStatus
    search_provider: str
    fetch_provider: str
    search_results: list[SearchEvidenceItem]
    fetched_pages: list[PageEvidence]
    citations: list[CitationEvidence]
    answer_quality: AnswerQuality
    failure_kind: str | None
    diagnostics: WebResearchDiagnostics

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


__all__ = [
    "AnswerQuality",
    "AnswerSource",
    "CitationEvidence",
    "EvidenceStatus",
    "PageEvidence",
    "PageStatus",
    "RelevanceStatus",
    "SearchEvidenceItem",
    "SearchResultSet",
    "WebResearchDiagnostics",
    "WebResearchEvidence",
]
