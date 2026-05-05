"""
Test type: behavioral
Regression for: BUG-2026-05-05-2305
Original symptom: conversation 2305 asked "查一下 2026年最热门的 女性裙子款式排行！";
the runtime rejected a low-quality Baidu vertical-search candidate and stopped
without expanding toward verifiable fashion trend sources.
Scope: WebResearchRuntime query planning -> expanded search -> relevance gate.
Mock strategy: fake providers replace external network only; the real runtime,
query planner, candidate selection, relevance gate, and evidence builder decide
whether trend ranking evidence can complete the turn.
"""

from collections.abc import Callable

import pytest

from app.ai.web_research import (
    FetchOptions,
    PageEvidence,
    SearchOptions,
    SearchResultSet,
    WebResearchRunOptions,
    WebResearchRuntime,
    build_web_research_query_plan,
    evaluate_page_relevance,
    normalize_page_evidence,
    normalize_search_item,
)

QUERY = "查一下 2026年最热门的 女性裙子款式排行！"
VOGUE_DRESS_TRENDS_URL = "https://www.vogue.com/article/spring-2026-dress-trends"
MARIE_CLAIRE_SUMMER_TRENDS_URL = (
    "https://www.marieclaire.com/fashion/summer-fashion/summer-fashion-trends-2026/"
)
WHO_WHAT_WEAR_DRESS_TRENDS_URL = (
    "https://www.whowhatwear.com/fashion/trends/dress-trends-2026"
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

    def __init__(self, handler: Callable[[str, FetchOptions], PageEvidence]):
        self.events: list[str] = []
        self._handler = handler

    async def fetch(self, url: str, options: FetchOptions) -> PageEvidence:
        self.events.append(url)
        return self._handler(url, options)


def _search_results(query: str, _options: SearchOptions) -> SearchResultSet:
    normalized_query = query.casefold()
    if "dress trends" in normalized_query or "流行趋势" in normalized_query:
        return SearchResultSet(
            query=query,
            provider="fake-search",
            items=[
                normalize_search_item(
                    title="10 Spring 2026 Dress Trends Sweeping the Runways | Vogue",
                    url=VOGUE_DRESS_TRENDS_URL,
                    snippet=(
                        "Vogue ranks the spring 2026 dress trends to know now, "
                        "including sweet minis, floral midis, and lace details."
                    ),
                    rank=1,
                    provider="fake-search",
                ),
                normalize_search_item(
                    title="These Are the Biggest Dress Trends of 2026 | Who What Wear",
                    url=WHO_WHAT_WEAR_DRESS_TRENDS_URL,
                    snippet=(
                        "Who What Wear lists 2026 dress trends including cape "
                        "dresses, modern T-shirt dresses, ruffles, and draping."
                    ),
                    rank=2,
                    provider="fake-search",
                ),
            ],
        )
    return SearchResultSet(
        query=query,
        provider="fake-search",
        items=[
            normalize_search_item(
                title="查一下 2026年最热门的 女性裙子款式排行! - 百度视频",
                url="http://www.baidu.com/link?url=2305-baidu-note-video",
                snippet=(
                    "2026年最全裙子款式大盘点，百度视频聚合页，需要跳转后才能确认正文。"
                ),
                rank=1,
                provider="fake-search",
            )
        ],
    )


def _fetch_page(url: str, _options: FetchOptions) -> PageEvidence:
    if "baidu.com/link" in url:
        return normalize_page_evidence(
            url=(
                "https://www.baidu.com/s?pd=note&rpf=pc&word="
                "%E6%9F%A5%E4%B8%80%E4%B8%8B+2026%E5%B9%B4%E6%9C%80%E7%83%AD"
                "%E9%97%A8%E7%9A%84+%E5%A5%B3%E6%80%A7%E8%A3%99%E5%AD%90"
                "%E6%AC%BE%E5%BC%8F%E6%8E%92%E8%A1%8C%21&sa=vs_video_top_ugc"
            ),
            status="completed",
            title="查一下 2026年最热门的 女性裙子款式排行! - 百度",
            description="来自百度的搜索结果",
            summary="查一下 2026年最热门的 女性裙子款式排行! - 百度",
            body_text="来自百度的搜索结果，不是可核实的时尚趋势正文。",
            provider="fake-fetch",
            raw={"requested_url": url},
        )
    if url == VOGUE_DRESS_TRENDS_URL:
        return normalize_page_evidence(
            url=url,
            status="completed",
            title="10 Spring 2026 Dress Trends That Swept the Runways",
            description=("Vogue rounds up the spring 2026 dress trends to know now."),
            summary="Vogue ranked spring 2026 dress trends for women.",
            body_text=(
                "Vogue's spring 2026 dress trends list ranks women's dress "
                "styles from the runways. 1. Sweet mini dresses. 2. Floral "
                "midi dresses. 3. Lace-trimmed dresses. 4. Slip dresses. "
                "5. Layered dresses. The list focuses on popular 2026 dresses "
                "and styling directions for women."
            ),
            provider="fake-fetch",
        )
    if url == MARIE_CLAIRE_SUMMER_TRENDS_URL:
        return normalize_page_evidence(
            url=url,
            status="completed",
            title="8 Essential Summer 2026 Fashion Trends Defining the Season",
            description=(
                "Marie Claire identifies the dress and skirt styles shaping "
                "summer 2026 fashion."
            ),
            summary="Marie Claire summer 2026 fashion trend ranking.",
            body_text=(
                "The summer 2026 fashion trends include dress and skirt styles "
                "women are wearing now. 1. A-line skirts. 2. Maxi dresses. "
                "3. Slip dresses. 4. Sheer skirts. 5. Draped dresses. "
                "6. Lace details. 7. Floral dresses. 8. Tailored shirt dresses."
            ),
            provider="fake-fetch",
        )
    if url == WHO_WHAT_WEAR_DRESS_TRENDS_URL:
        return normalize_page_evidence(
            url=url,
            status="completed",
            title="These Are the Biggest Dress Trends of 2026",
            description=(
                "Who What Wear lists the dress trends women will want in 2026."
            ),
            summary="Who What Wear 2026 dress trend ranking.",
            body_text=(
                "These are the biggest dress trends of 2026. 1. Cape dresses. "
                "2. Modern T-shirt dresses. 3. Ruffles. 4. Asymmetric waists. "
                "5. Silk mini dresses. 6. Bold blue dresses. 7. Chic draping. "
                "The article is a ranked trend guide for women's dresses."
            ),
            provider="fake-fetch",
        )
    raise AssertionError(f"unexpected fetch URL: {url}")


def test_2305_fashion_ranking_query_gets_trend_search_plan() -> None:
    plan = build_web_research_query_plan(QUERY)

    assert plan.profile == "fashion_trend_ranking"
    assert plan.minimum_relevant_sources == 2
    assert plan.trusted_seed_urls[:2] == [
        VOGUE_DRESS_TRENDS_URL,
        MARIE_CLAIRE_SUMMER_TRENDS_URL,
    ]
    assert any("dress trends" in query.casefold() for query in plan.search_queries)
    assert any("流行趋势" in query for query in plan.search_queries)


@pytest.mark.asyncio
async def test_2299_no_baidu_results_still_fetches_2026_fashion_trusted_seeds() -> None:
    """
    Test type: behavioral
    Regression for: BUG-2026-05-05-2299
    中文: Baidu public 搜索 0 结果时，2026 女性裙装排行仍应走 WebResearch query profile 的可信来源。
    EN: When Baidu public search returns zero results, the 2026 fashion ranking profile must still fetch trusted WebResearch seeds.
    """

    search_provider = FakeSearchProvider(
        lambda query, _options: SearchResultSet(
            query=query,
            provider="fake-search",
            status="failed",
            failure_kind="no_results",
            diagnostics={
                "failure_reason": "public:baidu returned only low-confidence results"
            },
        )
    )
    fetch_provider = FakeFetchProvider(_fetch_page)
    runtime = WebResearchRuntime(
        search_provider=search_provider,
        fetch_provider=fetch_provider,
    )

    evidence = await runtime.run(
        QUERY,
        WebResearchRunOptions(pipeline_id="pipeline-2299-zero-results"),
    )

    assert search_provider.queries == [
        QUERY,
        "2026 women's dress trends ranking",
        "2026 女性 裙子 款式 流行趋势 排行",
    ]
    assert evidence.status == "completed"
    assert evidence.answer_quality == "body"
    assert evidence.failure_kind is None
    assert evidence.diagnostics.answer_source == "fetched_body"
    assert evidence.diagnostics.raw["query_profile"] == "fashion_trend_ranking"
    assert evidence.diagnostics.raw["trusted_seed_count"] == 2
    assert evidence.diagnostics.fetched_urls[:2] == [
        VOGUE_DRESS_TRENDS_URL,
        MARIE_CLAIRE_SUMMER_TRENDS_URL,
    ]
    assert fetch_provider.events[:2] == [
        VOGUE_DRESS_TRENDS_URL,
        MARIE_CLAIRE_SUMMER_TRENDS_URL,
    ]


def test_fashion_ranking_search_plan_does_not_inject_2026_seeds_for_other_years() -> (
    None
):
    plan = build_web_research_query_plan("查一下 2025年最热门的 女性裙子款式排行！")

    assert plan.profile == "fashion_trend_ranking"
    assert plan.trusted_seed_candidates == []
    assert "2025 women's dress trends ranking" in plan.search_queries
    assert "2025 女性 裙子 款式 流行趋势 排行" in plan.search_queries
    assert all("2026" not in query for query in plan.search_queries)


def test_2305_fashion_trend_page_passes_relevance_without_llm_terms() -> None:
    page = _fetch_page(VOGUE_DRESS_TRENDS_URL, FetchOptions())

    relevance = evaluate_page_relevance(query=QUERY, page=page)

    assert relevance.status == "relevant"
    assert relevance.profile == "fashion_trend_ranking"
    assert "fashion_subject" not in relevance.required_terms
    assert "llm_subject" not in relevance.required_terms
    assert "multiple_model_names" not in relevance.required_terms


@pytest.mark.asyncio
async def test_2305_expands_after_wrapper_only_search_and_fetches_two_trend_sources() -> (
    None
):
    search_provider = FakeSearchProvider(_search_results)
    fetch_provider = FakeFetchProvider(_fetch_page)
    runtime = WebResearchRuntime(
        search_provider=search_provider,
        fetch_provider=fetch_provider,
    )

    evidence = await runtime.run(
        QUERY,
        WebResearchRunOptions(pipeline_id="bug-2305", max_fetches=4),
    )

    assert search_provider.queries[0] == QUERY
    assert len(search_provider.queries) >= 2
    assert any("dress trends" in query.casefold() for query in search_provider.queries)
    assert evidence.status == "completed"
    assert evidence.failure_kind is None
    assert evidence.diagnostics.answer_source == "fetched_body"
    assert evidence.diagnostics.fetched_urls == [
        VOGUE_DRESS_TRENDS_URL,
        MARIE_CLAIRE_SUMMER_TRENDS_URL,
    ]
    assert evidence.diagnostics.candidate_urls[:2] == [
        VOGUE_DRESS_TRENDS_URL,
        MARIE_CLAIRE_SUMMER_TRENDS_URL,
    ]
    assert "http://www.baidu.com/link?url=2305-baidu-note-video" in (
        evidence.diagnostics.candidate_urls
    )
    assert fetch_provider.events == evidence.diagnostics.fetched_urls
    assert "http://www.baidu.com/link?url=2305-baidu-note-video" not in (
        fetch_provider.events
    )
    assert evidence.diagnostics.relevance_profile == "fashion_trend_ranking"
    assert evidence.diagnostics.raw["query_profile"] == "fashion_trend_ranking"
    assert evidence.diagnostics.raw["minimum_relevant_sources"] == 2
    assert evidence.diagnostics.raw["planned_search_queries"] == search_provider.queries
