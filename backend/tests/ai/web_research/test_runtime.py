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
async def test_runtime_skips_search_wrapper_candidate_without_fetching() -> None:
    """
    Test type: behavioral
    中文: 回归保护 BUG-2026-05-05-2295，WebResearch 不应抓取搜索包装页。
    EN: Regression for BUG-2026-05-05-2295; WebResearch must not fetch search wrappers.
    """

    events: list[str] = []
    baidu_image_url = (
        "https://image.baidu.com/search/index?tn=baiduimage&word="
        "2026%E5%A5%B3%E6%80%A7%E8%A3%99%E5%AD%90"
    )

    def search_handler(query: str, options: SearchOptions) -> SearchResultSet:
        return SearchResultSet(
            query=query,
            provider="fake-search",
            items=[
                normalize_search_item(
                    title="查一下 2026年最热门的 女性裙子款式排行! - 百度图片",
                    url=baidu_image_url,
                    snippet="9 变清晰 4 变清晰 查看全部4341张图片 免费AI生图 百度图片",
                    rank=1,
                    provider="fake-search",
                )
            ],
        )

    def fetch_handler(url: str, options: FetchOptions) -> object:
        raise AssertionError(f"search wrapper URL should not be fetched: {url}")

    runtime = WebResearchRuntime(
        search_provider=FakeSearchProvider(events, search_handler),
        fetch_provider=FakeFetchProvider(events, fetch_handler),
    )

    evidence = await runtime.run(
        "查一下 2026年最热门的 女性裙子款式排行！",
        WebResearchRunOptions(pipeline_id="pipeline-2295-search-wrapper"),
    )

    assert events == ["search:查一下 2026年最热门的 女性裙子款式排行！:max=5"]
    assert evidence.status == "partial"
    assert evidence.answer_quality == "none"
    assert evidence.failure_kind == "candidate_search_wrapper_url"
    assert evidence.diagnostics.candidate_urls == []
    assert evidence.diagnostics.fetched_urls == []
    assert evidence.diagnostics.answer_source == "none"
    assert evidence.fetched_pages[0].status == "skipped"
    assert evidence.fetched_pages[0].failure_kind == "candidate_search_wrapper_url"
    assert evidence.diagnostics.raw["skipped_candidates"] == [
        {
            "url": baidu_image_url,
            "rank": 1,
            "provider": "fake-search",
            "reason": "search_wrapper_url",
        }
    ]


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


@pytest.mark.asyncio
async def test_runtime_fetches_llm_leaderboard_trusted_seed_before_noisy_search_hit() -> (
    None
):
    # behavioral: the runtime must apply query planning before fetch candidate
    # selection, so the trusted seed is the first fetched URL for this prompt.
    events: list[str] = []

    def search_handler(query: str, options: SearchOptions) -> SearchResultSet:
        return SearchResultSet(
            query=query,
            provider="public-search",
            items=[
                normalize_search_item(
                    title="大模型排行榜被投毒了吗",
                    url="https://baijiahao.baidu.com/s?id=noisy-315",
                    snippet="3·15 广告监管 黑产 软文 信息操控，不是模型榜单。",
                    rank=1,
                    provider="public-search",
                ),
                normalize_search_item(
                    title="Artificial Analysis duplicate",
                    url="https://artificialanalysis.ai/leaderboards/models",
                    snippet="Duplicate public-search result for the trusted seed.",
                    rank=2,
                    provider="public-search",
                ),
            ],
        )

    def fetch_handler(url: str, options: FetchOptions) -> object:
        return normalize_page_evidence(
            url=url,
            status="completed",
            title="Artificial Analysis LLM Leaderboard",
            body_text=(
                "2026 AI model leaderboard ranking GPT Claude Gemini DeepSeek "
                "Qwen with benchmark score and intelligence index results. "
                "#1 GPT #2 Claude #3 Gemini."
            ),
            summary="",
            description="",
            provider="fake-fetch",
        )

    runtime = WebResearchRuntime(
        search_provider=FakeSearchProvider(events, search_handler),
        fetch_provider=FakeFetchProvider(events, fetch_handler),
    )

    evidence = await runtime.run(
        "大模型排行榜 2026",
        WebResearchRunOptions(pipeline_id="pipeline-llm-leaderboard", max_fetches=1),
    )

    assert events == [
        "search:大模型排行榜 2026:max=5",
        "fetch:https://artificialanalysis.ai/leaderboards/models",
    ]
    trusted_urls = evidence.diagnostics.raw["trusted_seed_candidate_urls"]
    search_urls = [item.url for item in evidence.search_results]
    assert trusted_urls[0] == "https://artificialanalysis.ai/leaderboards/models"
    assert "https://lmarena.ai/leaderboard" in trusted_urls
    assert search_urls[: len(trusted_urls)] == trusted_urls
    assert search_urls.index("https://baijiahao.baidu.com/s?id=noisy-315") >= len(
        trusted_urls
    )
    assert [item.rank for item in evidence.search_results] == list(
        range(1, len(evidence.search_results) + 1)
    )
    assert evidence.diagnostics.candidate_urls[: len(trusted_urls)] == trusted_urls
    assert evidence.diagnostics.fetched_urls == [
        "https://artificialanalysis.ai/leaderboards/models"
    ]
    assert evidence.diagnostics.raw["query_profile"] == "llm_leaderboard"
    assert evidence.diagnostics.raw["minimum_relevant_sources"] == 2
    assert (
        evidence.diagnostics.raw["source_quality_floor"]
        == "trusted_leaderboard_or_relevant_benchmark"
    )


