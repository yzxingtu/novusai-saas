from __future__ import annotations

import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.api.admin.plugin_admin_contracts import PluginInstallConfirmBody
from app.api.admin.plugins import AdminPluginController
from app.services.system import plugin_install_preview_service


def _get_endpoint(path: str, method: str):
    router = AdminPluginController.get_router()
    for route in router.routes:
        if getattr(route, "path", None) == path and method in route.methods:
            return route.endpoint
    raise AssertionError(f"Route not found: {method} {path}")


@pytest.mark.asyncio
async def test_preview_install_route_delegates_to_preview_service(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(AdminPluginController, "_instance", None)
    monkeypatch.setattr(AdminPluginController, "_router", None)

    preview_result = {"preview": {"name": "demo-plugin"}, "preview_token": "token"}
    preview_service = SimpleNamespace(
        preview_upload_install=AsyncMock(return_value=preview_result),
    )

    def fake_service(_db):
        return preview_service

    monkeypatch.setattr(
        plugin_install_preview_service,
        "PluginInstallPreviewService",
        fake_service,
    )

    install_preview_module = sys.modules.get("app.api.admin.plugin_install_preview")
    if install_preview_module is not None:
        monkeypatch.setattr(
            install_preview_module,
            "PluginInstallPreviewService",
            fake_service,
            raising=False,
        )

    endpoint = _get_endpoint("/plugins/preview", "POST")
    upload = SimpleNamespace(
        read=AsyncMock(return_value=b"zip-bytes"),
        filename="demo.zip",
    )

    response = await endpoint(upload, AsyncMock(), SimpleNamespace(id=11))

    assert response["code"] == 0
    assert response["data"] == preview_result
    preview_service.preview_upload_install.assert_awaited_once()
    kwargs = preview_service.preview_upload_install.await_args.kwargs
    assert kwargs["content"] == b"zip-bytes"
    assert kwargs["filename"] == "demo.zip"
    assert kwargs["admin_id"] == 11


@pytest.mark.asyncio
async def test_marketplace_preview_install_route_delegates_to_service(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(AdminPluginController, "_instance", None)
    monkeypatch.setattr(AdminPluginController, "_router", None)

    preview_result = {"preview": {"name": "weather-widget"}, "preview_token": "token"}
    preview_service = SimpleNamespace(
        marketplace_preview_install=AsyncMock(return_value=preview_result),
    )

    def fake_service(_db):
        return preview_service

    monkeypatch.setattr(
        plugin_install_preview_service,
        "PluginInstallPreviewService",
        fake_service,
    )

    install_preview_module = sys.modules.get("app.api.admin.plugin_install_preview")
    if install_preview_module is not None:
        monkeypatch.setattr(
            install_preview_module,
            "PluginInstallPreviewService",
            fake_service,
            raising=False,
        )

    endpoint = _get_endpoint("/plugins/marketplace/{slug}/install", "POST")
    response = await endpoint("weather-widget", AsyncMock(), SimpleNamespace(id=7))

    assert response["code"] == 0
    assert response["data"] == preview_result
    preview_service.marketplace_preview_install.assert_awaited_once_with(
        slug="weather-widget",
        admin_id=7,
    )


@pytest.mark.asyncio
async def test_marketplace_confirm_install_route_delegates_to_service(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(AdminPluginController, "_instance", None)
    monkeypatch.setattr(AdminPluginController, "_router", None)

    install_result = {"id": 9, "name": "weather-widget"}
    preview_service = SimpleNamespace(
        marketplace_confirm_install=AsyncMock(return_value=install_result),
    )

    def fake_service(_db):
        return preview_service

    monkeypatch.setattr(
        plugin_install_preview_service,
        "PluginInstallPreviewService",
        fake_service,
    )

    install_preview_module = sys.modules.get("app.api.admin.plugin_install_preview")
    if install_preview_module is not None:
        monkeypatch.setattr(
            install_preview_module,
            "PluginInstallPreviewService",
            fake_service,
            raising=False,
        )

    body = PluginInstallConfirmBody(
        config={"enabled": True},
        preview_token="preview-token",
    )
    endpoint = _get_endpoint("/plugins/marketplace/{slug}/confirm-install", "POST")
    response = await endpoint(
        "weather-widget",
        body,
        AsyncMock(),
        SimpleNamespace(id=13),
    )

    assert response["code"] == 0
    assert response["data"] == install_result
    preview_service.marketplace_confirm_install.assert_awaited_once_with(
        slug="weather-widget",
        body=body,
        admin_id=13,
    )
