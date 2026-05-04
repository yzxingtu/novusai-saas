"""
Test type: behavioral
Regression for: BUG-2026-05-05-2293
Original symptom: conversation 2293 rejected noisy public-search candidates for
"查一下大模型排行榜 2026 水平排行！" but then stopped instead of reaching a
trusted leaderboard source.
Scope: WebResearchRuntime query planning -> trusted candidate fetch -> relevance gate.
Mock strategy: fake providers replace external network only; the real runtime,
query planner, candidate selection, relevance gate, and evidence builder decide
whether trusted fetched evidence can complete the turn.
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
        self.queries: list[str] = []
        self._handler = handler

    async def search(self, query: str, options: SearchOptions) -> SearchResultSet:
        self.queries.append(query)
        return self._handler(query, options)


class FakeFetchProvider:
    provider_id = "fake-fetch"

    def __init__(self, handler: Callable[[str, FetchOptions], object]):
        self.events: list[str] = []
        self._handler = handler

    async def fetch(self, url: str, options: FetchOptions) -> object:
        self.events.append(url)
        return self._handler(url, options)


def _noisy_2293_search_results(query: str) -> SearchResultSet:
    return SearchResultSet(
        query=query,
        provider="fake-search",
        items=[
            normalize_search_item(
                title="2026大模型 创新TOP100",
                url="https://baijiahao.baidu.com/s?id=1860091565873698107",
                snippet=(
                    "2026年3月19日 token调用量前三、OpenClaw、GEO营销、"
                    "AI信息操控与安全风险。"
                ),
                rank=1,
                provider="fake-search",
            ),
            normalize_search_item(
                title="大型 模型 - 京东静态模型 TOP榜 广告",
                url="https://example.invalid/ads/static-model-top",
                snippet="京东模型玩具热销榜单，静态模型广告。",
                rank=2,
                provider="fake-search",
            ),
            normalize_search_item(
                title="大模型排行榜2026 年 - 知乎",
                url="https://example.invalid/zhihu/no-fetch",
                snippet="个人整理的排行榜，未提供可核实来源。",
                rank=3,
                provider="fake-search",
            ),
        ],
    )


def _artificial_analysis_page(url: str):
    return normalize_page_evidence(
        url=url,
        status="completed",
        title=(
            "LLM Leaderboard - Comparison of over 100 AI models from OpenAI, "
            "Google, DeepSeek & others"
        ),
        description=(
            "Comparison and ranking the performance of over 100 AI models "
            "(LLMs) across key metrics including intelligence, price, "
            "performance and speed."
        ),
        summary="LLM Leaderboard - model ranking and benchmark scores",
        body_text=(
            "Artificial Analysis LLM Leaderboard ranks frontier language models "
            "by intelligence index, quality index, pricing and speed. "
            "1. GPT-5.5 intelligence score 72. "
            "2. Gemini 3 Pro intelligence score 71. "
            "3. Claude Opus 4.6 intelligence score 69. "
            "4. DeepSeek V3.2 intelligence score 66. "
            "5. Qwen3 Max intelligence score 64."
        ),
        provider="fake-fetch",
    )


def _lmarena_page(url: str):
    return normalize_page_evidence(
        url=url,
        status="completed",
        title="Arena Leaderboard | Compare & Benchmark the Best Frontier AI Models",
        description="See how leading AI models stack up across text, code, vision, and more.",
        summary="Arena leaderboard compares frontier AI models by category and score",
        body_text=(
            "LMArena Arena Leaderboard ranks frontier AI models across text, "
            "code and multimodal arenas with benchmark scores. "
            "1. Claude Opus 4.7 thinking score 1503. "
            "2. Gemini 3.1 Pro score 1493. "
            "3. GPT-5.5 high score 1488. "
            "4. Grok 4.20 score 1480."
        ),
        provider="fake-fetch",
    )


def _noisy_or_blocked_page(url: str):
    if "baijiahao" in url:
        return normalize_page_evidence(
            url=url,
            status="completed",
            title="2026大模型 创新TOP100",
            body_text=(
                "AI信息操控、3·15、GEO营销、OpenClaw、token调用量和安全风险，"
                "没有可核实的大模型能力排行榜。"
            ),
            summary="AI投毒与GEO文章",
            description="",
            provider="fake-fetch",
        )
    return normalize_page_evidence(
        url=url,
        status="blocked",
        title="Blocked noisy candidate",
        body_text="",
        summary="",
        description="",
        provider="fake-fetch",
        failure_kind="blocked_url",
    )


@pytest.mark.asyncio
async def test_2293_llm_leaderboard_query_uses_trusted_authority_candidate_after_noisy_search() -> (
    None
):
    query = "查一下大模型排行榜 2026 水平排行！"

    def fetch_handler(url: str, options: FetchOptions) -> object:
        if "artificialanalysis.ai/leaderboards/models" in url:
            return _artificial_analysis_page(url)
        if "lmarena.ai/leaderboard" in url:
            return _lmarena_page(url)
        return _noisy_or_blocked_page(url)

    search_provider = FakeSearchProvider(
        lambda query, _options: _noisy_2293_search_results(query)
    )
    fetch_provider = FakeFetchProvider(fetch_handler)
    runtime = WebResearchRuntime(
        search_provider=search_provider,
        fetch_provider=fetch_provider,
    )

    evidence = await runtime.run(
        query,
        WebResearchRunOptions(pipeline_id="bug-2293", max_fetches=3),
    )

    assert evidence.status == "completed"
    assert evidence.failure_kind is None
    assert evidence.answer_quality == "body"
    assert evidence.diagnostics.answer_source == "fetched_body"
    assert evidence.diagnostics.fetched_urls == [
        "https://artificialanalysis.ai/leaderboards/models",
        "https://lmarena.ai/leaderboard",
    ]
    assert [citation.url for citation in evidence.citations] == [
        "https://artificialanalysis.ai/leaderboards/models",
        "https://lmarena.ai/leaderboard",
    ]
    assert fetch_provider.events == [
        "https://artificialanalysis.ai/leaderboards/models",
        "https://lmarena.ai/leaderboard",
    ]
    assert evidence.diagnostics.raw["query_profile"] == "llm_leaderboard"
    assert evidence.diagnostics.raw["trusted_seed_candidate_urls"] == [
        "https://artificialanalysis.ai/leaderboards/models",
        "https://lmarena.ai/leaderboard",
    ]
    assert evidence.diagnostics.raw["minimum_relevant_sources"] == 2
    assert (
        evidence.diagnostics.raw["source_quality_floor"]
        == "trusted_leaderboard_or_relevant_benchmark"
    )
