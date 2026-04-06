from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import httpx
import pytest

from app.ai.engine.base import BaseEngine
from app.ai.tools.executors import builtin_executor as be
from app.ai.tools.executors.builtin_executor import BuiltinToolExecutor
from app.ai.tools.types import ToolDefinition
from app.ai.types import ChatMessage
from app.ai.web_search.public_html import (
    _extract_baidu_public_results,
    _extract_so360_public_results,
)
from app.ai.web_search.types import (
    PROVIDER_MODE_NATIVE,
    PROVIDER_MODE_PUBLIC,
    STATUS_NO_RESULTS,
    STATUS_SUCCESS,
    STATUS_TIMEOUT,
    WebSearchExecution,
    WebSearchExecutionMeta,
)


def _make_response(
    method: str,
    url: str,
    *,
    status_code: int = 200,
    text: str = "",
    content_type: str = "text/html; charset=utf-8",
) -> httpx.Response:
    request = httpx.Request(method, url)
    return httpx.Response(
        status_code,
        text=text,
        headers={"content-type": content_type},
        request=request,
    )


class _FakeAsyncClient:
    def __init__(self, *, get_response: httpx.Response | None = None) -> None:
        self._get_response = get_response

    async def __aenter__(self) -> "_FakeAsyncClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001
        return None

    async def get(self, *_args, **_kwargs) -> httpx.Response:
        assert self._get_response is not None
        return self._get_response


def _make_search_execution(
    *,
    status: str = STATUS_SUCCESS,
    provider: str = "openai",
    provider_mode: str = PROVIDER_MODE_NATIVE,
    selected_backend: str = "native:openai:gpt-5.4",
    used_fallback: bool = False,
    cache_hit: bool = False,
    failure_reason: str | None = None,
    attempted_backends: list[str] | None = None,
    provider_chain: list[str] | None = None,
    items: list[SearchResultItemLike] | None = None,
) -> WebSearchExecution:
    normalized_items = list(items or [])
    meta = WebSearchExecutionMeta(
        status=status,
        attempted_backends=list(attempted_backends or [selected_backend]),
        selected_backend=selected_backend,
        used_fallback=used_fallback,
        failure_reason=failure_reason,
        provider=provider,
        provider_mode=provider_mode,
        provider_chain=list(provider_chain or [selected_backend]),
        cache_hit=cache_hit,
    )
    output = (
        "Search results for: OpenAI\n\n1. Example"
        if status == STATUS_SUCCESS
        else "No results found for: OpenAI"
        if status == STATUS_NO_RESULTS
        else f"Search source timed out: {failure_reason or 'timeout'}"
    )
    return WebSearchExecution(
        output=output,
        items=normalized_items,
        meta=meta,
    )


class SearchResultItemLike:
    def __init__(
        self,
        *,
        title: str,
        url: str,
        snippet: str,
        source: str,
        provider: str,
        provider_mode: str,
        rank: int,
    ) -> None:
        self.title = title
        self.url = url
        self.snippet = snippet
        self.source = source
        self.provider = provider
        self.provider_mode = provider_mode
        self.rank = rank

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


def test_extract_baidu_public_results_parses_basic_result_fields() -> None:
    html = """
    <html>
      <body>
        <div class="result c-container">
          <h3><a href="http://www.baidu.com/link?url=example">Sample Result</a></h3>
          This is a short public snippet.
        </div>
      </body>
    </html>
    """

    results = _extract_baidu_public_results(html, 5)

    assert len(results) == 1
    assert results[0]["title"] == "Sample Result"
    assert results[0]["url"] == "http://www.baidu.com/link?url=example"
    assert "short public snippet" in results[0]["snippet"]


def test_extract_so360_public_results_parses_basic_result_fields() -> None:
    html = """
    <html>
      <body>
        <li class="res-list">
          <h3 class="res-title"><a href="https://www.so.com/link?m=example">Sample Result</a></h3>
          This is another short public snippet.
        </li>
      </body>
    </html>
    """

    results = _extract_so360_public_results(html, 5)

    assert len(results) == 1
    assert results[0]["title"] == "Sample Result"
    assert "so.com/link" in results[0]["url"]
    assert "another short public snippet" in results[0]["snippet"]


@pytest.mark.asyncio
async def test_fetch_url_extracts_main_content_and_omits_navigation_noise() -> None:
    html = """
    <html>
      <head>
        <title>Sample Doc</title>
        <meta name="description" content="Meta description here." />
      </head>
      <body>
        <header><nav>Home Pricing Docs</nav></header>
        <main>
          <h1>Sample Doc</h1>
          <p>First important paragraph.</p>
          <p>Second important paragraph with useful details.</p>
        </main>
        <footer>Footer links</footer>
      </body>
    </html>
    """
    response = _make_response("GET", "https://example.com/doc", text=html)

    with patch(
        "httpx.AsyncClient",
        return_value=_FakeAsyncClient(get_response=response),
    ):
        result = await BuiltinToolExecutor._fetch_url(
            "https://example.com/doc",
            1200,
        )

    assert "Title: Sample Doc" in result
    assert "Description: Meta description here." in result
    assert "First important paragraph." in result
    assert "Second important paragraph with useful details." in result
    assert "Home Pricing Docs" not in result
    assert "Footer links" not in result


@pytest.mark.asyncio
async def test_builtin_executor_fetch_url_http_error_is_failed_tool_result() -> None:
    executor = BuiltinToolExecutor()
    definition = ToolDefinition(name="fetch_url", description="Fetch a webpage")
    response = _make_response(
        "GET",
        "https://example.com/private",
        status_code=403,
        text="<html><head><title>Access Denied</title></head><body>Blocked</body></html>",
    )

    with patch(
        "httpx.AsyncClient",
        return_value=_FakeAsyncClient(get_response=response),
    ):
        result = await executor.execute(
            definition,
            "call_fetch_403",
            {"url": "https://example.com/private", "max_length": 1200},
        )

    assert result.success is False
    assert "HTTP 403" in result.error
    assert "Access Denied" in result.error


