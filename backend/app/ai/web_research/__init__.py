"""
Thin public facade for provider-neutral WebResearch runtime contracts.
"""

from app.ai.web_research.contracts import (
    FetchOptions,
    FetchProvider,
    SearchOptions,
    SearchProvider,
    WebResearchRunOptions,
)
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
from app.ai.web_research.normalization import (
    answer_source_for_quality,
    build_citations,
    build_web_research_evidence,
    determine_evidence_answer_quality,
    normalize_page_evidence,
    normalize_search_item,
)
from app.ai.web_research.routing import ProviderResolution, WebResearchProviderRouter
from app.ai.web_research.runtime import WebResearchRuntime
from app.ai.web_research.selection import (
    FetchCandidateSelection,
    SkippedFetchCandidate,
    select_fetch_candidates,
)

__all__ = [
    "AnswerQuality",
    "AnswerSource",
    "CitationEvidence",
    "EvidenceStatus",
    "FetchOptions",
    "FetchProvider",
    "PageEvidence",
    "PageStatus",
    "SearchEvidenceItem",
    "SearchOptions",
    "SearchProvider",
    "SearchResultSet",
    "FetchCandidateSelection",
    "ProviderResolution",
    "SkippedFetchCandidate",
    "WebResearchDiagnostics",
    "WebResearchEvidence",
    "WebResearchProviderRouter",
    "WebResearchRunOptions",
    "WebResearchRuntime",
    "answer_source_for_quality",
    "build_citations",
    "build_web_research_evidence",
    "determine_evidence_answer_quality",
    "normalize_page_evidence",
    "normalize_search_item",
    "select_fetch_candidates",
]
