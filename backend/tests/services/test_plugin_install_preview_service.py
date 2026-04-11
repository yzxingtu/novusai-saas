from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.core.i18n import _, set_locale
from app.exceptions.base import ValidationException
from app.plugins.exceptions import PluginInstallError
from app.plugins.preview import InstallPreview
from app.services.system import PluginInstallPreviewService
from app.services.system.plugin_install_preview_service import (
    assert_install_preview_token,
    assert_marketplace_package_identity,
    create_install_preview_token,
    decode_install_preview_token,
    sanitize_marketplace_slug,
)


@pytest.fixture(autouse=True)
def _use_english_locale():
    set_locale("en")
    yield
    set_locale("zh_CN")


def test_sanitize_marketplace_slug_rejects_invalid_slug() -> None:
    slug = "bad/slug"

    with pytest.raises(ValidationException) as exc:
        sanitize_marketplace_slug(slug)

    assert exc.value.message == _("plugin.error.invalid_marketplace_slug").format(
        slug=slug,
    )


def test_marketplace_package_identity_accepts_matching_manifest() -> None:
    manifest = SimpleNamespace(name="weather-widget", version="1.2.3")

    assert_marketplace_package_identity(
        slug="weather-widget",
        detail={"name": "weather-widget", "version": "1.2.3"},
        manifest=manifest,
    )


def test_marketplace_package_identity_rejects_manifest_name_mismatch() -> None:
    manifest = SimpleNamespace(name="other-plugin", version="1.2.3")

    with pytest.raises(PluginInstallError, match="expected plugin 'weather-widget'"):
        assert_marketplace_package_identity(
            slug="weather-widget",
            detail={"name": "weather-widget", "version": "1.2.3"},
            manifest=manifest,
        )


def test_marketplace_package_identity_rejects_manifest_version_mismatch() -> None:
    manifest = SimpleNamespace(name="weather-widget", version="9.9.9")

    with pytest.raises(PluginInstallError, match="expected '1.2.3'"):
        assert_marketplace_package_identity(
            slug="weather-widget",
            detail={"name": "weather-widget", "version": "1.2.3"},
            manifest=manifest,
        )


def test_install_preview_token_round_trip_accepts_matching_marketplace_context() -> None:
    token = create_install_preview_token(
        source="marketplace",
        plugin_name="weather-widget",
        version="1.2.3",
        admin_id=7,
        marketplace_slug="weather-widget",
    )

    payload = decode_install_preview_token(token)

    assert_install_preview_token(
        payload,
        source="marketplace",
        plugin_name="weather-widget",
        version="1.2.3",
        admin_id=7,
        marketplace_slug="weather-widget",
    )


@pytest.mark.asyncio
async def test_marketplace_list_clamps_page_bounds(
    mock_db,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = SimpleNamespace(
        list_plugins=AsyncMock(return_value={"items": [{"name": "demo"}], "total": 1})
    )
    monkeypatch.setattr(
        "app.plugins.marketplace.MarketplaceClient",
        lambda _db: client,
    )

    service = PluginInstallPreviewService(mock_db)
    result = await service.marketplace_list(
        category="",
        sort="",
        search="",
        page_number=0,
        page_size=999,
    )

    assert result["page"] == 1
    assert result["page_size"] == 100
    assert result["total"] == 1
    client.list_plugins.assert_awaited_once_with(
        search="",
        category="",
        sort="",
        page_number=1,
        page_size=100,
    )


@pytest.mark.asyncio
async def test_preview_upload_install_sets_preview_token_and_cleans_tmp(
    mock_db,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    staging_dir = tmp_path / "staging"
    plugin_dir = staging_dir / "demo-plugin"
    plugin_dir.mkdir(parents=True)

    monkeypatch.setattr(
        "app.services.system.plugin_install_preview_service.extract_plugin_from_zip",
        lambda _content, _filename: (staging_dir, plugin_dir),
    )

    manifest = SimpleNamespace(name="demo-plugin", version="1.2.3")
    loader = SimpleNamespace(load_manifest_from_path=lambda _path: manifest)
    monkeypatch.setattr("app.plugins.loader.PluginLoader", lambda **_kwargs: loader)

    preview = InstallPreview(plugin_info={"name": "demo-plugin"})
    generate_preview = AsyncMock(return_value=preview)
    monkeypatch.setattr("app.plugins.preview.generate_preview", generate_preview)

    service = PluginInstallPreviewService(mock_db)
    payload = await service.preview_upload_install(
        content=b"zip",
        filename="demo.zip",
        admin_id=9,
    )

    assert payload["preview_token"]
    generate_preview.assert_awaited_once_with(plugin_dir, loader, db=mock_db)
    assert not staging_dir.exists()
