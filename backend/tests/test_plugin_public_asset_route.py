"""Plugin public asset route tests. / 插件公共资源路由测试。"""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from starlette.requests import Request

from app.main import create_application


class _AsyncSessionFactoryStub:
    async def __aenter__(self):
        return object()

    async def __aexit__(self, exc_type, exc, tb):
        return False


def _build_request(
    path: str,
    *,
    host: str = "tenant.example.com",
    method: str = "GET",
) -> Request:
    return Request(
        {
            "type": "http",
            "method": method,
            "path": path,
            "headers": [(b"host", host.encode("utf-8"))],
            "query_string": b"",
        }
    )


def _get_public_asset_endpoint():
    app = create_application().other_asgi_app
    route = next(
        route
        for route in app.routes
        if getattr(route, "path", None)
        == "/plugin-public-assets/{public_endpoint}/{plugin_name}/{file_path:path}"
    )
    return route.endpoint


def _assert_cookie_cleanup_headers(response) -> None:
    set_cookie_headers = response.headers.getlist("set-cookie")
    assert any("novus_plugin_asset_token=" in header for header in set_cookie_headers)
    assert any("Path=/" in header for header in set_cookie_headers)
    assert any("Path=/plugin-assets" in header for header in set_cookie_headers)
    assert any("Path=/plugin-icons" in header for header in set_cookie_headers)
    assert any("Path=/plugin-public-assets" in header for header in set_cookie_headers)
    assert any("Domain=tenant.example.com" in header for header in set_cookie_headers)
    assert any("Domain=example.com" in header for header in set_cookie_headers)


def _assert_public_asset_fail_closed_response(response) -> None:
    assert response.status_code == 404
    assert response.headers["Cache-Control"] == "private, no-store, max-age=0"
    assert response.headers["Vary"] == "Host, Authorization, Cookie"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    _assert_cookie_cleanup_headers(response)


@pytest.mark.asyncio
async def test_public_plugin_asset_route_varies_by_host(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    endpoint = _get_public_asset_endpoint()

    monkeypatch.setattr(
        "app.core.database.async_session_factory",
        _AsyncSessionFactoryStub,
    )
    monkeypatch.setattr(
        "app.plugins.asset_runtime.authorize_public_captcha_asset_request",
        AsyncMock(return_value=SimpleNamespace(allowed=True)),
    )

    with TemporaryDirectory() as temp_dir:
        asset_file = Path(temp_dir) / "plugin.js"
        asset_file.write_text("console.log('ok');", encoding="utf-8")
        monkeypatch.setattr(
            "app.plugins.asset_resolver.resolve_plugin_asset_file",
            lambda *_args, **_kwargs: asset_file,
        )

        response = await endpoint(
            "tenant",
            "demo-plugin",
            "assets/plugin.js",
            _build_request("/plugin-public-assets/tenant/demo-plugin/assets/plugin.js"),
        )

    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "public, max-age=300, must-revalidate"
    assert response.headers["Vary"] == "Host, Authorization, Cookie"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    _assert_cookie_cleanup_headers(response)


@pytest.mark.asyncio
async def test_public_plugin_asset_route_clears_cookie_on_invalid_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    endpoint = _get_public_asset_endpoint()
    authorize_mock = AsyncMock(side_effect=AssertionError("authorize should not be called"))
    monkeypatch.setattr(
        "app.plugins.asset_runtime.authorize_public_captcha_asset_request",
        authorize_mock,
    )

    response = await endpoint(
        "tenant",
        "demo-plugin",
        ".",
        _build_request("/plugin-public-assets/tenant/demo-plugin/."),
    )

    _assert_public_asset_fail_closed_response(response)
    assert authorize_mock.await_count == 0


@pytest.mark.asyncio
async def test_public_plugin_asset_route_clears_cookie_on_denied_access(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    endpoint = _get_public_asset_endpoint()

    monkeypatch.setattr(
        "app.core.database.async_session_factory",
        _AsyncSessionFactoryStub,
    )
    monkeypatch.setattr(
        "app.plugins.asset_runtime.authorize_public_captcha_asset_request",
        AsyncMock(return_value=SimpleNamespace(allowed=False)),
    )
    monkeypatch.setattr(
        "app.plugins.asset_resolver.resolve_plugin_asset_file",
        lambda *_args, **_kwargs: pytest.fail("asset resolver should not be called"),
    )

    response = await endpoint(
        "tenant",
        "demo-plugin",
        "assets/plugin.js",
        _build_request("/plugin-public-assets/tenant/demo-plugin/assets/plugin.js"),
    )

    _assert_public_asset_fail_closed_response(response)


@pytest.mark.asyncio
async def test_public_plugin_asset_route_clears_cookie_on_missing_asset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    endpoint = _get_public_asset_endpoint()

    monkeypatch.setattr(
        "app.core.database.async_session_factory",
        _AsyncSessionFactoryStub,
    )
    monkeypatch.setattr(
        "app.plugins.asset_runtime.authorize_public_captcha_asset_request",
        AsyncMock(return_value=SimpleNamespace(allowed=True)),
    )
    monkeypatch.setattr(
        "app.plugins.asset_resolver.resolve_plugin_asset_file",
        lambda *_args, **_kwargs: None,
    )

    response = await endpoint(
        "tenant",
        "demo-plugin",
        "assets/missing.js",
        _build_request("/plugin-public-assets/tenant/demo-plugin/assets/missing.js"),
    )

    _assert_public_asset_fail_closed_response(response)
