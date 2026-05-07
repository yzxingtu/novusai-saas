"""Storage plugin runtime evidence test."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.plugins import _extension_registrar as registrar
from app.plugins.context import PluginContext
from app.plugins.manifest import PluginManifest
from app.plugins.registry import ExtensionRegistry
from app.storage.base import StorageDriver
from app.storage.manager import storage_manager


class FakeStorageConfig:
    """StorageConfig stub that tolerates missing root_path."""

    def __init__(self, driver, root_path="plugins", base_url=None, options=None):
        self.driver = driver
        self.root_path = root_path
        self.base_url = base_url
        self.options = options or {}


class CapturingStorageDriver(StorageDriver):
    """Storage driver stub to capture namespaced paths."""

    name = "storage-evidence"
    instances: list[CapturingStorageDriver] = []

    def __init__(self, config):
        super().__init__(config)
        self.accessed_paths: list[str] = []
        CapturingStorageDriver.instances.append(self)

    async def get_url(
        self,
        path: str,
        expires: int = 3600,
        visibility=None,
    ) -> str:
        _ = expires, visibility
        self.accessed_paths.append(path)
        return f"url://{path}"


@pytest.mark.asyncio
async def test_plugin_storage_driver_registers_and_namespaces(monkeypatch):
    plugin_name = "storage-evidence-plugin"
    driver_code = CapturingStorageDriver.name

    class DummyConfigService:
        def __init__(self, db):
            self.db = db

        async def get_value(self, key):
            if key == "storage_driver":
                return driver_code
            return None

    registry = ExtensionRegistry.get_instance()
    registry.unregister_all(plugin_name)
    CapturingStorageDriver.instances.clear()

    manifest = PluginManifest.model_validate(
        {
            "name": plugin_name,
            "version": "0.0.1",
            "display_name": {"en": "Storage Evidence"},
            "scope": "global_shared",
            "extensions": {
                "storage_drivers": [
                    {
                        "code": driver_code,
                        "display_name": {"en": "Storage Evidence Driver"},
                        "entry_point": "driver.PluginStorageDriver",
                    }
                ]
            },
        }
    )

    monkeypatch.setattr(
        registrar,
        "_load_handler",
        lambda *_args, **_kwargs: CapturingStorageDriver,
    )
    monkeypatch.setattr(
        "app.services.common.config_service.ConfigService",
        DummyConfigService,
    )
    monkeypatch.setattr(
        "app.plugins.context.StorageConfig",
        FakeStorageConfig,
        raising=False,
    )

    registered = registrar.register_all_extensions(
        registry,
        manifest,
        plugin_name,
    )

    assert registered == 1
    assert storage_manager.has_driver(driver_code)

    ctx = PluginContext(
        plugin_name=plugin_name,
        manifest=manifest,
        db=SimpleNamespace(),
        granted_capabilities=["storage:read"],
    )

    storage = await ctx.get_storage()
    assert storage is not None

    awaited_path = "files/report.txt"
    url = await storage.get_url(awaited_path)
    expected_path = f"plugins/{plugin_name}/{awaited_path}"
    assert url == f"url://{expected_path}"

    driver = CapturingStorageDriver.instances[-1]
    assert driver.accessed_paths == [expected_path]

    registry.unregister_all(plugin_name)
    assert not storage_manager.has_driver(driver_code)
