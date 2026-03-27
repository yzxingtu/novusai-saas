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


@pytest.mark.asyncio
async def test_web_search_parses_results_and_decodes_duckduckgo_redirect() -> None:
    html = """
    <html>
      <body>
        <div class="result">
          <a class="result__a" href="/l/?uddg=https%3A%2F%2Fexample.com%2Farticle">
            Example Result
          </a>
          <a class="result__snippet">Useful summary text.</a>
        </div>
      </body>
    </html>
    """
    response = _make_response(
        "POST",
        "https://html.duckduckgo.com/html/",
        text=html,
    )

    with patch(
        "httpx.AsyncClient",
        return_value=_FakeAsyncClient(post_response=response),
    ):
        result = await BuiltinToolExecutor._web_search("example", 5)

    assert "Example Result" in result
    assert "https://example.com/article" in result
    assert "Useful summary text." in result


@pytest.mark.asyncio
async def test_web_search_uses_duckduckgo_for_chinese_company_queries() -> None:
    calls: list[str] = []

    async def fake_ddg(query: str, max_results: int):
        calls.append(f"ddg:{query}:{max_results}")
        return [
            {
                "title": "示例企业有限公司 - 企业信息",
                "url": "https://example.com/company",
                "snippet": "企业信息",
            }
        ], None

    with patch.object(
        be,
        "_search_with_duckduckgo",
        side_effect=fake_ddg,
    ):
        result = await BuiltinToolExecutor._web_search(
            "示例企业有限公司 企业信息",
            5,
        )

    assert calls == ["ddg:示例企业有限公司 企业信息:5"]
    assert "示例企业有限公司 - 企业信息" in result


@pytest.mark.asyncio
async def test_web_search_prefers_duckduckgo_for_general_english_queries() -> None:
    calls: list[str] = []

    async def fake_ddg(query: str, max_results: int):
        calls.append(f"ddg:{query}:{max_results}")
        return [
            {
                "title": "OpenAI Responses API",
                "url": "https://example.com/openai",
                "snippet": "Official docs",
            }
        ], None

    with patch.object(
        be,
        "_search_with_duckduckgo",
        side_effect=fake_ddg,
    ):
        result = await BuiltinToolExecutor._web_search(
            "OpenAI Responses API",
            5,
        )

    assert calls == ["ddg:OpenAI Responses API:5"]
    assert "OpenAI Responses API" in result


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


def test_build_web_research_hint_guides_search_then_fetch_workflow() -> None:
    hint = BaseEngine._build_web_research_hint([
        ToolDefinition(name="web_search"),
        ToolDefinition(name="fetch_url"),
    ])

    assert "[WEB RESEARCH]" in hint
    assert "web_search" in hint
    assert "fetch_url" in hint
    assert "Do not answer only from search snippets" in hint
    assert "do NOT claim that internet search" in hint


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
async def test_builtin_executor_adds_follow_up_guidance_for_web_search() -> None:
    with patch.object(
        BuiltinToolExecutor,
        "_web_search",
        return_value="Search results for: OpenAI\n\n1. Example",
    ):
        executor = BuiltinToolExecutor()
        definition = ToolDefinition(name="web_search", description="Search the web")
        result = await executor.execute(
            definition,
            "call_search",
            {"query": "OpenAI", "max_results": 3},
        )

    assert result.success is True
    assert result.llm_follow_up_message is not None
    assert "Do not call web_search again" in result.llm_follow_up_message
    assert "call fetch_url" in result.llm_follow_up_message
    assert "multiple articles" in result.llm_follow_up_message


@pytest.mark.asyncio
async def test_builtin_executor_adds_follow_up_guidance_for_fetch_url() -> None:
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
    assert result.llm_follow_up_message is not None
    assert "Do not call fetch_url again for the same URL" in result.llm_follow_up_message
    assert "Use the fetched content above to answer directly" in result.llm_follow_up_message
    assert "another distinct relevant URL" in result.llm_follow_up_message


@pytest.mark.asyncio
async def test_builtin_executor_adds_retry_guardance_for_failed_fetch_url() -> None:
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
    assert result.llm_follow_up_message is not None
    assert "Do not call fetch_url again for the same URL" in result.llm_follow_up_message
    assert "choose a different URL" in result.llm_follow_up_message


def _async_return(value: str):
    async def _inner(**_kwargs):
        return value

    return _inner()