@pytest.mark.asyncio
async def test_builtin_executor_web_search_returns_complete_native_summary_payload() -> None:
    executor = BuiltinToolExecutor()
    definition = ToolDefinition(name="web_search", description="Search the web")
    execution = _make_search_execution(
        items=[
            SearchResultItemLike(
                title="Example",
                url="https://example.com",
                snippet="summary",
                source="native:openai:gpt-5.4",
                provider="openai",
                provider_mode=PROVIDER_MODE_NATIVE,
                rank=1,
            )
        ],
        cache_hit=True,
    )

    with patch.object(be, "_run_web_search", return_value=execution):
        result = await executor.execute(
            definition,
            "call_search",
            {"query": "OpenAI", "max_results": 3},
        )

    assert result.success is True
    assert result.summary == "openai: 1 result(s)"
    assert result.summary_payload is not None
    assert result.summary_payload["provider"] == "openai"
    assert result.summary_payload["provider_mode"] == PROVIDER_MODE_NATIVE
    assert result.summary_payload["provider_chain"] == ["native:openai:gpt-5.4"]
    assert result.summary_payload["used_fallback"] is False
    assert result.summary_payload["status"] == STATUS_SUCCESS
    assert result.summary_payload["result_count"] == 1
    assert result.summary_payload["cache_hit"] is True
    assert result.summary_payload["items"][0]["url"] == "https://example.com"


@pytest.mark.asyncio
async def test_builtin_executor_web_search_no_results_is_not_a_failure() -> None:
    executor = BuiltinToolExecutor()
    definition = ToolDefinition(name="web_search", description="Search the web")
    execution = _make_search_execution(
        status=STATUS_NO_RESULTS,
        provider="baidu_public",
        provider_mode=PROVIDER_MODE_PUBLIC,
        selected_backend="public:baidu",
        used_fallback=True,
        attempted_backends=["native:openai:gpt-5.4", "public:baidu"],
        provider_chain=["native:openai:gpt-5.4", "public:baidu"],
        failure_reason="public:baidu returned no results",
    )

    with patch.object(be, "_run_web_search", return_value=execution):
        result = await executor.execute(
            definition,
            "call_search_empty",
            {"query": "OpenAI", "max_results": 3},
        )

    assert result.success is True
    assert result.output == "No results found for: OpenAI"
    assert result.summary_payload is not None
    assert result.summary_payload["provider_mode"] == PROVIDER_MODE_PUBLIC
    assert result.summary_payload["used_fallback"] is True
    assert result.summary_payload["status"] == STATUS_NO_RESULTS
    assert result.summary_payload["selected_backend"] == "public:baidu"


@pytest.mark.asyncio
async def test_builtin_executor_web_search_failure_surfaces_error_and_status() -> None:
    executor = BuiltinToolExecutor()
    definition = ToolDefinition(name="web_search", description="Search the web")
    execution = _make_search_execution(
        status=STATUS_TIMEOUT,
        provider="openai",
        provider_mode=PROVIDER_MODE_NATIVE,
        selected_backend="native:openai:gpt-5.4",
        failure_reason="provider timed out",
    )

    with patch.object(be, "_run_web_search", return_value=execution):
        result = await executor.execute(
            definition,
            "call_search_timeout",
            {"query": "OpenAI", "max_results": 3},
        )

    assert result.success is False
    assert "timed out" in result.error.lower()
    assert result.summary_payload is not None
    assert result.summary_payload["status"] == STATUS_TIMEOUT
    assert result.summary_payload["failure_reason"] == "provider timed out"


def test_fetch_url_gate_requires_fetch_after_successful_web_search() -> None:
    messages = [
        ChatMessage(
            role="assistant",
            content="",
            tool_calls=[
                {
                    "function": {
                        "name": "web_search",
                        "arguments": '{"query": "test"}',
                    },
                    "success": True,
                }
            ],
        )
    ]
    assert BaseEngine._needs_fetch_url_before_summary(messages) is True
    tools = [
        ToolDefinition(name="web_search"),
        ToolDefinition(name="fetch_url"),
    ]
    gated = BaseEngine._apply_fetch_url_only_gate(messages, tools, tools)
    assert [t.name for t in gated] == ["fetch_url"]


def test_build_web_research_hint_mentions_native_results_are_still_candidates() -> None:
    hint = BaseEngine._build_web_research_hint(
        [
            ToolDefinition(name="web_search"),
            ToolDefinition(name="fetch_url"),
        ]
    )

    assert "[WEB RESEARCH]" in hint
    assert "candidate sources" in hint.lower()
    assert "provider-native web search" in hint.lower()
    assert "fetch_url" in hint


def test_correct_query_year_replaces_stale_year_without_historical_markers() -> None:
    with patch("app.ai.tools.executors.builtin_executor.datetime") as mocked_datetime:
        mocked_datetime.now.return_value = SimpleNamespace(year=2026)
        assert be._correct_query_year("乌克兰局势 2025 局势") == "乌克兰局势 2026 局势"


def test_correct_query_year_leaves_historical_queries_unchanged() -> None:
    with patch("app.ai.tools.executors.builtin_executor.datetime") as mocked_datetime:
        mocked_datetime.now.return_value = SimpleNamespace(year=2026)
        assert be._correct_query_year("乌克兰局势 2025 年历史回顾") == "乌克兰局势 2025 年历史回顾"
