from unittest.mock import patch

import httpx
import pytest

from app.ai.engine.base import BaseEngine
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
