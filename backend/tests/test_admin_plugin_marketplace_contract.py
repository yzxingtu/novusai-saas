from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.api.admin.plugins import (
    AdminPluginController,
    PluginInstallConfirmBody,
    _create_install_preview_token,
)
from app.core.i18n import _, set_locale
from app.exceptions.base import ValidationException
from app.plugins.preview import InstallPreview


def _get_endpoint(path: str, method: str):
    router = AdminPluginController.get_router()
    for route in router.routes:
        if getattr(route, "path", None) == path and method in route.methods:
            return route.endpoint
    raise AssertionError(f"Route not found: {method} {path}")


@pytest.fixture(autouse=True)
def _use_english_locale():
    set_locale("en")
    yield
    set_locale("zh_CN")


@pytest.mark.asyncio
async def test_marketplace_preview_install_returns_preview_token(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(AdminPluginController, "_instance", None)
    monkeypatch.setattr(AdminPluginController, "_router", None)

    staging_dir = tmp_path / "marketplace"
    staging_dir.mkdir()
    zip_path = staging_dir / "weather-widget-1.2.3.zip"
    zip_path.write_bytes(b"zip")
    plugin_dir = staging_dir / "extracted" / "weather-widget"
    plugin_dir.mkdir(parents=True)

    client = SimpleNamespace(
        fetch_plugin_detail=AsyncMock(
            return_value={"name": "weather-widget", "version": "1.2.3"}
        ),
        download_plugin=AsyncMock(return_value=zip_path),
    )
    loader = SimpleNamespace(
        load_manifest_from_path=lambda _plugin_dir: SimpleNamespace(
            name="weather-widget", version="1.2.3"
        )
    )

    monkeypatch.setattr(
        "app.plugins.marketplace.MarketplaceClient",
        lambda _db: client,
    )
    monkeypatch.setattr(
        "app.plugins.package_security.extract_plugin_zip_safely",
        lambda _zip_path, _extract_dir: plugin_dir,
    )
    monkeypatch.setattr("app.plugins.loader.PluginLoader", lambda **_kwargs: loader)
    monkeypatch.setattr(
        "app.plugins.preview.generate_preview",
        AsyncMock(return_value=InstallPreview(plugin_info={"name": "weather-widget"})),
    )

    endpoint = _get_endpoint("/plugins/marketplace/{slug}/install", "POST")
    response = await endpoint("weather-widget", AsyncMock(), SimpleNamespace(id=9))

    assert response["data"]["preview_token"]


@pytest.mark.asyncio
async def test_marketplace_confirm_install_requires_preview_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(AdminPluginController, "_instance", None)
    monkeypatch.setattr(AdminPluginController, "_router", None)

    endpoint = _get_endpoint("/plugins/marketplace/{slug}/confirm-install", "POST")

    with pytest.raises(ValidationException) as exc:
        await endpoint(
            "weather-widget",
            PluginInstallConfirmBody(config={}, preview_token=""),
            AsyncMock(),
            SimpleNamespace(id=7),
        )

    assert exc.value.message == _("plugin.error.install_preview_required")


@pytest.mark.asyncio
async def test_marketplace_confirm_install_rejects_stale_preview_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(AdminPluginController, "_instance", None)
    monkeypatch.setattr(AdminPluginController, "_router", None)

    client = SimpleNamespace(
        fetch_plugin_detail=AsyncMock(
            return_value={"name": "weather-widget", "version": "2.0.0"}
        ),
        download_plugin=AsyncMock(),
    )
    monkeypatch.setattr(
        "app.plugins.marketplace.MarketplaceClient",
        lambda _db: client,
    )

    endpoint = _get_endpoint("/plugins/marketplace/{slug}/confirm-install", "POST")
    preview_token = _create_install_preview_token(
        source="marketplace",
        plugin_name="weather-widget",
        version="1.2.3",
        admin_id=7,
        marketplace_slug="weather-widget",
    )

    with pytest.raises(ValidationException) as exc:
        await endpoint(
            "weather-widget",
            PluginInstallConfirmBody(
                config={},
                preview_token=preview_token,
            ),
            AsyncMock(),
            SimpleNamespace(id=7),
        )

    assert exc.value.message == _("plugin.error.install_preview_stale")
    client.download_plugin.assert_not_awaited()
