"""
Query-profile planning for platform WebResearch.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from app.ai.web_research.evidence import SearchEvidenceItem, SearchResultSet
from app.ai.web_research.normalization import normalize_search_item
from app.ai.web_research.relevance import detect_query_profile


@dataclass(frozen=True, slots=True)
class TrustedSeedCandidate:
    title: str
    url: str
    snippet: str
    provider: str = "platform:trusted_seed"


@dataclass(frozen=True, slots=True)
class WebResearchQueryPlan:
    profile: str
    trusted_seed_candidates: list[TrustedSeedCandidate]
    minimum_relevant_sources: int = 1
    source_quality_floor: str = "any_relevant_fetch_evidence"

    @property
    def trusted_seed_urls(self) -> list[str]:
        return [candidate.url for candidate in self.trusted_seed_candidates]


_LLM_LEADERBOARD_TRUSTED_SEEDS = (
    TrustedSeedCandidate(
        title="Artificial Analysis LLM Leaderboard",
        url="https://artificialanalysis.ai/leaderboards/models",
        snippet=(
            "Comparison and ranking of AI models across intelligence, "
            "performance, price, speed and context metrics."
        ),
    ),
    TrustedSeedCandidate(
        title="LMArena Arena Leaderboard",
        url="https://lmarena.ai/leaderboard",
        snippet=(
            "Arena leaderboard comparing frontier AI models across text, code, "
            "vision, document, search and other benchmark arenas."
        ),
    ),
)


def build_web_research_query_plan(query: str) -> WebResearchQueryPlan:
    profile = detect_query_profile(query)
    if profile == "llm_leaderboard":
        return WebResearchQueryPlan(
            profile=profile,
            trusted_seed_candidates=list(_LLM_LEADERBOARD_TRUSTED_SEEDS),
            minimum_relevant_sources=2,
            source_quality_floor="trusted_leaderboard_or_relevant_benchmark",
        )
    return WebResearchQueryPlan(profile=profile, trusted_seed_candidates=[])


def apply_query_plan_to_search_results(
    search_results: SearchResultSet,
    *,
    plan: WebResearchQueryPlan,
) -> SearchResultSet:
    if not plan.trusted_seed_candidates:
        return search_results

    items: list[SearchEvidenceItem] = []
    seen_url_keys: set[str] = set()
    organic_items = sorted(search_results.items, key=lambda result: result.rank)

    for seed in plan.trusted_seed_candidates:
        url_key = _canonical_url_key(seed.url)
        if url_key and url_key in seen_url_keys:
            continue
        if url_key:
            seen_url_keys.add(url_key)
        items.append(
            normalize_search_item(
                title=seed.title,
                url=seed.url,
                snippet=seed.snippet,
                rank=len(items) + 1,
                provider=seed.provider,
                raw={
                    "source": "trusted_seed",
                    "query_profile": plan.profile,
                    "trusted_seed": True,
                    "trusted_seed_index": len(items) + 1,
                },
            )
        )

    for item in organic_items:
        url_key = _canonical_url_key(item.url)
        if url_key and url_key in seen_url_keys:
            continue
        if url_key:
            seen_url_keys.add(url_key)
        items.append(replace(item, rank=len(items) + 1))

    diagnostics = dict(search_results.diagnostics or {})
    diagnostics.update(
        {
            "query_profile": plan.profile,
            "trusted_seed_candidate_urls": plan.trusted_seed_urls,
            "trusted_seed_count": len(plan.trusted_seed_candidates),
            "organic_result_count": len(search_results.items),
            "planned_result_count": len(items),
            "minimum_relevant_sources": plan.minimum_relevant_sources,
            "source_quality_floor": plan.source_quality_floor,
        }
    )
    return replace(search_results, items=items, diagnostics=diagnostics)


_TRACKING_QUERY_KEYS = {
    "fbclid",
    "gclid",
    "igshid",
    "mc_cid",
    "mc_eid",
    "ref",
    "spm",
}


def _canonical_url_key(url: str) -> str:
    raw = str(url or "").strip()
    if not raw:
        return ""
    parsed = urlsplit(raw)
    if not parsed.scheme or not parsed.netloc:
        return raw.rstrip("/")

    netloc = parsed.netloc.casefold()
    if netloc.startswith("www."):
        netloc = netloc.removeprefix("www.")
    path = parsed.path.rstrip("/") or "/"
    query = _canonical_query(parsed.query)
    return urlunsplit(("https", netloc, path, query, ""))


def _canonical_query(query: str) -> str:
    kept: list[tuple[str, str]] = []
    for key, value in parse_qsl(query, keep_blank_values=True):
        normalized_key = key.casefold()
        if normalized_key.startswith("utm_") or normalized_key in _TRACKING_QUERY_KEYS:
            continue
        kept.append((key, value))
    return urlencode(sorted(kept))


__all__ = [
    "TrustedSeedCandidate",
    "WebResearchQueryPlan",
    "apply_query_plan_to_search_results",
    "build_web_research_query_plan",
]
