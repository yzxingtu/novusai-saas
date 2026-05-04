"""
Test type: structural/behavioral
Scope: builtin web_search and fetch_url provider adapters.
Mock strategy: tests inject representative WebSearchExecution and ToolResult
shapes from the existing builtin tool seams. They assert normalized evidence
fields, concrete URLs, body text, status, quality, and runtime fetch order.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from app.ai.tools.types import ToolResult
from app.ai.web_research import FetchOptions, SearchOptions, WebResearchRunOptions
from app.ai.web_research.providers import (
    BUILTIN_FETCH_URL_PROVIDER_ID,
    BUILTIN_WEB_SEARCH_PROVIDER_ID,
    BuiltinFetchUrlProvider,
    BuiltinWebSearchProvider,
)
from app.ai.web_research.runtime import WebResearchRuntime

PROVIDER_MODE_PUBLIC = "public"
STATUS_SUCCESS = "success"
STATUS_TIMEOUT = "timeout"


@dataclass
class SearchResultItem:
    title: str
    url: str
    snippet: str
    source: str
    provider: str
    provider_mode: str
    rank: int

    def to_summary_item(self) -> dict[str, str | int]:
        return {
            "title": self.title,
            "url": self.url,
            "snippet": self.snippet,
            "source": self.source,
            "provider": self.provider,
            "provider_mode": self.provider_mode,
            "rank": self.rank,
        }


@dataclass
class WebSearchExecutionMeta:
    status: str
    attempted_backends: list[str] = field(default_factory=list)
    selected_backend: str | None = None
    used_fallback: bool = False
    failure_reason: str | None = None
    latency_ms: int = 0
    provider: str | None = None
    provider_mode: str | None = None
    provider_chain: list[str] = field(default_factory=list)
    fallback_reason: str | None = None
    native_failure_kind: str | None = None
    cache_hit: bool = False


@dataclass
class WebSearchExecution:
    output: str
    items: list[SearchResultItem]
    meta: WebSearchExecutionMeta


@pytest.mark.asyncio
async def test_builtin_search_provider_normalizes_web_search_execution() -> None:
    """
    Test type: structural
    """

    async def search_runner(query: str, max_results: int, context: object) -> object:
        assert query == "LLM rankings 2026"
        assert max_results == 3
        assert context is None
        return WebSearchExecution(
            output="Search results for: LLM rankings 2026",
            items=[
                SearchResultItem(
                    title="Ranked second",
                    url="https://example.com/second",
                    snippet="Second source snippet",
                    source="public:baidu",
                    provider="baidu_public",
                    provider_mode=PROVIDER_MODE_PUBLIC,
                    rank=2,
                ),
                SearchResultItem(
                    title="Ranked first",
                    url="https://example.com/first",
                    snippet="First source snippet",
                    source="public:baidu",
                    provider="baidu_public",
                    provider_mode=PROVIDER_MODE_PUBLIC,
                    rank=1,
                ),
            ],
            meta=WebSearchExecutionMeta(
                status=STATUS_SUCCESS,
                attempted_backends=["public:baidu"],
                selected_backend="public:baidu",
                used_fallback=False,
                provider="baidu_public",
                provider_mode=PROVIDER_MODE_PUBLIC,
                provider_chain=["public:baidu"],
                cache_hit=True,
                latency_ms=42,
            ),
        )

    provider = BuiltinWebSearchProvider(search_runner=search_runner)
    results = await provider.search(
        "LLM rankings 2026",
        SearchOptions(max_results=3, allow_snippet_quality=True),
    )

    assert results.provider == BUILTIN_WEB_SEARCH_PROVIDER_ID
    assert results.status == "completed"
    assert results.failure_kind is None
    assert [item.url for item in results.items] == [
        "https://example.com/second",
        "https://example.com/first",
    ]
    assert results.items[1].rank == 1
    assert results.items[1].provider == BUILTIN_WEB_SEARCH_PROVIDER_ID
    assert results.items[1].answer_quality == "snippet"
    assert results.items[1].raw == {
        "title": "Ranked first",
        "url": "https://example.com/first",
        "snippet": "First source snippet",
        "source": "public:baidu",
        "provider": "baidu_public",
        "provider_mode": PROVIDER_MODE_PUBLIC,
        "rank": 1,
    }
    assert results.diagnostics["builtin_tool"] == "web_search"
    assert results.diagnostics["status"] == STATUS_SUCCESS
    assert results.diagnostics["selected_backend"] == "public:baidu"
    assert results.diagnostics["cache_hit"] is True


@pytest.mark.asyncio
async def test_builtin_search_provider_projects_failure_status() -> None:
    """
    Test type: structural
    """

    async def search_runner(query: str, max_results: int, context: object) -> object:
        return WebSearchExecution(
            output="Search source timed out",
            items=[],
            meta=WebSearchExecutionMeta(
                status=STATUS_TIMEOUT,
                attempted_backends=["public:baidu"],
                selected_backend="public:baidu",
                failure_reason="public:baidu returned timeout",
            ),
        )

    provider = BuiltinWebSearchProvider(search_runner=search_runner)
    results = await provider.search("current AI news", SearchOptions(max_results=5))

    assert results.status == "failed"
    assert results.failure_kind == "search_timeout"
    assert results.items == []
    assert results.diagnostics["failure_reason"] == "public:baidu returned timeout"


@pytest.mark.asyncio
async def test_builtin_fetch_provider_normalizes_successful_tool_result() -> None:
    """
    Test type: structural
    """

    async def fetch_executor(url: str, max_length: int) -> ToolResult:
        assert url == "https://example.com/article"
        assert max_length == 1200
        return ToolResult(
            tool_call_id="call_fetch",
            name="fetch_url",
            success=True,
            output=(
                "Content from https://example.com/article:\n"
                "Title: AI Daily\n"
                "Description: Latest AI headlines and analysis.\n\n"
                "Lead paragraph.\n\nDetailed ranking body."
            ),
            summary="AI Daily - Latest AI headlines and analysis.",
            summary_payload={
                "fetch_url": True,
                "ok": True,
                "error_type": "",
                "requested_url": "https://example.com/article",
                "final_url": "https://example.com/article",
                "title": "AI Daily",
                "description": "Latest AI headlines and analysis.",
                "summary": "AI Daily - Latest AI headlines and analysis.",
            },
            duration_ms=17,
        )

    provider = BuiltinFetchUrlProvider(fetch_executor=fetch_executor)
    page = await provider.fetch(
        "https://example.com/article",
        FetchOptions(diagnostics={"max_length": 1200}),
    )

    assert page.provider == BUILTIN_FETCH_URL_PROVIDER_ID
    assert page.url == "https://example.com/article"
    assert page.status == "completed"
    assert page.answer_quality == "body"
    assert page.title == "AI Daily"
    assert page.description == "Latest AI headlines and analysis."
    assert page.summary == "AI Daily - Latest AI headlines and analysis."
    assert page.body_text == "Lead paragraph.\n\nDetailed ranking body."
    assert page.failure_kind is None
    assert page.raw == {
        "builtin_tool": "fetch_url",
        "tool_call_id": "call_fetch",
        "success": True,
        "error": "",
        "error_type": "",
        "duration_ms": 17,
        "requested_url": "https://example.com/article",
        "summary_payload": {
            "fetch_url": True,
            "ok": True,
            "error_type": "",
            "requested_url": "https://example.com/article",
            "final_url": "https://example.com/article",
            "title": "AI Daily",
            "description": "Latest AI headlines and analysis.",
            "summary": "AI Daily - Latest AI headlines and analysis.",
        },
    }


@pytest.mark.asyncio
async def test_builtin_fetch_provider_marks_blocked_tool_result() -> None:
    """
    Test type: structural
    """

    async def fetch_executor(url: str, max_length: int) -> ToolResult:
        return ToolResult(
            tool_call_id="call_blocked",
            name="fetch_url",
            success=False,
            error=(
                "HTTP 403 while fetching https://example.com/paywall (title: Paywall)"
            ),
            summary="fetch_url failed",
            error_type="blocked_url",
            summary_payload={
                "fetch_url": True,
                "ok": False,
                "error_type": "blocked_url",
                "requested_url": "https://example.com/paywall",
                "final_url": "https://example.com/paywall",
                "title": "Paywall",
                "description": None,
                "summary": None,
            },
        )

    provider = BuiltinFetchUrlProvider(fetch_executor=fetch_executor)
    page = await provider.fetch("https://example.com/paywall", FetchOptions())

    assert page.url == "https://example.com/paywall"
    assert page.status == "blocked"
    assert page.answer_quality == "none"
    assert page.title == "Paywall"
    assert page.body_text == ""
    assert page.summary == ""
    assert page.failure_kind == "blocked_url"
    assert page.raw["error"] == (
        "HTTP 403 while fetching https://example.com/paywall (title: Paywall)"
    )


@pytest.mark.asyncio
async def test_runtime_uses_builtin_candidate_urls_for_fetch_calls() -> None:
    """
    Test type: behavioral
    """

    events: list[str] = []

    async def search_runner(query: str, max_results: int, context: object) -> object:
        events.append(f"search:{query}:max={max_results}")
        return WebSearchExecution(
            output="Search results for: model leaderboard",
            items=[
                SearchResultItem(
                    title="Primary leaderboard",
                    url="https://example.com/leaderboard",
                    snippet="Primary ranking snippet",
                    source="public:baidu",
                    provider="baidu_public",
                    provider_mode=PROVIDER_MODE_PUBLIC,
                    rank=1,
                ),
                SearchResultItem(
                    title="Duplicate leaderboard",
                    url="https://example.com/leaderboard",
                    snippet="Duplicate ranking snippet",
                    source="public:baidu",
                    provider="baidu_public",
                    provider_mode=PROVIDER_MODE_PUBLIC,
                    rank=2,
                ),
                SearchResultItem(
                    title="Secondary leaderboard",
                    url="https://example.com/secondary",
                    snippet="Secondary ranking snippet",
                    source="public:baidu",
                    provider="baidu_public",
                    provider_mode=PROVIDER_MODE_PUBLIC,
                    rank=3,
                ),
            ],
            meta=WebSearchExecutionMeta(
                status=STATUS_SUCCESS,
                attempted_backends=["public:baidu"],
                selected_backend="public:baidu",
                provider="baidu_public",
                provider_mode=PROVIDER_MODE_PUBLIC,
            ),
        )

    async def fetch_executor(url: str, max_length: int) -> ToolResult:
        events.append(f"fetch:{url}:max={max_length}")
        return ToolResult(
            tool_call_id=f"call_{url.rsplit('/', 1)[-1]}",
            name="fetch_url",
            success=True,
            output=(
                f"Content from {url}:\n"
                "Title: Primary LLM leaderboard\n\n"
                "2026 model ranking body: 1. Gemini score 74; "
                "2. GPT score 73; 3. Claude score 71; "
                "4. DeepSeek score 68."
            ),
            summary="Primary LLM leaderboard",
            summary_payload={
                "fetch_url": True,
                "ok": True,
                "error_type": "",
                "requested_url": url,
                "final_url": url,
                "title": "Primary LLM leaderboard",
                "description": None,
                "summary": "Primary LLM leaderboard",
            },
        )

    runtime = WebResearchRuntime(
        search_provider=BuiltinWebSearchProvider(search_runner=search_runner),
        fetch_provider=BuiltinFetchUrlProvider(fetch_executor=fetch_executor),
    )

    evidence = await runtime.run(
        "model leaderboard",
        WebResearchRunOptions(
            pipeline_id="pipeline-builtin-behavioral",
            max_search_results=3,
            max_fetches=1,
            diagnostics={"fetch_max_length": 1600},
        ),
    )

    assert events == [
        "search:model leaderboard:max=3",
        "fetch:https://example.com/leaderboard:max=1600",
    ]
    assert evidence.status == "completed"
    assert evidence.search_provider == BUILTIN_WEB_SEARCH_PROVIDER_ID
    assert evidence.fetch_provider == BUILTIN_FETCH_URL_PROVIDER_ID
    assert evidence.diagnostics.candidate_urls == [
        "https://example.com/leaderboard",
        "https://example.com/secondary",
    ]
    assert evidence.diagnostics.fetched_urls == ["https://example.com/leaderboard"]
    assert "Gemini score 74" in evidence.fetched_pages[0].body_text
    assert evidence.citations[0].url == "https://example.com/leaderboard"
