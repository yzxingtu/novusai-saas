from __future__ import annotations

import pytest

import app.plugins._extension_registrar as registrar
from app.celery_app import celery_app
from app.plugins.manifest import PluginManifest
from app.plugins.registry import ExtensionRegistry


def _build_consumer_manifest(
    plugin_name: str,
    consumer_name: str,
    *,
    queue: str = "sample-consumer-queue",
    max_retries: int = 2,
    retry_delay: int = 5,
) -> PluginManifest:
    """Minimal manifest that declares a single consumer extension."""
    return PluginManifest.model_validate(
        {
            "name": plugin_name,
            "version": "0.1.0",
            "display_name": {"en": "Consumer Sample Plugin"},
            "scope": "all_tenants",
            "extensions": {
                "consumers": [
                    {
                        "name": consumer_name,
                        "handler": "consumers.runtime.handle",
                        "queue": queue,
                        "max_retries": max_retries,
                        "retry_delay": retry_delay,
                    }
                ]
            },
        }
    )


@pytest.fixture(autouse=True)
def _reset_registry_state():
    """Ensure registries are clean around each sample contract test."""
    ExtensionRegistry.reset()
    registrar._failed_extensions.clear()
    yield
    ExtensionRegistry.reset()
    registrar._failed_extensions.clear()


def test_plugin_consumer_sample_contract(monkeypatch) -> None:
    """Manifest -> registrar -> Celery consumer contract."""
    plugin_name = "sample-consumer-plugin"
    consumer_name = "sample-message-handler"
    queue_name = "sample-queue"
    celery_task_name = f"plugin.{plugin_name}.{consumer_name}"
    manifest = _build_consumer_manifest(
        plugin_name,
        consumer_name,
        queue=queue_name,
    )

    handled: list[str] = []

    def handler(payload: str) -> str:
        handled.append(payload)
        return f"handled:{payload}"

    monkeypatch.setattr(registrar, "_load_handler", lambda *_: handler)

    registry = ExtensionRegistry.get_instance()
    celery_app.tasks.pop(celery_task_name, None)

    try:
        registrar.register_all_extensions(registry, manifest, plugin_name)

        assert celery_task_name in celery_app.tasks
        task = celery_app.tasks[celery_task_name]
        assert task.name == celery_task_name
        assert task.queue == queue_name

        result = task.run("hello")
        assert result == "handled:hello"
        assert handled == ["hello"]

        assert registry._plugin_consumers[plugin_name][0]["name"] == consumer_name
        assert registry._plugin_consumers[plugin_name][0]["queue"] == queue_name

        removed = registry.unregister_all(plugin_name)
        assert removed == 1
        assert registry.get_registered_count(plugin_name) == 0
        assert registry._plugin_consumers.get(plugin_name) in (None, [])
        assert celery_task_name in celery_app.tasks
    finally:
        celery_app.tasks.pop(celery_task_name, None)