@pytest.mark.asyncio
async def test_runtime_max_fetches_one_uses_canonical_seed_before_url_variants() -> (
    None
):
    # behavioral: even when public-search ranks low-trust noise first and later
    # returns tracked trusted duplicates, max_fetches=1 must fetch the canonical
    # Artificial Analysis seed rather than Baijiahao or a duplicate variant.
    events: list[str] = []

    def search_handler(query: str, options: SearchOptions) -> SearchResultSet:
        return SearchResultSet(
            query=query,
            provider="public-search",
            items=[
                normalize_search_item(
                    title="大模型榜单软文",
                    url="https://baijiahao.baidu.com/s?id=noisy-315",
                    snippet="广告监管、信息操控、GEO营销，不是可核实能力榜单。",
                    rank=1,
                    provider="public-search",
                ),
                normalize_search_item(
                    title="Artificial Analysis tracking duplicate",
                    url="https://www.artificialanalysis.ai/leaderboards/models/?utm_source=search#models",
                    snippet="Duplicate tracked trusted result.",
                    rank=2,
                    provider="public-search",
                ),
                normalize_search_item(
                    title="LMArena http duplicate",
                    url="http://lmarena.ai/leaderboard?utm_campaign=rankings",
                    snippet="Duplicate tracked arena result.",
                    rank=3,
                    provider="public-search",
                ),
            ],
        )

    def fetch_handler(url: str, options: FetchOptions) -> object:
        return normalize_page_evidence(
            url=url,
            status="completed",
            title="Artificial Analysis LLM Leaderboard",
            body_text=(
                "2026 AI model leaderboard ranking GPT Claude Gemini DeepSeek "
                "Qwen with benchmark score and intelligence index results. "
                "#1 GPT #2 Claude #3 Gemini."
            ),
            summary="",
            description="",
            provider="fake-fetch",
        )

    runtime = WebResearchRuntime(
        search_provider=FakeSearchProvider(events, search_handler),
        fetch_provider=FakeFetchProvider(events, fetch_handler),
    )

    evidence = await runtime.run(
        "查一下大模型排行榜 2026 水平排行！",
        WebResearchRunOptions(pipeline_id="pipeline-llm-variant", max_fetches=1),
    )

    trusted_urls = evidence.diagnostics.raw["trusted_seed_candidate_urls"]
    assert events == [
        "search:查一下大模型排行榜 2026 水平排行！:max=5",
        "fetch:https://artificialanalysis.ai/leaderboards/models",
    ]
    assert evidence.diagnostics.candidate_urls[: len(trusted_urls)] == trusted_urls
    assert "https://baijiahao.baidu.com/s?id=noisy-315" in (
        evidence.diagnostics.candidate_urls
    )
    assert evidence.diagnostics.fetched_urls == [
        "https://artificialanalysis.ai/leaderboards/models"
    ]
    assert not any(
        "utm_" in item.url or "#" in item.url for item in evidence.search_results
    )
    assert not any(item.url.startswith("http://") for item in evidence.search_results)
    assert not any(
        "www.artificialanalysis.ai" in item.url for item in evidence.search_results
    )


