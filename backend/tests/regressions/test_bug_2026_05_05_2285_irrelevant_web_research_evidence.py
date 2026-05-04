"""
Test type: behavioral
Regression for: BUG-2026-05-05-2285
Original symptom: conversation 2285 marked WebResearch evidence as completed
after fetching an irrelevant Baijiahao article for "大模型排行榜 2026".
Scope: WebResearchRuntime search -> query planning -> fetch -> relevance gate -> evidence status.
Mock strategy: fake providers replace external network only; the real runtime,
query planner, candidate iteration, relevance gate, and evidence builder make the decision.
"""

from collections.abc import Callable

import pytest

from app.ai.web_research import (
    FetchOptions,
    SearchOptions,
    SearchResultSet,
    WebResearchRunOptions,
    WebResearchRuntime,
    normalize_page_evidence,
    normalize_search_item,
)


class FakeSearchProvider:
    provider_id = "fake-search"

    def __init__(self, handler: Callable[[str, SearchOptions], SearchResultSet]):
        self._handler = handler

    async def search(self, query: str, options: SearchOptions) -> SearchResultSet:
        return self._handler(query, options)


class FakeFetchProvider:
    provider_id = "fake-fetch"

    def __init__(self, handler: Callable[[str, FetchOptions], object]):
        self.events: list[str] = []
        self._handler = handler

    async def fetch(self, url: str, options: FetchOptions) -> object:
        self.events.append(url)
        return self._handler(url, options)


def _search_results(query: str) -> SearchResultSet:
    return SearchResultSet(
        query=query,
        provider="fake-search",
        items=[
            normalize_search_item(
                title="2026大模型创新TOP100",
                url="https://baijiahao.baidu.com/s?id=1860091565873698107",
                snippet="AI信息操控、3·15、OpenClaw、token调用量、GEO营销文章。",
                rank=1,
                provider="fake-search",
            ),
            normalize_search_item(
                title="Artificial Analysis LLM Leaderboard 2026",
                url="https://artificialanalysis.ai/leaderboards/models",
                snippet="LLM leaderboard ranking with model scores for Gemini, GPT, Claude and DeepSeek.",
                rank=2,
                provider="fake-search",
            ),
        ],
    )


def _irrelevant_2285_page(url: str):
    return normalize_page_evidence(
        url=url,
        status="completed",
        title="2026大模型创新TOP100",
        body_text=(
            "（来源：DBC德本咨询）AI信息操控。3·15晚会曝光AI大模型投毒黑产，"
            "GEO服务商通过软文影响AI推荐。文章随后讨论OpenClaw、token调用量、"
            "个人用户消费和安全风险，并没有给出大模型能力排行榜或评测分数。"
        ),
        summary="2026大模型创新TOP100",
        description="",
        provider="fake-fetch",
    )


def _leaderboard_page(url: str):
    return normalize_page_evidence(
        url=url,
        status="completed",
        title="Artificial Analysis LLM Leaderboard 2026",
        body_text=(
            "Artificial Analysis LLM leaderboard 2026 ranks frontier models by "
            "quality index, intelligence score, reasoning and coding benchmarks. "
            "1. Gemini 3 Pro score 74. 2. GPT-5.5 score 73. "
            "3. Claude Opus 5 score 71. 4. DeepSeek V3.2 score 68."
        ),
        summary="2026 LLM leaderboard with benchmark scores",
        description="",
        provider="fake-fetch",
    )


@pytest.mark.asyncio
async def test_2285_prioritizes_trusted_candidates_before_noisy_public_hit() -> None:
    query = "查一下大模型排行榜 2026  水平排行！"

    def fetch_handler(url: str, options: FetchOptions) -> object:
        if "baijiahao" in url:
            return _irrelevant_2285_page(url)
        return _leaderboard_page(url)

    fetch_provider = FakeFetchProvider(fetch_handler)
    runtime = WebResearchRuntime(
        search_provider=FakeSearchProvider(
            lambda query, _options: _search_results(query)
        ),
        fetch_provider=fetch_provider,
    )

    evidence = await runtime.run(
        query,
        WebResearchRunOptions(pipeline_id="bug-2285", max_fetches=3),
    )

    assert fetch_provider.events == [
        "https://artificialanalysis.ai/leaderboards/models",
        "https://lmarena.ai/leaderboard",
    ]
    assert evidence.status == "completed"
    assert evidence.answer_quality == "body"
    assert evidence.failure_kind is None
    assert [page.url for page in evidence.fetched_pages] == [
        "https://artificialanalysis.ai/leaderboards/models",
        "https://lmarena.ai/leaderboard",
    ]
    assert [page.status for page in evidence.fetched_pages] == ["completed", "completed"]
    assert evidence.diagnostics.fetched_urls == [
        "https://artificialanalysis.ai/leaderboards/models",
        "https://lmarena.ai/leaderboard",
    ]
    assert evidence.diagnostics.answer_source == "fetched_body"
    assert [citation.url for citation in evidence.citations] == [
        "https://artificialanalysis.ai/leaderboards/models",
        "https://lmarena.ai/leaderboard",
    ]


@pytest.mark.asyncio
async def test_2285_low_relevance_only_never_completes_as_fetched_body_answer() -> None:
    query = "查一下大模型排行榜 2026  水平排行！"
    fetch_provider = FakeFetchProvider(lambda url, _options: _irrelevant_2285_page(url))
    runtime = WebResearchRuntime(
        search_provider=FakeSearchProvider(
            lambda query, _options: _search_results(query)
        ),
        fetch_provider=fetch_provider,
    )

    evidence = await runtime.run(
        query,
        WebResearchRunOptions(pipeline_id="bug-2285-low-only", max_fetches=1),
    )

    assert fetch_provider.events == [
        "https://artificialanalysis.ai/leaderboards/models"
    ]
    assert evidence.status == "partial"
    assert evidence.answer_quality == "none"
    assert evidence.failure_kind == "low_query_relevance"
    assert evidence.fetched_pages[0].url == (
        "https://artificialanalysis.ai/leaderboards/models"
    )
    assert evidence.fetched_pages[0].failure_kind == "low_query_relevance"
    assert evidence.diagnostics.answer_source == "none"
    assert evidence.diagnostics.fetched_urls == []
    assert evidence.citations == []
