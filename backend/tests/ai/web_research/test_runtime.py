"""
Test type: behavioral
Scope: WebResearchRuntime search -> fetch -> evidence progression.
Mock strategy: fake providers implement the public provider contracts. They do
not return asserted evidence; tests assert runtime ordering, candidate choice,
diagnostics, quality normalization, and failure projection.
"""

from collections.abc import Callable

import pytest

from app.ai.web_research import (
    FetchOptions,
    SearchOptions,
    SearchResultSet,
    WebResearchProviderRouter,
    WebResearchRunOptions,
    WebResearchRuntime,
    normalize_page_evidence,
    normalize_search_item,
)


class FakeSearchProvider:
    provider_id = "fake-search"

    def __init__(
        self,
        events: list[str],
        handler: Callable[[str, SearchOptions], SearchResultSet],
        provider_id: str = "fake-search",
    ) -> None:
        self._events = events
        self._handler = handler
        self.provider_id = provider_id

    async def search(self, query: str, options: SearchOptions) -> SearchResultSet:
        self._events.append(f"search:{query}:max={options.max_results}")
        return self._handler(query, options)


class FakeFetchProvider:
    provider_id = "fake-fetch"

    def __init__(
        self,
        events: list[str],
        handler: Callable[[str, FetchOptions], object],
        provider_id: str = "fake-fetch",
    ) -> None:
        self._events = events
        self._handler = handler
        self.provider_id = provider_id

    async def fetch(self, url: str, options: FetchOptions) -> object:
        self._events.append(f"fetch:{url}")
        result = self._handler(url, options)
        if isinstance(result, Exception):
            raise result
        return result


@pytest.mark.asyncio
async def test_runtime_fetches_primary_ranked_candidate_after_search() -> None:
    events: list[str] = []

    def search_handler(query: str, options: SearchOptions) -> SearchResultSet:
        return SearchResultSet(
            query=query,
            provider="fake-search",
            items=[
                normalize_search_item(
                    title="Second",
                    url="https://example.com/second",
                    snippet="Second snippet",
                    rank=2,
                    provider="fake-search",
                ),
                normalize_search_item(
                    title="First",
                    url="https://example.com/first",
                    snippet="First snippet",
                    rank=1,
                    provider="fake-search",
                ),
            ],
        )

    def fetch_handler(url: str, options: FetchOptions) -> object:
        return normalize_page_evidence(
            url=url,
            status="completed",
            title="Fetched primary",
            body_text=f"Body for {url}",
            summary="",
            description="",
            provider="fake-fetch",
        )

    runtime = WebResearchRuntime(
        search_provider=FakeSearchProvider(events, search_handler),
        fetch_provider=FakeFetchProvider(events, fetch_handler),
    )

    evidence = await runtime.run(
        "ranked query",
        WebResearchRunOptions(pipeline_id="pipeline-behavioral", max_fetches=1),
    )

    assert events == [
        "search:ranked query:max=5",
        "fetch:https://example.com/first",
    ]
    assert evidence.status == "completed"
    assert evidence.answer_quality == "body"
    assert evidence.search_provider == "fake-search"
    assert evidence.fetch_provider == "fake-fetch"
    assert evidence.diagnostics.candidate_urls == [
        "https://example.com/first",
        "https://example.com/second",
    ]
    assert evidence.diagnostics.fetched_urls == ["https://example.com/first"]
    assert evidence.diagnostics.answer_source == "fetched_body"
    assert evidence.citations[0].url == "https://example.com/first"


