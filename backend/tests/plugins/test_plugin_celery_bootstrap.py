from __future__ import annotations

from types import SimpleNamespace

import app.plugins._extension_registrar as registrar
from app.celery_app import celery_app
from app.plugins.manifest import PluginManifest
from app.plugins.registry import ExtensionRegistry


def _build_consumer_manifest(
    plugin_name: str,
    consumer_name: str,
    *,
    queue: str = "consumer-bootstrap",
) -> PluginManifest:
    return PluginManifest.model_validate(
        {
            "name": plugin_name,
            "version": "0.1.0",
            "display_name": {"en": "Consumer Bootstrap Plugin"},
            "scope": "all_tenants",
            "extensions": {
                "consumers": [
                    {
                        "name": consumer_name,
                        "handler": "consumers.runtime.handle",
                        "queue": queue,
                        "max_retries": 4,
                        "retry_delay": 30,
                    }
                ]
            },
        }
    )


def test_registry_register_task_can_skip_schedule_injection() -> None:
    registry = ExtensionRegistry.get_instance()
    plugin_name = "unit-test-plugin"
    task_name = "sample_task"
    celery_task_name = f"plugin.{plugin_name}.{task_name}"
    beat_key = f"plugin_{plugin_name}_{task_name}"

    def _handler():
        return {"ok": True}

    celery_app.conf.beat_schedule = {}
    celery_app.tasks.pop(celery_task_name, None)

    registry.register_task(
        plugin_name,
        task_name,
        _handler,
        interval_seconds=30,
        register_schedule=False,
    )

    assert celery_task_name in celery_app.tasks
    assert beat_key not in (celery_app.conf.beat_schedule or {})


def test_celery_bootstrap_registers_enabled_plugin_queue_extensions_without_schedule(
    monkeypatch,
) -> None:
    from app import celery_app as celery_module

    captured: list[dict[str, object]] = []

    class _FakeResult:
        def all(self):
            return [("storage-billing",)]

    class _FakeSession:
        def execute(self, _stmt):
            return _FakeResult()

        def close(self):
            return None

    class _FakeLoader:
        def load_manifest(self, _plugin_name: str):
            return SimpleNamespace(
                extensions=SimpleNamespace(
                    tasks=[
                        SimpleNamespace(name="sample", handler="tasks.sample.handle")
                    ],
                    consumers=[],
                )
            )

    def _fake_sync_session_factory():
        return _FakeSession()

    def _fake_register_queue_extensions(
        registry,
        manifest,
        plugin_name: str,
        *,
        register_schedule: bool,
        record_failures: bool,
    ) -> None:
        captured.append(
            {
                "plugin_name": plugin_name,
                "registry": registry,
                "manifest": manifest,
                "register_schedule": register_schedule,
                "record_failures": record_failures,
            }
        )

    monkeypatch.setattr(
        "app.core.database.sync_session_factory",
        _fake_sync_session_factory,
    )
    monkeypatch.setattr(
        "app.plugins.loader.PluginLoader",
        _FakeLoader,
    )
    monkeypatch.setattr(
        "app.plugins._extension_registrar.register_queue_extensions",
        _fake_register_queue_extensions,
    )

    celery_module._bootstrap_enabled_plugin_queue_extensions()

    assert len(captured) == 1
    assert captured[0]["plugin_name"] == "storage-billing"
    assert captured[0]["register_schedule"] is False
    assert captured[0]["record_failures"] is False


def test_celery_bootstrap_restores_consumer_only_plugin(monkeypatch) -> None:
    from app import celery_app as celery_module

    plugin_name = "consumer-bootstrap-plugin"
    consumer_name = "sample-consumer"
    queue_name = "consumer-bootstrap"
    celery_task_name = f"plugin.{plugin_name}.{consumer_name}"
    manifest = _build_consumer_manifest(
        plugin_name,
        consumer_name,
        queue=queue_name,
    )
    handled: list[str] = []

    def _handler(payload: str) -> str:
        handled.append(payload)
        return f"handled:{payload}"

    class _FakeResult:
        def all(self):
            return [(plugin_name,)]

    class _FakeSession:
        def execute(self, _stmt):
            return _FakeResult()

        def close(self):
            return None

    class _FakeLoader:
        def load_manifest(self, requested_plugin_name: str):
            assert requested_plugin_name == plugin_name
            return manifest

    def _fake_sync_session_factory():
        return _FakeSession()

    monkeypatch.setattr(
        "app.core.database.sync_session_factory",
        _fake_sync_session_factory,
    )
    monkeypatch.setattr(
        "app.plugins.loader.PluginLoader",
        _FakeLoader,
    )
    monkeypatch.setattr(
        registrar,
        "_load_handler",
        lambda *_args, **_kwargs: _handler,
    )

    ExtensionRegistry.reset()
    registrar._failed_extensions.clear()
    celery_app.tasks.pop(celery_task_name, None)

    try:
        celery_module._bootstrap_enabled_plugin_queue_extensions()

        assert celery_task_name in celery_app.tasks
        task = celery_app.tasks[celery_task_name]
        assert task.name == celery_task_name
        assert task.queue == queue_name
        assert task.max_retries == 4
        assert task.default_retry_delay == 30
        assert task.run("ping") == "handled:ping"
        assert handled == ["ping"]
    finally:
        celery_app.tasks.pop(celery_task_name, None)
        ExtensionRegistry.reset()
        registrar._failed_extensions.clear()
