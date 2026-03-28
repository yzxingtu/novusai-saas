from unittest.mock import patch

import httpx
import pytest

from app.ai.engine.base import BaseEngine
from app.ai.tools.executors import builtin_executor as be
from app.ai.tools.executors.builtin_executor import BuiltinToolExecutor
from app.ai.tools.types import ToolDefinition


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
    def __init__(
        self,
        *,
        get_response: httpx.Response | None = None,
        post_response: httpx.Response | None = None,
    ) -> None:
        self._get_response = get_response
        self._post_response = post_response

    async def __aenter__(self) -> "_FakeAsyncClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    async def get(self, *_args, **_kwargs) -> httpx.Response:
        assert self._get_response is not None
        return self._get_response

    async def post(self, *_args, **_kwargs) -> httpx.Response:
        assert self._post_response is not None
        return self._post_response


def test_extract_baidu_public_results_parses_basic_result_fields() -> None:
    html = """
    <html>
      <body>
        <div class="result c-container">
          <div class="_content_1q9is_4">
            <div class="title-box_4YBsj">
              <h3>
                <a href="http://www.baidu.com/link?url=example">Sample Result</a>
              </h3>
            </div>
            This is a short public snippet.
          </div>
        </div>
      </body>
    </html>
    """

    results = be._extract_baidu_public_results(html, 5)

    assert len(results) == 1
    assert results[0]["title"] == "Sample Result"
    assert results[0]["url"] == "http://www.baidu.com/link?url=example"
    assert "short public snippet" in results[0]["snippet"]


def test_extract_so360_public_results_parses_basic_result_fields() -> None:
    html = """
    <html>
      <body>
        <li class="res-list">
          <h3 class="res-title">
            <a href="https://www.so.com/link?m=example">Sample Result</a>
          </h3>
          This is another short public snippet.
        </li>
      </body>
    </html>
    """

    results = be._extract_so360_public_results(html, 5)

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
        <header>
          <nav>Home Pricing Docs</nav>
        </header>
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
async def test_fetch_url_returns_clear_http_error_message_with_title() -> None:
    html = """
    <html>
      <head><title>Access Denied</title></head>
      <body>Blocked by target site.</body>
    </html>
    """
    response = _make_response(
        "GET",
        "https://example.com/private",
        status_code=403,
        text=html,
    )

    with patch(
        "httpx.AsyncClient",
        return_value=_FakeAsyncClient(get_response=response),
    ):
        result = await BuiltinToolExecutor._fetch_url(
            "https://example.com/private",
            1200,
        )

    assert "HTTP 403" in result
    assert "Access Denied" in result


@pytest.mark.asyncio
async def test_run_web_search_uses_user_query_without_backend_rewrite() -> None:
    captured_queries: list[str] = []

    async def fake_baidu(query: str, max_results: int):
        captured_queries.append(f"baidu:{query}:{max_results}")
        return be.SearchProviderResponse(
            provider="baidu_public",
            status="success",
            results=[
                {
                    "title": "Sample Result",
                    "url": "https://example.com/result",
                    "snippet": "Public page snippet",
                }
            ],
        )

    async def fake_so360(query: str, max_results: int):
        captured_queries.append(f"so360:{query}:{max_results}")
        return be.SearchProviderResponse(
            provider="so360_public",
            status="success",
            results=[],
        )

    with patch.object(be, "_search_with_baidu_public", side_effect=fake_baidu), patch.object(
        be,
        "_search_with_so360_public",
        side_effect=fake_so360,
    ):
        result = await be._run_web_search("sample topic public info", 5)

    assert result.status == "success"
    assert captured_queries == ["baidu:sample topic public info:5"]


@pytest.mark.asyncio
async def test_builtin_executor_web_search_falls_back_to_so360_and_returns_summary_payload() -> None:
    executor = BuiltinToolExecutor()
    definition = ToolDefinition(name="web_search", description="Search the web")

    with patch.object(
        be,
        "_search_with_baidu_public",
        return_value=be.SearchProviderResponse(
            provider="baidu_public",
            status="source_challenged",
            results=[],
            error="returned safety verification",
        ),
    ), patch.object(
        be,
        "_search_with_so360_public",
        return_value=be.SearchProviderResponse(
            provider="so360_public",
            status="success",
            results=[
                {
                    "title": "Sample Result",
                    "url": "https://example.com/result",
                    "snippet": "Public page snippet",
                }
            ],
        ),
    ):
        result = await executor.execute(
            definition,
            "call_search_fallback",
            {"query": "sample topic public info", "max_results": 5},
        )

    assert result.success is True
    assert "Sample Result" in result.output
    assert result.summary_payload is not None
    assert result.summary_payload["provider"] == "so360_public"
    assert result.summary_payload["status"] == "success"
    assert result.summary_payload["result_count"] == 1
    assert result.summary_payload["items"][0]["url"] == "https://example.com/result"


@pytest.mark.asyncio
async def test_builtin_executor_web_search_returns_no_results_payload() -> None:
    executor = BuiltinToolExecutor()
    definition = ToolDefinition(name="web_search", description="Search the web")

    with patch.object(
        be,
        "_search_with_baidu_public",
        return_value=be.SearchProviderResponse(
            provider="baidu_public",
            status="no_results",
            results=[],
            error="returned no results",
        ),
    ), patch.object(
        be,
        "_search_with_so360_public",
        return_value=be.SearchProviderResponse(
            provider="so360_public",
            status="no_results",
            results=[],
            error="returned no results",
        ),
    ):
        result = await executor.execute(
            definition,
            "call_search_empty",
            {"query": "sample topic public info", "max_results": 5},
        )

    assert result.success is True
    assert result.output.startswith("No results found for:")
    assert result.summary_payload is not None
    assert result.summary_payload["status"] == "no_results"
    assert result.summary_payload["result_count"] == 0


