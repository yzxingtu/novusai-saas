"""
Pure fetch-candidate selection for WebResearch.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal
from urllib.parse import urlparse

from app.ai.web_research.evidence import SearchResultSet

SkippedCandidateReason = Literal[
    "empty_url",
    "duplicate_url",
    "unsupported_scheme",
]


@dataclass(frozen=True, slots=True)
class SkippedFetchCandidate:
    url: str
    title: str
    rank: int
    provider: str
    reason: SkippedCandidateReason


@dataclass(frozen=True, slots=True)
class FetchCandidateSelection:
    candidate_urls: list[str] = field(default_factory=list)
    selected_urls: list[str] = field(default_factory=list)
    skipped: list[SkippedFetchCandidate] = field(default_factory=list)


def select_fetch_candidates(
    search_results: SearchResultSet,
    *,
    max_fetches: int,
    require_fetch: bool,
) -> FetchCandidateSelection:
    fetch_limit = _fetch_limit(max_fetches=max_fetches, require_fetch=require_fetch)
    if fetch_limit <= 0:
        return FetchCandidateSelection()

    candidate_urls: list[str] = []
    skipped: list[SkippedFetchCandidate] = []
    seen: set[str] = set()

    for item in sorted(search_results.items, key=lambda result: result.rank):
        url = item.url.strip()
        if not url:
            skipped.append(
                SkippedFetchCandidate(
                    url="",
                    title=item.title,
                    rank=item.rank,
                    provider=item.provider,
                    reason="empty_url",
                )
            )
            continue
        if url in seen:
            skipped.append(
                SkippedFetchCandidate(
                    url=url,
                    title=item.title,
                    rank=item.rank,
                    provider=item.provider,
                    reason="duplicate_url",
                )
            )
            continue
        seen.add(url)
        if not _is_fetchable_url(url):
            skipped.append(
                SkippedFetchCandidate(
                    url=url,
                    title=item.title,
                    rank=item.rank,
                    provider=item.provider,
                    reason="unsupported_scheme",
                )
            )
            continue
        candidate_urls.append(url)

    return FetchCandidateSelection(
        candidate_urls=candidate_urls,
        selected_urls=candidate_urls[:fetch_limit],
        skipped=skipped,
    )


def _fetch_limit(*, max_fetches: int, require_fetch: bool) -> int:
    if require_fetch:
        return max(1, max_fetches)
    return max(0, max_fetches)


def _is_fetchable_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


__all__ = [
    "FetchCandidateSelection",
    "SkippedCandidateReason",
    "SkippedFetchCandidate",
    "select_fetch_candidates",
]
