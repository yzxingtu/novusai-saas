from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.ai.tools.executors.http_executor import HttpToolExecutor
from app.ai.tools.types import ToolDefinition
from app.core.config import settings
from app.middleware.trace import trace_id_var


class _FakeResponse:
    def __init__(self, status_code: int, text: str = "", headers: dict[str, str] | None = None):
        self.status_code = status_code
        self.text = text
        self.headers = headers or {}

    def json(self):
        return {}


class _FakeClient:
    def __init__(self, response: _FakeResponse):
        self._response = response

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def request(self, **kwargs):
        _ = kwargs
        return self._response


@pytest.mark.asyncio
async def test_http_executor_blocks_redirect_response():
    executor = HttpToolExecutor()
    definition = ToolDefinition(
        name="http_tool",
        description="HTTP tool",
        config={"_http_url": "https://example.com"},
    )
    fake_response = _FakeResponse(
        302,
        headers={"location": "http://169.254.169.254/latest/meta-data"},
    )

    with patch(
        "app.ai.tools.executors.http_executor.UrlValidator.validate",
        new=AsyncMock(return_value=None),
    ), patch(
        "httpx.AsyncClient",
        return_value=_FakeClient(fake_response),
    ):
        result = await executor.execute(
            definition=definition,
            tool_call_id="tc_http_redirect",
            arguments={},
        )

    assert result.success is False
    assert "redirect blocked" in (result.error or "").lower()


@pytest.mark.asyncio
async def test_http_executor_hides_generic_exception_detail_in_production():
    executor = HttpToolExecutor()
    definition = ToolDefinition(
        name="http_tool",
        description="HTTP tool",
        config={"_http_url": "https://example.com"},
    )
    original_debug = settings.DEBUG
    token = trace_id_var.set("trace-http-prod")
    settings.DEBUG = False
    try:
        with patch(
            "app.ai.tools.executors.http_executor.UrlValidator.validate",
            new=AsyncMock(return_value=None),
        ), patch(
            "httpx.AsyncClient",
            side_effect=RuntimeError("socket exploded"),
        ):
            result = await executor.execute(
                definition=definition,
                tool_call_id="tc_http_error",
                arguments={},
            )
    finally:
        settings.DEBUG = original_debug
        trace_id_var.reset(token)

    assert result.success is False
    assert "socket exploded" not in (result.error or "")
    assert "trace-http-prod" in (result.error or "")