@pytest.mark.asyncio
async def test_runtime_router_records_disabled_optional_provider_reason() -> None:
    events: list[str] = []

    def default_search_handler(
        query: str,
        options: SearchOptions,
    ) -> SearchResultSet:
        return SearchResultSet(
            query=query,
            provider="default-search",
            items=[
                normalize_search_item(
                    title="Default result",
                    url="https://example.com/default",
                    snippet="Default snippet",
                    rank=1,
                    provider="default-search",
                )
            ],
        )

    def disabled_search_handler(
        query: str,
        options: SearchOptions,
    ) -> SearchResultSet:
        return SearchResultSet(query=query, provider="hosted-search")

    def fetch_handler(url: str, options: FetchOptions) -> object:
        return normalize_page_evidence(
            url=url,
            status="completed",
            title="Fetched default",
            body_text="Fetched body",
            summary="",
            description="",
            provider="default-fetch",
        )

    router = WebResearchProviderRouter(
        search_providers={
            "default-search": FakeSearchProvider(
                events,
                default_search_handler,
                provider_id="default-search",
            ),
            "hosted-search": FakeSearchProvider(
                events,
                disabled_search_handler,
                provider_id="hosted-search",
            ),
        },
        fetch_providers={
            "default-fetch": FakeFetchProvider(
                events,
                fetch_handler,
                provider_id="default-fetch",
            ),
        },
        default_search_provider_id="default-search",
        default_fetch_provider_id="default-fetch",
        disabled_search_providers={
            "hosted-search": "openai_compatible_hosted_search_disabled_by_default",
        },
    )
    runtime = WebResearchRuntime(provider_router=router)

    evidence = await runtime.run(
        "provider routing",
        WebResearchRunOptions(
            pipeline_id="pipeline-router",
            search_provider_id="hosted-search",
        ),
    )

    assert events == [
        "search:provider routing:max=5",
        "fetch:https://example.com/default",
    ]
    assert evidence.search_provider == "default-search"
    assert evidence.diagnostics.provider_disable_reason == (
        "openai_compatible_hosted_search_disabled_by_default"
    )
    assert evidence.diagnostics.raw["requested_search_provider"] == "hosted-search"
    assert evidence.diagnostics.raw["selected_search_provider"] == "default-search"


@pytest.mark.asyncio
async def test_runtime_records_fetch_failure_as_partial_evidence() -> None:
    events: list[str] = []

    def search_handler(query: str, options: SearchOptions) -> SearchResultSet:
        return SearchResultSet(
            query=query,
            provider="fake-search",
            items=[
                normalize_search_item(
                    title="Candidate",
                    url="https://example.com/fail",
                    snippet="Candidate snippet",
                    rank=1,
                    provider="fake-search",
                )
            ],
        )

    def fetch_handler(url: str, options: FetchOptions) -> object:
        return RuntimeError(f"fetch failed for {url}")

    runtime = WebResearchRuntime(
        search_provider=FakeSearchProvider(events, search_handler),
        fetch_provider=FakeFetchProvider(events, fetch_handler),
    )

    evidence = await runtime.run(
        "fetch failure",
        WebResearchRunOptions(pipeline_id="pipeline-fetch-failure"),
    )

    assert events == ["search:fetch failure:max=5", "fetch:https://example.com/fail"]
    assert evidence.status == "partial"
    assert evidence.answer_quality == "none"
    assert evidence.failure_kind == "fetch_exception"
    assert evidence.fetched_pages[0].status == "failed"
    assert evidence.fetched_pages[0].failure_kind == "fetch_exception"
    assert evidence.diagnostics.fetched_urls == []
    assert evidence.diagnostics.failure_kind == "fetch_exception"


@pytest.mark.asyncio
async def test_runtime_does_not_fetch_when_search_provider_fails() -> None:
    events: list[str] = []

    def search_handler(query: str, options: SearchOptions) -> SearchResultSet:
        raise RuntimeError("search backend down")

    def fetch_handler(url: str, options: FetchOptions) -> object:
        return normalize_page_evidence(
            url=url,
            status="completed",
            title="Should not run",
            body_text="Should not run",
            summary="",
            description="",
            provider="fake-fetch",
        )

    runtime = WebResearchRuntime(
        search_provider=FakeSearchProvider(events, search_handler),
        fetch_provider=FakeFetchProvider(events, fetch_handler),
    )

    evidence = await runtime.run(
        "search failure",
        WebResearchRunOptions(pipeline_id="pipeline-search-failure"),
    )

    assert events == ["search:search failure:max=5"]
    assert evidence.status == "failed"
    assert evidence.failure_kind == "search_exception"
    assert evidence.search_results == []
    assert evidence.fetched_pages == []
    assert evidence.diagnostics.answer_source == "none"


