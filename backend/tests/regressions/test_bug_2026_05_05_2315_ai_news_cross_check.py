"""
Test type: behavioral
Regression for: BUG-2026-05-05-2315
Original symptom: conversation 2315 asked "今日ai新闻查一下"; WebResearch
accepted one stale low-trust NetEase repost as completed evidence and rendered
the fetched article body directly instead of cross-checking and summarizing.
Scope: WebResearchRuntime query planning -> relevance/source gate -> recovery
evidence rendering.
Mock strategy: fake providers replace external network only; runtime query
planning, relevance gating, evidence normalization, and RecoveryManager output
assembly run real code.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest

from app.ai.engine.recovery_manager import RecoveryManager
from app.ai.engine.types import IntentPlan
from app.ai.tools.types import ToolResult
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

QUERY = "今日ai新闻查一下"
NETEASE_STALE_URL = "https://www.163.com/dy/article/J1QO5JKJ05198CJN.html"
OPENAI_NEWS_URL = "https://www.reuters.com/technology/artificial-intelligence/openai-search-2026-05-05/"
NVIDIA_NEWS_URL = "https://www.theverge.com/ai/2026/5/5/nvidia-ai-chip-news"


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


def _ai_news_intent() -> IntentPlan:
    return IntentPlan(
        intent_id="intent-1",
        kind="web_research",
        family="web_research",
        order=1,
        user_visible_label="web_research",
        source_text=QUERY,
        status="pending",
        requires_tools=True,
        allowed_tool_names=["web_search", "fetch_url"],
        completion_signals=["fetch_url"],
    )


@pytest.mark.asyncio
async def test_2315_rejects_stale_single_source_ai_news_body() -> None:
    def search_handler(query: str, _options: SearchOptions) -> SearchResultSet:
        return SearchResultSet(
            query=query,
            provider="fake-search",
            items=[
                normalize_search_item(
                    title="百度自己制造了一次灾害级公关；通义千问App更名 | AI daily早新闻",
                    url=NETEASE_STALE_URL,
                    snippet="财联社AI daily 5月10日讯，OpenAI计划下周一宣布搜索竞品。",
                    rank=1,
                    provider="fake-search",
                )
            ],
        )

    def fetch_handler(url: str, _options: FetchOptions) -> PageEvidence:
        return normalize_page_evidence(
            url=url,
            status="completed",
            title="百度自己制造了一次灾害级公关；通义千问App更名 | AI daily早新闻",
            description="网易号转载的AI daily早新闻。",
            summary="百度公关、淘宝VisionPro、苹果AI服务器芯片、OpenAI搜索产品。",
            body_text=(
                "财联社AI daily 5月10日讯 今日AI daily早新闻主要内容有："
                "淘宝VisionPro正式版将会开放完整的交易功能；"
                "苹果公司今年将通过配备自有处理器的数据中心提供一些即将推出的人工智能功能。"
                "据路透，OpenAI计划于下周一宣布其AI搜索产品。"
                "近期，三星发布首款Galaxy ring，并且苹果也申请数项专利。"
                "AAAI 2024杰出论文奖相关研究被提及。"
            ),
            provider="fake-fetch",
        )

    runtime = WebResearchRuntime(
        search_provider=FakeSearchProvider(search_handler),
        fetch_provider=FakeFetchProvider(fetch_handler),
    )

    evidence = await runtime.run(
        QUERY,
        WebResearchRunOptions(pipeline_id="pipeline-2315-stale-news"),
    )

    assert evidence.status != "completed"
    assert evidence.answer_quality == "none"
    assert evidence.diagnostics.answer_source == "none"
    assert evidence.diagnostics.raw["query_profile"] == "ai_news"
    assert evidence.diagnostics.raw["minimum_relevant_sources"] == 2
    assert evidence.diagnostics.fetched_urls == []
    assert evidence.diagnostics.rejected_urls == [NETEASE_STALE_URL]
    assert evidence.failure_kind in {
        "low_query_relevance",
        "insufficient_cross_checked_sources",
    }


@pytest.mark.asyncio
async def test_2315_ai_news_needs_two_relevant_sources_before_completion() -> None:
    def search_handler(query: str, _options: SearchOptions) -> SearchResultSet:
        return SearchResultSet(
            query=query,
            provider="fake-search",
            items=[
                normalize_search_item(
                    title="OpenAI launches new AI search features on May 5, 2026",
                    url=OPENAI_NEWS_URL,
                    snippet="2026年5月5日 OpenAI 发布 AI 搜索功能，人工智能新闻。",
                    rank=1,
                    provider="fake-search",
                )
            ],
        )

    def fetch_handler(url: str, _options: FetchOptions) -> PageEvidence:
        return normalize_page_evidence(
            url=url,
            status="completed",
            title="OpenAI launches new AI search features on May 5, 2026",
            description="2026年5月5日 OpenAI 发布新的 AI 搜索功能。",
            summary="OpenAI announced AI search features on 2026-05-05.",
            body_text=(
                "2026年5月5日，OpenAI 宣布新的 AI 搜索功能，"
                "该人工智能新闻涉及搜索、ChatGPT和实时信息能力。"
            ),
            provider="fake-fetch",
        )

    runtime = WebResearchRuntime(
        search_provider=FakeSearchProvider(search_handler),
        fetch_provider=FakeFetchProvider(fetch_handler),
    )

    evidence = await runtime.run(
        QUERY,
        WebResearchRunOptions(pipeline_id="pipeline-2315-single-news-source"),
    )

    assert evidence.status == "partial"
    assert evidence.answer_quality == "none"
    assert evidence.failure_kind == "insufficient_cross_checked_sources"
    assert evidence.diagnostics.answer_source == "none"
    assert evidence.diagnostics.fetched_urls == [OPENAI_NEWS_URL]
    assert evidence.diagnostics.raw["query_profile"] == "ai_news"
    assert evidence.diagnostics.raw["minimum_relevant_sources"] == 2


def _ai_news_fetch_result(
    *,
    url: str,
    title: str,
    summary: str,
    body: str,
) -> ToolResult:
    return ToolResult(
        tool_call_id=f"call-{url}",
        name="fetch_url",
        success=True,
        output=f"Content from {url}:\nTitle: {title}\n\n{body}",
        summary=f"{title} - {summary}",
        result_link=url,
        summary_payload={
            "fetch_url": True,
            "ok": True,
            "url": url,
            "final_url": url,
            "title": title,
            "description": summary,
            "summary": f"{title} - {summary}",
            "answer_quality": "body",
            "status": "completed",
            "provider": "fake-fetch",
            "relevance_status": "relevant",
            "relevance_score": 0.78,
            "relevance_profile": "ai_news",
            "relevance_reason": "query_relevance_passed",
            "web_research_evidence": {
                "query": QUERY,
                "status": "completed",
                "answer_quality": "body",
                "diagnostics": {
                    "evidence_status": "completed",
                    "answer_source": "fetched_body",
                    "relevance_profile": "ai_news",
                    "raw": {
                        "query_profile": "ai_news",
                        "minimum_relevant_sources": 2,
                    },
                },
                "fetched_pages": [
                    {
                        "url": url,
                        "status": "completed",
                        "title": title,
                        "description": summary,
                        "summary": f"{title} - {summary}",
                        "body_text": body,
                        "answer_quality": "body",
                        "provider": "fake-fetch",
                        "relevance_status": "relevant",
                        "relevance_profile": "ai_news",
                    }
                ],
            },
        },
    )


def test_2315_renders_cross_checked_ai_news_summary_not_article_dump() -> None:
    body_one = (
        "2026年5月5日，OpenAI 宣布新的 AI 搜索功能。"
        "该功能面向 ChatGPT 的实时信息检索。"
        "这是第一来源正文的第二段，包含很多背景细节，不应被整段转储。"
    )
    body_two = (
        "2026年5月5日，NVIDIA 发布新的 AI 数据中心芯片路线图。"
        "The Verge 报道该芯片面向生成式人工智能工作负载。"
        "这是第二来源正文的第二段，包含很多背景细节，不应被整段转储。"
    )
    fetch_results = [
        _ai_news_fetch_result(
            url=OPENAI_NEWS_URL,
            title="OpenAI 发布新的 AI 搜索功能",
            summary="2026年5月5日 OpenAI 更新 ChatGPT 实时搜索能力。",
            body=body_one,
        ),
        _ai_news_fetch_result(
            url=NVIDIA_NEWS_URL,
            title="NVIDIA 发布新的 AI 数据中心芯片路线图",
            summary="2026年5月5日 NVIDIA 面向生成式 AI 工作负载更新芯片路线图。",
            body=body_two,
        ),
    ]

    updated = RecoveryManager.update_intent_statuses(
        [_ai_news_intent()],
        messages=[],
        tool_results=fetch_results,
    )
    output = RecoveryManager.build_completed_output(
        updated,
        tool_results=fetch_results,
        reason="partial_exit_recovery",
    )

    assert updated[0].status == "completed"
    assert "今日 AI 新闻摘要" in output
    assert "OpenAI 发布新的 AI 搜索功能" in output
    assert "NVIDIA 发布新的 AI 数据中心芯片路线图" in output
    assert "来源：" in output
    assert "整段转储" not in output
    assert body_one not in output
    assert body_two not in output
