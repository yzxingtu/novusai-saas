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
    queue: str = "consumer-runtime",
    max_retries: int = 6,
    retry_delay: int = 15,
) -> PluginManifest:
    return PluginManifest.model_validate(
        {
            "name": plugin_name,
            "version": "0.1.0",
            "display_name": {"en": "Consumer Runtime Plugin"},
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
def reset_registry_state() -> None:
    ExtensionRegistry.reset()
    registrar._failed_extensions.clear()
    yield
    ExtensionRegistry.reset()
    registrar._failed_extensions.clear()


def test_register_all_extensions_registers_celery_consumer(monkeypatch) -> None:
    plugin_name = "runtime-consumer-plugin"
    consumer_name = "message-handler"
    celery_task_name = f"plugin.{plugin_name}.{consumer_name}"
    manifest = _build_consumer_manifest(plugin_name, consumer_name)
    consumer_ext = manifest.extensions.consumers[0]

    def handler(*_args: object, **_kwargs: object) -> str:
        return "ok"

    monkeypatch.setattr(
        registrar,
        "_load_handler",
        lambda *_args, **_kwargs: handler,
    )

    registry = ExtensionRegistry.get_instance()
    celery_app.tasks.pop(celery_task_name, None)

    try:
        registered_count = registrar.register_all_extensions(
            registry,
            manifest,
            plugin_name,
        )

        assert registered_count == 1
        assert celery_task_name in celery_app.tasks

        task = celery_app.tasks[celery_task_name]
        assert task.name == celery_task_name
        assert task.queue == consumer_ext.queue
        assert task.max_retries == consumer_ext.max_retries
        assert task.default_retry_delay == consumer_ext.retry_delay

        assert registry._plugin_consumers[plugin_name][0]["name"] == consumer_name
        assert registry._plugin_consumers[plugin_name][0]["queue"] == consumer_ext.queue
        assert registrar.get_failed_extensions(plugin_name) == []
    finally:
        celery_app.tasks.pop(celery_task_name, None)


def test_unregister_all_consumer_cleans_tracking_but_keeps_celery_task(
    monkeypatch,
) -> None:
    plugin_name = "runtime-consumer-plugin"
    consumer_name = "message-handler"
    celery_task_name = f"plugin.{plugin_name}.{consumer_name}"
    manifest = _build_consumer_manifest(plugin_name, consumer_name)

    def handler(*_args: object, **_kwargs: object) -> str:
        return "ok"

    monkeypatch.setattr(
        registrar,
        "_load_handler",
        lambda *_args, **_kwargs: handler,
    )

    registry = ExtensionRegistry.get_instance()
    celery_app.tasks.pop(celery_task_name, None)

    try:
        registrar.register_all_extensions(
            registry,
            manifest,
            plugin_name,
        )

        removed_count = registry.unregister_all(plugin_name)

        assert removed_count == 1
        assert registry.get_registered_count(plugin_name) == 0
        assert registry._plugin_consumers.get(plugin_name) in (None, [])
        assert celery_task_name in celery_app.tasks
    finally:
        celery_app.tasks.pop(celery_task_name, None)