@pytest.mark.asyncio
async def test_runtime_can_emit_snippet_quality_only_when_fetch_not_required() -> None:
    events: list[str] = []

    def search_handler(query: str, options: SearchOptions) -> SearchResultSet:
        return SearchResultSet(
            query=query,
            provider="fake-search",
            items=[
                normalize_search_item(
                    title="Snippet source",
                    url="https://example.com/snippet",
                    snippet="Snippet evidence",
                    rank=1,
                    provider="fake-search",
                    allow_snippet_quality=options.allow_snippet_quality,
                )
            ],
        )

    def fetch_handler(url: str, options: FetchOptions) -> object:
        return normalize_page_evidence(
            url=url,
            status="completed",
            title="Should not run",
            body_text="Should not run",
            summary="",
            description="",
            provider="fake-fetch",
        )

    runtime = WebResearchRuntime(
        search_provider=FakeSearchProvider(events, search_handler),
        fetch_provider=FakeFetchProvider(events, fetch_handler),
    )

    evidence = await runtime.run(
        "snippet only",
        WebResearchRunOptions(
            pipeline_id="pipeline-snippet",
            require_fetch=False,
            max_fetches=0,
            allow_snippet_quality=True,
        ),
    )

    assert events == ["search:snippet only:max=5"]
    assert evidence.status == "completed"
    assert evidence.answer_quality == "snippet"
    assert evidence.diagnostics.answer_source == "search_snippet"
    assert evidence.citations[0].source == "search_result"
    assert evidence.citations[0].url == "https://example.com/snippet"


@pytest.mark.asyncio
async def test_runtime_projects_skipped_unsafe_candidate_before_fetching_next_url() -> (
    None
):
    events: list[str] = []

    def search_handler(query: str, options: SearchOptions) -> SearchResultSet:
        return SearchResultSet(
            query=query,
            provider="fake-search",
            items=[
                normalize_search_item(
                    title="Unsafe",
                    url="ftp://example.com/file",
                    snippet="Unsafe candidate",
                    rank=1,
                    provider="fake-search",
                ),
                normalize_search_item(
                    title="Fetchable",
                    url="https://example.com/fetchable",
                    snippet="Fetchable candidate",
                    rank=2,
                    provider="fake-search",
                ),
            ],
        )

    def fetch_handler(url: str, options: FetchOptions) -> object:
        return normalize_page_evidence(
            url=url,
            status="completed",
            title="Fetched",
            body_text="Fetched body",
            summary="",
            description="",
            provider="fake-fetch",
        )

    runtime = WebResearchRuntime(
        search_provider=FakeSearchProvider(events, search_handler),
        fetch_provider=FakeFetchProvider(events, fetch_handler),
    )

    evidence = await runtime.run(
        "unsafe candidate",
        WebResearchRunOptions(pipeline_id="pipeline-skipped"),
    )

    assert events == [
        "search:unsafe candidate:max=5",
        "fetch:https://example.com/fetchable",
    ]
    assert evidence.status == "completed"
    assert evidence.answer_quality == "body"
    assert evidence.fetched_pages[0].status == "skipped"
    assert evidence.fetched_pages[0].failure_kind == "candidate_unsupported_scheme"
    assert evidence.fetched_pages[1].url == "https://example.com/fetchable"
    assert evidence.diagnostics.raw["skipped_candidates"] == [
        {
            "url": "ftp://example.com/file",
            "rank": 1,
            "provider": "fake-search",
            "reason": "unsupported_scheme",
        }
    ]
