"""API dispatcher 中 PluginContext 信任边界行为的回归测试。"""

from __future__ import annotations

from unittest.mock import MagicMock

from app.plugins.api_dispatcher import _build_plugin_context
from app.plugins.manifest import PluginManifest


def _minimal_manifest_data(plugin_name: str = "demo-plugin") -> dict:
    manifest = PluginManifest(
        name=plugin_name,
        version="1.0.0",
        display_name={"en": "Demo Plugin"},
        scope="all_tenants",
    )
    return manifest.model_dump()


def test_build_plugin_context_uses_db_manifest_in_production(
    monkeypatch,
) -> None:
    manifest_data = _minimal_manifest_data()
    captured: dict[str, object] = {}

    class _Loader:
        def load_manifest(self, plugin_name: str):
            _ = plugin_name
            raise AssertionError("production mode must not load manifest from disk")

    def _fake_create_plugin_context(**kwargs):
        captured.update(kwargs)
        return {"ok": True}

    monkeypatch.setattr("app.plugins.api_dispatcher._get_plugin_loader", lambda: _Loader())
    monkeypatch.setattr("app.plugins.api_dispatcher.settings.DEBUG", False, raising=False)
    monkeypatch.setattr(
        "app.plugins.context_factory.create_plugin_context",
        _fake_create_plugin_context,
    )

    result = _build_plugin_context(
        plugin_name="demo-plugin",
        manifest_data=manifest_data,
        granted_capabilities=["db:own_tables"],
        db=MagicMock(),
        tenant_id=1,
        user_id=2,
        user_role="tenant_admin",
        request_id="req-1",
    )

    assert result == {"ok": True}
    manifest = captured["manifest"]
    assert isinstance(manifest, PluginManifest)
    assert manifest.name == "demo-plugin"


def test_build_plugin_context_debug_falls_back_to_db_manifest_on_loader_error(
    monkeypatch,
) -> None:
    manifest_data = _minimal_manifest_data("debug-plugin")

    class _BrokenLoader:
        def load_manifest(self, plugin_name: str):
            _ = plugin_name
            raise RuntimeError("disk manifest unavailable")

    captured: dict[str, object] = {}

    def _fake_create_plugin_context(**kwargs):
        captured.update(kwargs)
        return {"ok": True}

    monkeypatch.setattr("app.plugins.api_dispatcher._get_plugin_loader", lambda: _BrokenLoader())
    monkeypatch.setattr("app.plugins.api_dispatcher.settings.DEBUG", True, raising=False)
    monkeypatch.setattr(
        "app.plugins.context_factory.create_plugin_context",
        _fake_create_plugin_context,
    )

    result = _build_plugin_context(
        plugin_name="debug-plugin",
        manifest_data=manifest_data,
        granted_capabilities=[],
        db=MagicMock(),
    )

    assert result == {"ok": True}
    manifest = captured["manifest"]
    assert isinstance(manifest, PluginManifest)
    assert manifest.name == "debug-plugin"
