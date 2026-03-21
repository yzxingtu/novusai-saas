"""Plugin asset runtime gate regression tests. / 插件静态资源运行时闸门回归测试。"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import ANY, AsyncMock

import pytest
from starlette.requests import Request

from app.plugins.asset_runtime import (
    authorize_plugin_asset_request,
    authorize_plugin_icon_request,
    extract_plugin_asset_access_token,
)


def _build_request(
    *,
    headers: dict[str, str] | None = None,
    query_string: str = "",
) -> Request:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/plugin-assets/demo/icon.png",
        "headers": [
            (key.lower().encode("utf-8"), value.encode("utf-8"))
            for key, value in (headers or {}).items()
        ],
        "query_string": query_string.encode("utf-8"),
    }
    return Request(scope)


def test_extract_plugin_asset_access_token_prefers_bearer_header() -> None:
    request = _build_request(
        headers={"Authorization": "Bearer header-token"},
    )

    assert extract_plugin_asset_access_token(request) == "header-token"


def test_extract_plugin_asset_access_token_falls_back_to_cookie() -> None:
    request = _build_request(headers={"Cookie": "novus_plugin_asset_token=cookie-token"})

    assert extract_plugin_asset_access_token(request) == "cookie-token"


@pytest.mark.asyncio
async def test_authorize_plugin_asset_request_accepts_admin_cookie_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    decode = AsyncMock(
        return_value={"type": "access", "scope": "admin", "sub": "1"},
    )
    gate = AsyncMock(
        return_value=SimpleNamespace(allowed=True, reason_code="allowed"),
    )
    monkeypatch.setattr("app.plugins.asset_runtime.decode_token", decode)
    monkeypatch.setattr(
        "app.plugins.asset_runtime.evaluate_plugin_runtime_gate",
        gate,
    )

    result = await authorize_plugin_asset_request(
        AsyncMock(),
        _build_request(headers={"Cookie": "novus_plugin_asset_token=admin-token"}),
        "demo-plugin",
    )

    assert result.allowed is True
    assert result.token_scope == "admin"
    assert result.tenant_id is None
    gate.assert_awaited_once_with(
        ANY,
        "demo-plugin",
        tenant_id=None,
        require_enabled=True,
        enforce_scope=False,
    )


@pytest.mark.asyncio
async def test_authorize_plugin_asset_request_enforces_tenant_scope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    decode = AsyncMock(
        return_value={
            "type": "access",
            "scope": "tenant_admin",
            "tenant_id": 42,
            "sub": "7",
        },
    )
    gate = AsyncMock(
        return_value=SimpleNamespace(allowed=True, reason_code="allowed"),
    )
    monkeypatch.setattr("app.plugins.asset_runtime.decode_token", decode)
    monkeypatch.setattr(
        "app.plugins.asset_runtime.evaluate_plugin_runtime_gate",
        gate,
    )

    result = await authorize_plugin_asset_request(
        AsyncMock(),
        _build_request(headers={"Authorization": "Bearer tenant-token"}),
        "demo-plugin",
    )

    assert result.allowed is True
    assert result.token_scope == "tenant_admin"
    assert result.tenant_id == 42
    gate.assert_awaited_once_with(
        ANY,
        "demo-plugin",
        tenant_id=42,
        require_enabled=True,
        enforce_scope=True,
    )


@pytest.mark.asyncio
async def test_authorize_plugin_asset_request_rejects_missing_or_invalid_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.plugins.asset_runtime.decode_token",
        AsyncMock(return_value=None),
    )
    gate = AsyncMock()
    monkeypatch.setattr(
        "app.plugins.asset_runtime.evaluate_plugin_runtime_gate",
        gate,
    )

    missing = await authorize_plugin_asset_request(
        AsyncMock(),
        _build_request(),
        "demo-plugin",
    )
    invalid = await authorize_plugin_asset_request(
        AsyncMock(),
        _build_request(headers={"Cookie": "novus_plugin_asset_token=bad-token"}),
        "demo-plugin",
    )

    assert missing.allowed is False
    assert missing.reason_code == "missing_token"
    assert invalid.allowed is False
    assert invalid.reason_code == "invalid_token"
    gate.assert_not_awaited()


@pytest.mark.asyncio
async def test_authorize_plugin_asset_request_rejects_unsupported_scope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.plugins.asset_runtime.decode_token",
        AsyncMock(
            return_value={"type": "access", "scope": "tenant_user", "tenant_id": 7},
        ),
    )
    gate = AsyncMock()
    monkeypatch.setattr(
        "app.plugins.asset_runtime.evaluate_plugin_runtime_gate",
        gate,
    )

    result = await authorize_plugin_asset_request(
        AsyncMock(),
        _build_request(headers={"Cookie": "novus_plugin_asset_token=user-token"}),
        "demo-plugin",
    )

    assert result.allowed is False
    assert result.reason_code == "unsupported_scope"
    gate.assert_not_awaited()


@pytest.mark.asyncio
async def test_authorize_plugin_asset_request_propagates_gate_denial(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.plugins.asset_runtime.decode_token",
        AsyncMock(return_value={"type": "access", "scope": "admin"}),
    )
    monkeypatch.setattr(
        "app.plugins.asset_runtime.evaluate_plugin_runtime_gate",
        AsyncMock(
            return_value=SimpleNamespace(
                allowed=False,
                reason_code="license_inactive",
            ),
        ),
    )

    result = await authorize_plugin_asset_request(
        AsyncMock(),
        _build_request(headers={"Cookie": "novus_plugin_asset_token=admin-token"}),
        "demo-plugin",
    )

    assert result.allowed is False
    assert result.reason_code == "license_inactive"


@pytest.mark.asyncio
async def test_authorize_plugin_icon_request_allows_admin_for_disabled_plugin_icon(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.plugins.asset_runtime.decode_token",
        AsyncMock(return_value={"type": "access", "scope": "admin", "sub": "1"}),
    )
    db = AsyncMock()
    db.execute = AsyncMock(return_value=SimpleNamespace(scalar_one_or_none=lambda: 99))

    result = await authorize_plugin_icon_request(
        db,
        _build_request(headers={"Cookie": "novus_plugin_asset_token=admin-token"}),
        "weather-widget",
    )

    assert result.allowed is True
    assert result.reason_code == "allowed"


@pytest.mark.asyncio
async def test_authorize_plugin_icon_request_rejects_non_admin_scope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.plugins.asset_runtime.decode_token",
        AsyncMock(return_value={"type": "access", "scope": "tenant_admin", "tenant_id": 7}),
    )
    db = AsyncMock()

    result = await authorize_plugin_icon_request(
        db,
        _build_request(headers={"Cookie": "novus_plugin_asset_token=tenant-token"}),
        "weather-widget",
    )

    assert result.allowed is False
    assert result.reason_code == "unsupported_scope"
    db.execute.assert_not_awaited()
