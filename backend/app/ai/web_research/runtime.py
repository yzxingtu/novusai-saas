"""
Platform-owned WebResearch runtime.
"""

from __future__ import annotations

from itertools import count

from app.ai.web_research.contracts import (
    FetchOptions,
    FetchProvider,
    SearchOptions,
    SearchProvider,
    WebResearchRunOptions,
)
from app.ai.web_research.evidence import (
    PageEvidence,
    SearchResultSet,
    WebResearchEvidence,
)
from app.ai.web_research.normalization import (
    build_web_research_evidence,
    normalize_page_evidence,
)
from app.ai.web_research.query_planning import (
    apply_query_plan_to_search_results,
    build_web_research_query_plan,
)
from app.ai.web_research.relevance import apply_page_relevance_gate
from app.ai.web_research.routing import WebResearchProviderRouter
from app.ai.web_research.selection import (
    FetchCandidateSelection,
    SkippedFetchCandidate,
    select_fetch_candidates,
)

_PIPELINE_COUNTER = count(1)


class WebResearchRuntime:
    def __init__(
        self,
        *,
        search_provider: SearchProvider | None = None,
        fetch_provider: FetchProvider | None = None,
        provider_router: WebResearchProviderRouter | None = None,
    ) -> None:
        if provider_router is None:
            if search_provider is None or fetch_provider is None:
                raise ValueError(
                    "WebResearchRuntime requires either provider_router or both "
                    "search_provider and fetch_provider"
                )
            provider_router = WebResearchProviderRouter.from_providers(
                search_provider=search_provider,
                fetch_provider=fetch_provider,
            )
        self._provider_router = provider_router

    async def run(
        self,
        query: str,
        options: WebResearchRunOptions | None = None,
    ) -> WebResearchEvidence:
        run_options = options or WebResearchRunOptions()
        pipeline_id = run_options.pipeline_id or _next_pipeline_id()
        search_resolution = self._provider_router.resolve_search_provider(
            run_options.search_provider_id
        )
        fetch_resolution = self._provider_router.resolve_fetch_provider(
            run_options.fetch_provider_id
        )
        search_provider = search_resolution.provider
        fetch_provider = fetch_resolution.provider
        search_results = await self._search(query, run_options, search_provider)
        candidate_selection = select_fetch_candidates(
            search_results,
            max_fetches=run_options.max_fetches,
            require_fetch=run_options.require_fetch,
        )
        fetched_pages = await self._fetch_candidates(
            query,
            search_results,
            candidate_selection,
            run_options,
            fetch_provider,
        )
        provider_disable_reason = (
            run_options.provider_disable_reason
            or search_resolution.disable_reason
            or fetch_resolution.disable_reason
        )
        return build_web_research_evidence(
            query=query,
            search_results=search_results,
            fetched_pages=fetched_pages,
            fetch_provider=fetch_provider.provider_id,
            pipeline_id=pipeline_id,
            candidate_urls=candidate_selection.candidate_urls,
            require_fetch=run_options.require_fetch,
            provider_disable_reason=provider_disable_reason,
            raw_diagnostics={
                **dict(run_options.diagnostics),
                **_query_plan_diagnostics(search_results),
                "requested_search_provider": search_resolution.requested_provider_id,
                "selected_search_provider": search_resolution.selected_provider_id,
                "requested_fetch_provider": fetch_resolution.requested_provider_id,
                "selected_fetch_provider": fetch_resolution.selected_provider_id,
                "skipped_candidates": [
                    {
                        "url": skipped.url,
                        "rank": skipped.rank,
                        "provider": skipped.provider,
                        "reason": skipped.reason,
                    }
                    for skipped in candidate_selection.skipped
                ],
            },
        )

    async def _search(
        self,
        query: str,
        options: WebResearchRunOptions,
        search_provider: SearchProvider,
    ) -> SearchResultSet:
        query_plan = build_web_research_query_plan(query)
        try:
            search_results = await search_provider.search(
                query,
                SearchOptions(
                    max_results=options.max_search_results,
                    allow_snippet_quality=options.allow_snippet_quality,
                    diagnostics=options.diagnostics,
                ),
            )
            return apply_query_plan_to_search_results(
                search_results,
                plan=query_plan,
            )
        except Exception as exc:
            search_results = SearchResultSet(
                query=query,
                provider=search_provider.provider_id,
                status="failed",
                failure_kind="search_exception",
                diagnostics={"error": str(exc)},
            )
            return apply_query_plan_to_search_results(
                search_results,
                plan=query_plan,
            )

    async def _fetch_candidates(
        self,
        query: str,
        search_results: SearchResultSet,
        candidate_selection: FetchCandidateSelection,
        options: WebResearchRunOptions,
        fetch_provider: FetchProvider,
    ) -> list[PageEvidence]:
        pages = _skipped_pages(candidate_selection.skipped, fetch_provider.provider_id)
        if not candidate_selection.selected_urls:
            return pages

        minimum_relevant_sources = _minimum_relevant_sources(search_results)
        relevant_source_count = 0
        search_items_by_url = {
            item.url.strip(): item for item in search_results.items if item.url.strip()
        }
        for url in candidate_selection.selected_urls:
            try:
                page = await fetch_provider.fetch(
                    url,
                    FetchOptions(diagnostics=options.diagnostics),
                )
            except Exception as exc:
                page = normalize_page_evidence(
                    url=url,
                    status="failed",
                    title="",
                    body_text="",
                    summary="",
                    description="",
                    provider=fetch_provider.provider_id,
                    failure_kind="fetch_exception",
                    raw={"error": str(exc)},
                )
            page = apply_page_relevance_gate(
                query=query,
                page=page,
                search_item=search_items_by_url.get(url),
            )
            pages.append(page)
            if page.status == "completed" and page.answer_quality != "none":
                relevant_source_count += 1
                if relevant_source_count >= minimum_relevant_sources:
                    break
        return pages


def _skipped_pages(
    skipped_candidates: list[SkippedFetchCandidate],
    fetch_provider_id: str,
) -> list[PageEvidence]:
    return [
        normalize_page_evidence(
            url=skipped.url,
            status="skipped",
            title=skipped.title,
            body_text="",
            summary="",
            description="",
            provider=fetch_provider_id,
            failure_kind=f"candidate_{skipped.reason}",
            raw={
                "rank": skipped.rank,
                "provider": skipped.provider,
                "reason": skipped.reason,
            },
        )
        for skipped in skipped_candidates
        if skipped.url and skipped.reason == "unsupported_scheme"
    ]


def _next_pipeline_id() -> str:
    return f"web-research-{next(_PIPELINE_COUNTER)}"


def _query_plan_diagnostics(search_results: SearchResultSet) -> dict[str, object]:
    diagnostics = dict(search_results.diagnostics or {})
    payload: dict[str, object] = {
        "search_diagnostics": diagnostics,
    }
    for key in (
        "query_profile",
        "trusted_seed_candidate_urls",
        "minimum_relevant_sources",
        "source_quality_floor",
    ):
        if key in diagnostics:
            payload[key] = diagnostics[key]
    return payload


def _minimum_relevant_sources(search_results: SearchResultSet) -> int:
    raw_value = dict(search_results.diagnostics or {}).get("minimum_relevant_sources")
    try:
        return max(1, int(raw_value or 1))
    except (TypeError, ValueError):
        return 1


__all__ = ["WebResearchRuntime"]
