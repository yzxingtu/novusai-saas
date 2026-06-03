from __future__ import annotations

from unittest.mock import AsyncMock

import httpx
import pytest

from app.core.config import settings
from app.plugins.exceptions import PluginError
from app.plugins.marketplace import MarketplaceClient


class _Resp404:
    status_code = 404


class _Always404AsyncClient:
    def __init__(self, *args, **kwargs):
        del args, kwargs

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        del exc_type, exc, tb
        return False

    async def get(self, url: str):
        del url
        return _Resp404()


@pytest.mark.asyncio
async def test_fetch_plugin_detail_fallback_to_registry(
    monkeypatch: pytest.MonkeyPatch,
):
    client = MarketplaceClient(db=None)
    client._get_cached = AsyncMock(return_value=None)  # type: ignore[attr-defined]
    client._set_cached = AsyncMock()  # type: ignore[attr-defined]
    client._select_source = AsyncMock(return_value="https://example.test")  # type: ignore[attr-defined]
    client.fetch_registry = AsyncMock(  # type: ignore[method-assign]
        return_value=[
            {
                "slug": "example-weather",
                "name": "example-weather",
                "version": "1.0.0",
                "download_url": "https://example.test/example-weather-1.0.0.zip",
            }
        ]
    )

    monkeypatch.setattr(
        "app.plugins.marketplace.httpx.AsyncClient",
        _Always404AsyncClient,
    )

    detail = await client.fetch_plugin_detail("example-weather")
    assert detail is not None
    assert detail["slug"] == "example-weather"
    client._set_cached.assert_awaited_once()  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_fetch_plugin_detail_returns_none_when_not_found(
    monkeypatch: pytest.MonkeyPatch,
):
    client = MarketplaceClient(db=None)
    client._get_cached = AsyncMock(return_value=None)  # type: ignore[attr-defined]
    client._set_cached = AsyncMock()  # type: ignore[attr-defined]
    client._select_source = AsyncMock(return_value="https://example.test")  # type: ignore[attr-defined]
    client.fetch_registry = AsyncMock(  # type: ignore[method-assign]
        return_value=[{"slug": "another-plugin", "name": "another-plugin"}]
    )

    monkeypatch.setattr(
        "app.plugins.marketplace.httpx.AsyncClient",
        _Always404AsyncClient,
    )

    detail = await client.fetch_plugin_detail("example-weather")
    assert detail is None


@pytest.mark.asyncio
async def test_download_plugin_rejects_non_github_download_url():
    client = MarketplaceClient(db=None)
    client.fetch_plugin_detail = AsyncMock(  # type: ignore[method-assign]
        return_value={
            "slug": "example-weather",
            "download_url": "https://evil.example/download.zip",
        }
    )

    with pytest.raises(PluginError, match="hosted on GitHub"):
        await client.download_plugin("example-weather", "1.0.0")


@pytest.mark.asyncio
async def test_download_plugin_rejects_non_github_repository_fallback():
    client = MarketplaceClient(db=None)
    client.fetch_plugin_detail = AsyncMock(  # type: ignore[method-assign]
        return_value={
            "slug": "example-weather",
            "repository_url": "https://gitee.com/example/weather",
        }
    )

    with pytest.raises(PluginError, match="No download URL available"):
        await client.download_plugin("example-weather", "1.0.0")


@pytest.mark.asyncio
async def test_download_plugin_does_not_fallback_to_debug_stub_on_retry_exhaustion(
    monkeypatch: pytest.MonkeyPatch,
):
    client = MarketplaceClient(db=None)
    client.fetch_plugin_detail = AsyncMock(  # type: ignore[method-assign]
        return_value={
            "slug": "debug-probe",
            "download_url": "https://github.com/example/debug-probe/releases/download/v1.0.0/debug-probe-1.0.0.zip",
        }
    )

    async def _always_fail(*_args, **_kwargs):
        raise httpx.ConnectError("boom")

    monkeypatch.setattr(
        "app.plugins.marketplace.open_github_only_stream",
        _always_fail,
    )

    original_debug = settings.DEBUG
    settings.DEBUG = True
    try:
        with pytest.raises(PluginError, match="Failed to download plugin"):
            await client.download_plugin("debug-probe", "1.0.0")
    finally:
        settings.DEBUG = original_debug
