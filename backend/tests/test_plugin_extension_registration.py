"""Test type: behavioral
Scope: plugin extension registrar and runtime registry contracts.
Real dependencies: PluginManifest validation and ExtensionRegistry state.
Mocked dependencies: handler loading only.
"""

from __future__ import annotations

from unittest.mock import Mock

import app.plugins._extension_registrar as registrar
from app.plugins.manifest import PluginManifest


def _build_runtime_bridge_manifest() -> PluginManifest:
    return PluginManifest.model_validate(
        {
            "name": "demo-plugin",
            "version": "1.0.0",
            "display_name": {"en": "Demo Plugin"},
            "scope": "admin_only",
            "extensions": {
                "consumers": [
                    {
                        "name": "sync-jobs",
                        "handler": "consumers.sync.consume",
                        "max_retries": 5,
                        "queue": "plugin-sync",
                        "retry_delay": 15,
                    }
                ],
                "middleware": [
                    {
                        "handler": "middleware.trace.PluginTraceMiddleware",
                        "name": "plugin-trace",
                        "priority": 10,
                    }
                ],
                "socketio": [
                    {
                        "auth_required": False,
                        "auth_scopes": ["tenant_admin", "admin"],
                        "handler": "sio.collab_namespace.CollabNamespace",
                        "path": "collab",
                    }
                ],
            },
        }
    )


class _FakeRegistry:
    def __init__(self, registered_count: int) -> None:
        self._registered_count = registered_count
        self.register_consumer = Mock()
        self.register_middleware = Mock()
        self.register_socketio = Mock()
        self.unregister_all = Mock()

    def get_registered_count(self, _plugin_name: str) -> int:
        return self._registered_count


def test_register_all_extensions_bridges_runtime_extensions(monkeypatch) -> None:
    manifest = _build_runtime_bridge_manifest()
    registry = _FakeRegistry(registered_count=3)

    consumer_handler = object()
    middleware_cls = type("PluginTraceMiddleware", (), {})
    socketio_cls = type("CollabNamespace", (), {})
    handler_map = {
        "consumers.sync.consume": consumer_handler,
        "middleware.trace.PluginTraceMiddleware": middleware_cls,
        "sio.collab_namespace.CollabNamespace": socketio_cls,
    }

    monkeypatch.setattr(
        registrar,
        "_load_handler",
        lambda _plugin_name, handler_path: handler_map.get(handler_path),
    )
    registrar._failed_extensions.pop("demo-plugin", None)

    count = registrar.register_all_extensions(registry, manifest, "demo-plugin")

    registry.unregister_all.assert_called_once_with("demo-plugin")
    registry.register_consumer.assert_called_once_with(
        "demo-plugin",
        "sync-jobs",
        consumer_handler,
        max_retries=5,
        queue="plugin-sync",
        retry_delay=15,
    )
    registry.register_socketio.assert_called_once_with(
        "demo-plugin",
        "collab",
        socketio_cls,
        False,
        ["tenant_admin", "admin"],
    )
    registry.register_middleware.assert_called_once_with(
        "demo-plugin",
        "plugin-trace",
        middleware_cls,
        priority=10,
    )
    assert count == 3
    assert registrar.get_failed_extensions("demo-plugin") == []


def test_register_all_extensions_records_runtime_extension_failures(
    monkeypatch,
) -> None:
    manifest = _build_runtime_bridge_manifest()
    registry = _FakeRegistry(registered_count=0)

    monkeypatch.setattr(registrar, "_load_handler", lambda *_args, **_kwargs: None)
    registrar._failed_extensions.pop("demo-plugin", None)

    count = registrar.register_all_extensions(registry, manifest, "demo-plugin")

    assert count == 0
    assert registrar.get_failed_extensions("demo-plugin") == [
        {"entry_point": "consumers.sync.consume", "type": "consumer"},
        {
            "entry_point": "sio.collab_namespace.CollabNamespace",
            "type": "socketio",
        },
        {
            "entry_point": "middleware.trace.PluginTraceMiddleware",
            "type": "middleware",
        },
    ]


def test_registry_keeps_plugin_skill_resolvers_by_skill_name() -> None:
    from app.plugins.registry import ExtensionRegistry

    ExtensionRegistry.reset()
    registry = ExtensionRegistry.get_instance()

    def alpha_resolver(*_args, **_kwargs):
        return ["alpha"]

    def beta_resolver(*_args, **_kwargs):
        return ["beta"]

    registry.register_skill(
        "demo-plugin",
        "toolkit",
        alpha_resolver,
        skill_name="alpha-skill",
    )
    registry.register_skill(
        "demo-plugin",
        "toolkit",
        beta_resolver,
        skill_name="beta-skill",
    )

    assert registry.get_plugin_skill_resolver("demo-plugin", "alpha-skill") is (
        alpha_resolver
    )
    assert registry.get_plugin_skill_resolver("demo-plugin", "beta-skill") is (
        beta_resolver
    )
    assert registry.get_plugin_skill_resolver("demo-plugin", "missing-skill") is None
    assert registry.get_plugin_skill_resolver("demo-plugin") is alpha_resolver

    registry.unregister_all("demo-plugin")

    assert registry.get_plugin_skill_resolver("demo-plugin", "alpha-skill") is None
    assert registry.get_plugin_skill_resolver("demo-plugin", "beta-skill") is None
    assert registry.get_plugin_skill_resolver("demo-plugin") is None


def test_registry_unregister_by_type_clears_plugin_skill_facade() -> None:
    from app.plugins.registry import ExtensionRegistry

    ExtensionRegistry.reset()
    registry = ExtensionRegistry.get_instance()

    def alpha_resolver(*_args, **_kwargs):
        return ["alpha"]

    def beta_resolver(*_args, **_kwargs):
        return ["beta"]

    registry.register_skill(
        "demo-plugin",
        "toolkit",
        alpha_resolver,
        skill_name="alpha-skill",
    )
    registry.register_skill(
        "demo-plugin",
        "toolkit",
        beta_resolver,
        skill_name="beta-skill",
    )

    assert registry.unregister_by_type("demo-plugin", "skill") == 2
    assert registry.get_plugin_skill_resolver("demo-plugin", "alpha-skill") is None
    assert registry.get_plugin_skill_resolver("demo-plugin", "beta-skill") is None
    assert registry.get_plugin_skill_resolver("demo-plugin") is None