@pytest.mark.asyncio
async def test_builtin_executor_web_search_returns_unavailable_payload_when_public_sources_fail() -> None:
    executor = BuiltinToolExecutor()
    definition = ToolDefinition(name="web_search", description="Search the web")

    with patch.object(
        be,
        "_search_with_baidu_public",
        return_value=be.SearchProviderResponse(
            provider="baidu_public",
            status="source_challenged",
            results=[],
            error="returned safety verification",
        ),
    ), patch.object(
        be,
        "_search_with_so360_public",
        return_value=be.SearchProviderResponse(
            provider="so360_public",
            status="source_unavailable",
            results=[],
            error="returned an unreadable page",
        ),
    ):
        result = await executor.execute(
            definition,
            "call_search_unavailable",
            {"query": "sample topic public info", "max_results": 5},
        )

    assert result.success is False
    assert "Search source unavailable:" in result.error
    assert result.summary_payload is not None
    assert result.summary_payload["status"] == "source_unavailable"
    assert "baidu_public" in result.summary_payload["failure_reason"]


def test_build_web_research_hint_guides_search_then_fetch_workflow() -> None:
    hint = BaseEngine._build_web_research_hint([
        ToolDefinition(name="web_search"),
        ToolDefinition(name="fetch_url"),
    ])

    assert "[WEB RESEARCH CONTRACT]" in hint
    assert "web_search" in hint
    assert "fetch_url" in hint
    assert "do not answer only from search snippets" in hint.lower()
    assert "do NOT claim that internet search" in hint
    assert "web_search is for finding candidate sources" in hint


def test_build_weather_tools_hint_guides_weather_queries() -> None:
    hint = BaseEngine._build_weather_tools_hint([
        ToolDefinition(name="get_current_weather"),
        ToolDefinition(name="get_weather_forecast"),
    ])

    assert "[WEATHER TOOLS]" in hint
    assert "get_current_weather" in hint
    assert "get_weather_forecast" in hint
    assert "do NOT claim that weather tools are unavailable" in hint


def test_build_capability_reporting_hint_lists_only_current_tools_and_page_ops() -> None:
    hint = BaseEngine._build_capability_reporting_hint(
        [
            ToolDefinition(name="web_search"),
            ToolDefinition(name="data_query"),
        ],
        {
            "page_context": {
                "page_key": "admin.ai.providers",
                "page_data": {
                    "available_operations": [
                        {"name": "create_record"},
                        {"name": "fill_form"},
                    ],
                },
            },
        },
    )

    assert "[CAPABILITY REPORTING]" in hint
    assert "Current tools: web_search, data_query." in hint
    assert "Current page operations: create_record, fill_form." in hint
    assert "Do NOT invent external capabilities" in hint


def test_extract_readable_page_tolerates_nodes_with_none_attrs() -> None:
    from bs4 import BeautifulSoup

    from app.ai.tools.executors import builtin_executor as be

    soup = BeautifulSoup("<html><body><div>ok</div></body></html>", "lxml")
    broken_node = soup.find("div")
    assert broken_node is not None
    broken_node.attrs = None

    be._remove_noise_nodes(soup)

    assert "ok" in soup.get_text()


@pytest.mark.asyncio
async def test_builtin_executor_returns_search_summary_payload() -> None:
    with patch.object(
        be,
        "_run_web_search",
        return_value=be.WebSearchExecution(
            output="Search results for: OpenAI\n\n1. Example",
            provider="baidu_public",
            status="success",
            items=[
                {
                    "title": "Example",
                    "url": "https://example.com",
                    "snippet": "summary",
                }
            ],
        ),
    ):
        executor = BuiltinToolExecutor()
        definition = ToolDefinition(name="web_search", description="Search the web")
        result = await executor.execute(
            definition,
            "call_search",
            {"query": "OpenAI", "max_results": 3},
        )

    assert result.success is True
    assert result.summary == "baidu_public: 1 result(s)"
    assert result.summary_payload is not None
    assert result.summary_payload["result_count"] == 1


@pytest.mark.asyncio
async def test_builtin_executor_returns_fetched_content_without_hidden_follow_up() -> None:
    with patch.object(
        BuiltinToolExecutor,
        "_fetch_url",
        return_value="Content from https://example.com:\n\nExample body",
    ):
        executor = BuiltinToolExecutor()
        definition = ToolDefinition(name="fetch_url", description="Fetch a URL")
        result = await executor.execute(
            definition,
            "call_fetch",
            {"url": "https://example.com", "max_length": 1000},
        )

    assert result.success is True
    assert result.output == "Content from https://example.com:\n\nExample body"


@pytest.mark.asyncio
async def test_builtin_executor_returns_failed_fetch_url_error_text() -> None:
    executor = BuiltinToolExecutor()
    definition = ToolDefinition(name="fetch_url", description="Fetch a URL")

    executor._functions["fetch_url"] = lambda **_kwargs: _async_return(  # type: ignore[assignment]
        "Error: HTTP 403 while fetching https://example.com/private"
    )

    result = await executor.execute(
        definition,
        "call_fetch_error",
        {"url": "https://example.com/private", "max_length": 1000},
    )

    assert result.success is True
    assert result.output == "Error: HTTP 403 while fetching https://example.com/private"


def _async_return(value: str):
    async def _inner(**_kwargs):
        return value

    return _inner()
