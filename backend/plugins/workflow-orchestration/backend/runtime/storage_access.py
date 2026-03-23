from __future__ import annotations

from typing import Any

from app.services.common.storage_config_resolver import StorageConfigResolver
from app.storage.manager import storage_manager

PLUGIN_NAME = "workflow-orchestration"


class NamespacedStorageProxy:
    def __init__(self, driver: Any, namespace: str) -> None:
        self._driver = driver
        self._namespace = namespace.strip("/")

    def _full_path(self, path: str) -> str:
        cleaned = str(path or "").strip().lstrip("/")
        if cleaned.startswith("plugins/"):
            return cleaned
        return f"{self._namespace}/{cleaned}" if cleaned else self._namespace

    async def get(self, path: str) -> Any:
        return await self._driver.get(self._full_path(path))

    async def put(self, path: str, content: Any, mime_type: str | None = None, **kwargs: Any) -> Any:
        return await self._driver.put(self._full_path(path), content, mime_type=mime_type, **kwargs)

    async def delete(self, path: str) -> Any:
        return await self._driver.delete(self._full_path(path))

    async def exists(self, path: str) -> Any:
        return await self._driver.exists(self._full_path(path))


async def get_plugin_storage(db: Any, tenant_id: int | None = None) -> NamespacedStorageProxy:
    resolver = StorageConfigResolver(db)
    if tenant_id is not None:
        _, storage_config, _ = await resolver.resolve_context(tenant_id)
    else:
        storage_config = await resolver.resolve_platform_config()
    driver = storage_manager.get_driver(storage_config)
    return NamespacedStorageProxy(driver, f"plugins/{PLUGIN_NAME}")
