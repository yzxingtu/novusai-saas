"""Runtime adapter registration tests for plugin extension bridge."""

from __future__ import annotations

from typing import Sequence

import pytest

import app.plugins._extension_registrar as registrar
from app.ai.adapters import AdapterRegistry
from app.plugins.manifest import PluginManifest
from app.plugins.registry import ExtensionRegistry


def _build_adapter_manifest(provider_code: str = "test-provider") -> PluginManifest:
    return PluginManifest.model_validate(
        {
            "name": "adapter-plugin",
            "version": "1.0.0",
            "display_name": {"en": "Adapter Plugin"},
            "scope": "admin_only",
            "extensions": {
                "adapters": [
                    {
                        "provider_code": provider_code,
                        "entry_point": "adapters.fake_adapter.FakeAdapter",
                        "supported_models": ["gpt-4"],
                    }
                ]
            },
        }
    )


def _clear_adapter_registry() -> None:
    for provider_type in list(AdapterRegistry.list_adapters()):
        AdapterRegistry.unregister(provider_type)


@pytest.fixture(autouse=True)
def _reset_extension_state() -> Sequence[None]:
    ExtensionRegistry.reset()
    registrar._failed_extensions.clear()
    _clear_adapter_registry()
    yield
    ExtensionRegistry.reset()
    registrar._failed_extensions.clear()
    _clear_adapter_registry()


def test_register_all_extensions_bridges_adapters(monkeypatch) -> None:
    manifest = _build_adapter_manifest()
    registry = ExtensionRegistry.get_instance()

    class FakeAdapter:
        pass

    monkeypatch.setattr(
        registrar,
        "_load_handler",
        lambda *_: FakeAdapter,
    )

    count = registrar.register_all_extensions(registry, manifest, "adapter-plugin")

    assert count == 1
    assert AdapterRegistry.get_adapter("test-provider") is FakeAdapter
    assert registrar.get_failed_extensions("adapter-plugin") == []


def test_unsubscribe_unregisters_adapter(monkeypatch) -> None:
    manifest = _build_adapter_manifest()
    registry = ExtensionRegistry.get_instance()

    class FakeAdapter:
        pass

    monkeypatch.setattr(
        registrar,
        "_load_handler",
        lambda *_: FakeAdapter,
    )

    registrar.register_all_extensions(registry, manifest, "adapter-plugin")
    registry.unregister_all("adapter-plugin")

    assert AdapterRegistry.get_adapter("test-provider") is None
