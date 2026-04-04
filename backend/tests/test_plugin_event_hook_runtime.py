"""Regression guard covering hook and PluginEventBus runtime registration."""

from __future__ import annotations

import pytest

import app.plugins._extension_registrar as registrar
from app.ai.events.hooks import HookPoint, HookRegistry
from app.plugins.event_bus import PluginEventBus
from app.plugins.manifest import PluginManifest
from app.plugins.registry import ExtensionRegistry


@pytest.fixture(autouse=True)
def _reset_plugin_runtime_singletons():
    """Keep the registries clean between tests."""
    ExtensionRegistry.reset()
    HookRegistry.reset()
    PluginEventBus.reset()
    registrar._failed_extensions.clear()
    yield
    ExtensionRegistry.reset()
    HookRegistry.reset()
    PluginEventBus.reset()
    registrar._failed_extensions.clear()


def _build_event_hook_manifest() -> PluginManifest:
    return PluginManifest.model_validate(
        {
            "name": "demo-plugin",
            "version": "1.0.0",
            "display_name": {"en": "Demo Plugin"},
            "scope": "admin_only",
            "extensions": {
                "hooks": [
                    {
                        "point": HookPoint.BEFORE_EXECUTE,
                        "handler": "hooks.demo_before_execute",
                        "priority": 25,
                    }
                ],
                "events": [
                    {
                        "event": "plugin.demo-plugin.action_performed",
                        "handler": "events.on_action",
                    }
                ],
            },
        }
    )


@pytest.mark.asyncio
async def test_register_all_extensions_wire_hook_and_event_bus(monkeypatch):
    """manifest -> registrar -> HookRegistry + PluginEventBus bridge stays intact."""
    manifest = _build_event_hook_manifest()
    registry = ExtensionRegistry.get_instance()

    event_calls: list[tuple[str, int | None]] = []

    async def hook_handler(**_kwargs):
        return {"hook_result": "invoked"}

    async def event_handler(event_name: str, payload: dict[str, int | None]):
        event_calls.append((event_name, payload.get("value")))

    handler_map = {
        "hooks.demo_before_execute": hook_handler,
        "events.on_action": event_handler,
    }

    monkeypatch.setattr(
        registrar,
        "_load_handler",
        lambda _plugin_name, handler_path: handler_map.get(handler_path),
    )
    registrar._failed_extensions.pop("demo-plugin", None)

    count = registrar.register_all_extensions(registry, manifest, "demo-plugin")
    assert count == 2
    assert registry.get_registered_count("demo-plugin") == 2

    hooks = HookRegistry.get_instance()
    assert hooks.has_hooks(HookPoint.BEFORE_EXECUTE)
    context = await hooks.trigger(HookPoint.BEFORE_EXECUTE, tenant_id=1)
    assert context.get("hook_result") == "invoked"

    event_name = manifest.extensions.events[0].event
    bus = PluginEventBus.get_instance()
    assert bus.has_subscribers(event_name)
    result = await bus.publish(event_name, {"value": 123}, source_plugin="demo-plugin")
    assert result["delivered"] == 1
    assert event_calls == [(event_name, 123)]
    assert registrar.get_failed_extensions("demo-plugin") == []
