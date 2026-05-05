"""中文: BUG-2026-05-05-2326 的行为回归测试。

EN: Behavioral regression coverage for BUG-2026-05-05-2326.

Test type: behavioral
Regression for: BUG-2026-05-05-2326
Original symptom: conversation 2326 asked "查一下今日AI 新闻"; WebResearch
found 15 candidates but fetched only the first three Baidu-wrapper results, so
one relevant source plus two rejected Baijiahao pages ended as
insufficient_cross_checked_sources before later relevant candidates were tried.
Scope: WebResearchRuntime query planning -> candidate fetch budget -> relevance
gate -> evidence completion.
Mock strategy: fake providers replace external network only; query planning,
candidate selection, fetch loop, relevance gating, and evidence normalization
run real code.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest

from app.ai.web_research import (
    FetchOptions,
    PageEvidence,
    SearchOptions,
    SearchResultSet,
    WebResearchRunOptions,
    WebResearchRuntime,
    normalize_page_evidence,
    normalize_search_item,
)

QUERY = "查一下今日AI 新闻"

BAIDU_CCTV_WRAPPER = "http://www.baidu.com/link?url=ai-news-cctv"
BAIDU_LOW_RELEVANCE_WRAPPER_ONE = "http://www.baidu.com/link?url=ai-news-low-one"
BAIDU_LOW_RELEVANCE_WRAPPER_TWO = "http://www.baidu.com/link?url=ai-news-low-two"
BAIDU_REUTERS_WRAPPER = "http://www.baidu.com/link?url=ai-news-reuters"
BAIDU_UNUSED_WRAPPER = "http://www.baidu.com/link?url=ai-news-unused"

CCTV_FINAL_URL = "https://5gai.cctv.com/AI/index.shtml"
LOW_RELEVANCE_FINAL_URL_ONE = (
    "https://baijiahao.baidu.com/s?id=1833511051781267313&wfr=spider&for=pc"
)
LOW_RELEVANCE_FINAL_URL_TWO = (
    "https://baijiahao.baidu.com/s?id=1864035867509140983&wfr=spider&for=pc"
)
REUTERS_FINAL_URL = (
    "https://www.reuters.com/technology/artificial-intelligence/"
    "openai-ai-news-2026-05-05/"
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


def _search_handler(query: str, _options: SearchOptions) -> SearchResultSet:
    return SearchResultSet(
        query=query,
        provider="fake-search",
        items=[
            normalize_search_item(
                title="央视网数智频道 人工智能 新闻",
                url=BAIDU_CCTV_WRAPPER,
                snippet=(
                    "2026年5月5日 AI 新模型拉响网络安全攻防警报，"
                    "Anthropic Claude 最新人工智能新闻。"
                ),
                rank=1,
                provider="fake-search",
            ),
            normalize_search_item(
                title="资讯平台 AI 大横评 今日 新闻",
                url=BAIDU_LOW_RELEVANCE_WRAPPER_ONE,
                snippet="2026年5月5日 AI 新闻客户端评测，讨论内容生产价值。",
                rank=2,
                provider="fake-search",
            ),
            normalize_search_item(
                title="美国国防部与人工智能公司达成合作",
                url=BAIDU_LOW_RELEVANCE_WRAPPER_TWO,
                snippet="2026年5月5日 OpenAI 英伟达 人工智能 公司合作消息。",
                rank=3,
                provider="fake-search",
            ),
            normalize_search_item(
                title="Reuters technology page",
                url=BAIDU_REUTERS_WRAPPER,
                snippet="Reuters technology landing page. Fetch resolves the final story.",
                rank=4,
                provider="fake-search",
            ),
            normalize_search_item(
                title="AI News Today latest artificial intelligence updates",
                url=BAIDU_UNUSED_WRAPPER,
                snippet="AI news today and artificial intelligence updates.",
                rank=5,
                provider="fake-search",
            ),
        ],
    )


def _fetch_handler(url: str, _options: FetchOptions) -> PageEvidence:
    if url == BAIDU_CCTV_WRAPPER:
        return normalize_page_evidence(
            url=CCTV_FINAL_URL,
            status="completed",
            title="央视网数智频道 人工智能新闻",
            description="2026年5月5日，Anthropic 发布 Claude 安全研究相关 AI 新闻。",
            summary="央视网报道最新 AI 模型与网络安全攻防趋势。",
            body_text=(
                "2026年5月5日，央视网数智频道报道 Anthropic 最新 Claude "
                "模型引发 AI 网络安全攻防讨论，这是今日人工智能新闻。"
            ),
            provider="fake-fetch",
        )
    if url == BAIDU_REUTERS_WRAPPER:
        return normalize_page_evidence(
            url=REUTERS_FINAL_URL,
            status="completed",
            title="OpenAI announces new AI features today",
            description="Reuters reported OpenAI's latest artificial intelligence update.",
            summary="Reuters 2026-05-05 OpenAI AI news update.",
            body_text=(
                "Reuters reported on 2026-05-05 that OpenAI announced new "
                "AI features today, adding another current artificial "
                "intelligence news source for cross-checking."
            ),
            provider="fake-fetch",
        )
    if url == BAIDU_LOW_RELEVANCE_WRAPPER_ONE:
        return normalize_page_evidence(
            url=LOW_RELEVANCE_FINAL_URL_ONE,
            status="completed",
            title="资讯平台 AI 大横评：AI对新闻的价值绝不只是创作",
            description="2025年资讯客户端 AI 助手体验评测。",
            summary="AI 资讯客户端产品评测，不是今日 AI 新闻。",
            body_text="2025年5月30日，资讯客户端 AI 助手横评，讨论新闻创作价值。",
            provider="fake-fetch",
        )
    if url == BAIDU_LOW_RELEVANCE_WRAPPER_TWO:
        return normalize_page_evidence(
            url=LOW_RELEVANCE_FINAL_URL_TWO,
            status="completed",
            title="美国国防部与7家人工智能公司达成合作协议",
            description="低信任转载页，非可交叉验证来源。",
            summary="转载汇总国防部合作新闻。",
            body_text="转载页面汇总美国国防部与人工智能公司合作，缺少今日新闻原始证据。",
            provider="fake-fetch",
        )
    return normalize_page_evidence(
        url=url,
        status="failed",
        title="",
        body_text="",
        summary="",
        description="",
        provider="fake-fetch",
        failure_kind="unexpected_fetch",
    )


@pytest.mark.asyncio
async def test_2326_ai_news_fetches_past_first_three_candidates_for_cross_check() -> (
    None
):
    fetch_provider = FakeFetchProvider(_fetch_handler)
    runtime = WebResearchRuntime(
        search_provider=FakeSearchProvider(_search_handler),
        fetch_provider=fetch_provider,
    )

    evidence = await runtime.run(
        QUERY,
        WebResearchRunOptions(pipeline_id="pipeline-2326-ai-news-depth"),
    )

    assert fetch_provider.events[0] == BAIDU_CCTV_WRAPPER
    assert BAIDU_LOW_RELEVANCE_WRAPPER_ONE in fetch_provider.events[:4]
    assert BAIDU_LOW_RELEVANCE_WRAPPER_TWO in fetch_provider.events[:4]
    assert BAIDU_REUTERS_WRAPPER in fetch_provider.events
    assert fetch_provider.events.index(BAIDU_REUTERS_WRAPPER) >= 3
    assert evidence.status == "completed"
    assert evidence.answer_quality == "body"
    assert evidence.failure_kind is None
    assert evidence.diagnostics.answer_source == "fetched_body"
    assert evidence.diagnostics.fetched_urls == [CCTV_FINAL_URL, REUTERS_FINAL_URL]
    assert set(evidence.diagnostics.rejected_urls) == {
        LOW_RELEVANCE_FINAL_URL_ONE,
        LOW_RELEVANCE_FINAL_URL_TWO,
    }
    assert evidence.diagnostics.raw["query_profile"] == "ai_news"
    assert evidence.diagnostics.raw["minimum_relevant_sources"] == 2
    assert evidence.diagnostics.raw["accepted_source_count"] == 2
