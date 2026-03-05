from __future__ import annotations

import zipfile
from unittest.mock import AsyncMock

import pytest

from app.plugins.marketplace import MarketplaceClient
from app.plugins.package_security import validate_plugin_zip_archive


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
async def test_fetch_plugin_detail_fallback_to_registry(monkeypatch: pytest.MonkeyPatch):
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
async def test_fetch_plugin_detail_returns_none_when_not_found(monkeypatch: pytest.MonkeyPatch):
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


def test_build_debug_stub_package_creates_valid_zip(tmp_path):
    client = MarketplaceClient(db=None)
    zip_path = client._build_debug_stub_package(
        tmp_dir=tmp_path,
        slug="debug-probe",
        version="1.0.0",
        detail={
            "display_name": "Debug Probe",
            "description": "stub package for tests",
        },
    )

    assert zip_path.is_file()
    validate_plugin_zip_archive(zip_path)

    with zipfile.ZipFile(zip_path, "r") as zf:
        names = set(zf.namelist())
        assert "plugin.yaml" in names
        assert "backend/main.py" in names
        assert "backend/__init__.py" in names