@pytest.mark.asyncio
async def test_runtime_fetches_two_relevant_llm_leaderboard_sources_before_stopping() -> (
    None
):
    # behavioral: leaderboard queries need more than one authority when the
    # plan requires two relevant sources; the runtime should not stop after the
    # first fetched body for this profile.
    events: list[str] = []

    def search_handler(query: str, options: SearchOptions) -> SearchResultSet:
        return SearchResultSet(
            query=query,
            provider="public-search",
            items=[
                normalize_search_item(
                    title="Weak public-search result",
                    url="https://baijiahao.baidu.com/s?id=noisy-315",
                    snippet="GEO营销、广告监管、token调用量和信息操控，不是能力榜单。",
                    rank=1,
                    provider="public-search",
                )
            ],
        )

    def fetch_handler(url: str, options: FetchOptions) -> object:
        if "lmarena.ai" in url:
            return normalize_page_evidence(
                url=url,
                status="completed",
                title="Arena Leaderboard",
                body_text=(
                    "AI model ranking leaderboard with Claude Gemini GPT Grok "
                    "and Qwen scores. 1. Claude 2. Gemini 3. GPT."
                ),
                summary="Arena leaderboard ranking frontier AI models",
                description="",
                provider="fake-fetch",
            )
        return normalize_page_evidence(
            url=url,
            status="completed",
            title="Artificial Analysis LLM Leaderboard",
            body_text=(
                "2026 AI model leaderboard ranking GPT Claude Gemini DeepSeek "
                "Qwen with benchmark score and intelligence index results. "
                "#1 GPT #2 Claude #3 Gemini."
            ),
            summary="Artificial Analysis ranks frontier AI models",
            description="",
            provider="fake-fetch",
        )

    runtime = WebResearchRuntime(
        search_provider=FakeSearchProvider(events, search_handler),
        fetch_provider=FakeFetchProvider(events, fetch_handler),
    )

    evidence = await runtime.run(
        "大模型排行榜 2026",
        WebResearchRunOptions(pipeline_id="pipeline-llm-leaderboard-2", max_fetches=3),
    )

    trusted_urls = evidence.diagnostics.raw["trusted_seed_candidate_urls"]
    assert events[:2] == [
        "search:大模型排行榜 2026:max=5",
        "fetch:https://artificialanalysis.ai/leaderboards/models",
    ]
    assert events[2].removeprefix("fetch:") in trusted_urls
    assert "fetch:https://baijiahao.baidu.com/s?id=noisy-315" not in events[:3]
    assert evidence.status == "completed"
    assert len(evidence.diagnostics.fetched_urls) == 2
    assert evidence.diagnostics.fetched_urls[0] == (
        "https://artificialanalysis.ai/leaderboards/models"
    )
    assert set(evidence.diagnostics.fetched_urls).issubset(set(trusted_urls))
    assert [citation.url for citation in evidence.citations] == (
        evidence.diagnostics.fetched_urls
    )
    assert evidence.diagnostics.raw["minimum_relevant_sources"] == 2


@pytest.mark.asyncio
async def test_runtime_cross_checks_two_relevant_llm_leaderboard_sources() -> None:
    # behavioral: default leaderboard research should not stop at the first
    # relevant page when the query plan requires two independent sources.
    events: list[str] = []

    def search_handler(query: str, options: SearchOptions) -> SearchResultSet:
        return SearchResultSet(
            query=query,
            provider="public-search",
            items=[
                normalize_search_item(
                    title="大模型榜单软文",
                    url="https://baijiahao.baidu.com/s?id=noisy-315",
                    snippet="广告监管、信息操控、GEO营销，不是可核实能力榜单。",
                    rank=1,
                    provider="public-search",
                )
            ],
        )

    def fetch_handler(url: str, options: FetchOptions) -> object:
        if "artificialanalysis.ai" in url:
            return normalize_page_evidence(
                url=url,
                status="completed",
                title="Artificial Analysis LLM Leaderboard",
                body_text=(
                    "LLM leaderboard benchmark score intelligence index ranks "
                    "GPT Claude Gemini DeepSeek Qwen. #1 GPT #2 Claude."
                ),
                summary="",
                description="",
                provider="fake-fetch",
            )
        if "lmarena.ai" in url:
            return normalize_page_evidence(
                url=url,
                status="completed",
                title="Arena Leaderboard",
                body_text=(
                    "Arena leaderboard benchmark score for frontier language "
                    "models GPT Claude Gemini DeepSeek Qwen. #1 Claude #2 GPT."
                ),
                summary="",
                description="",
                provider="fake-fetch",
            )
        return normalize_page_evidence(
            url=url,
            status="completed",
            title="Noisy article",
            body_text="3·15 广告监管 信息操控 黑产 token消耗 恐慌。",
            summary="",
            description="",
            provider="fake-fetch",
        )

    runtime = WebResearchRuntime(
        search_provider=FakeSearchProvider(events, search_handler),
        fetch_provider=FakeFetchProvider(events, fetch_handler),
    )

    evidence = await runtime.run(
        "查一下大模型排行榜 2026 水平排行！",
        WebResearchRunOptions(pipeline_id="pipeline-llm-cross-check"),
    )

    trusted_urls = evidence.diagnostics.raw["trusted_seed_candidate_urls"]
    assert events[:2] == [
        "search:查一下大模型排行榜 2026 水平排行！:max=5",
        "fetch:https://artificialanalysis.ai/leaderboards/models",
    ]
    assert events[2].removeprefix("fetch:") in trusted_urls
    assert "fetch:https://baijiahao.baidu.com/s?id=noisy-315" not in events[:3]
    assert evidence.status == "completed"
    assert evidence.answer_quality == "body"
    assert len(evidence.diagnostics.fetched_urls) == 2
    assert evidence.diagnostics.fetched_urls[0] == (
        "https://artificialanalysis.ai/leaderboards/models"
    )
    assert set(evidence.diagnostics.fetched_urls).issubset(set(trusted_urls))
    assert [citation.url for citation in evidence.citations] == (
        evidence.diagnostics.fetched_urls
    )
    assert evidence.diagnostics.raw["minimum_relevant_sources"] == 2
