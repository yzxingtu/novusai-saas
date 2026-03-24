from __future__ import annotations

from types import SimpleNamespace

from app.celery_app import celery_app
from app.plugins.registry import ExtensionRegistry


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
        def load_manifest(self, plugin_name: str):
            return SimpleNamespace(
                extensions=SimpleNamespace(
                    tasks=[SimpleNamespace(name="sample", handler="tasks.sample.handle")],
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
