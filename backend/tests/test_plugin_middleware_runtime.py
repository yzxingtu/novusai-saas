"""Middleware runtime registration lifecycle tests."""

import pytest
from fastapi import FastAPI

from app.plugins import _extension_registrar as registrar
from app.plugins.manifest import PluginManifest
from app.plugins.registry import ExtensionRegistry

PLUGIN_NAME = "middleware-runtime-plugin"


class HostAuditMiddleware:
    """Host middleware fixture. / 宿主中间件夹具。"""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        await self.app(scope, receive, send)


class PluginTraceMiddleware:
    """Plugin middleware fixture. / 插件中间件夹具。"""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        await self.app(scope, receive, send)


@pytest.fixture(autouse=True)
def _reset_registry_state():
    """Reset singleton registries between tests."""
    ExtensionRegistry.reset()
    registrar._failed_extensions.clear()
    yield
    ExtensionRegistry.reset()
    registrar._failed_extensions.clear()


def _build_middleware_manifest() -> PluginManifest:
    return PluginManifest.model_validate(
        {
            "name": PLUGIN_NAME,
            "version": "0.0.1",
            "display_name": {"en": "Middleware Runtime Plugin"},
            "scope": "admin_only",
            "extensions": {
                "middleware": [
                    {
                        "handler": "middleware.trace.PluginTraceMiddleware",
                        "name": "plugin-trace",
                        "priority": 10,
                    }
                ]
            },
        }
    )


def _build_started_fastapi_app() -> FastAPI:
    """Build a started app so add_middleware() is no longer allowed. / 构造已启动状态应用。"""
    app = FastAPI()
    app.add_middleware(HostAuditMiddleware)
    app.middleware_stack = app.build_middleware_stack()
    return app


def test_middleware_registration_rebuilds_started_runtime_stack_and_unregisters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    started_app = _build_started_fastapi_app()
    original_stack = started_app.middleware_stack

    import app.main as app_main  # noqa: WPS300

    monkeypatch.setattr(app_main, "app", started_app)

    registry = ExtensionRegistry.get_instance()
    manifest = _build_middleware_manifest()
    monkeypatch.setattr(
        registrar,
        "_load_handler",
        lambda *_, **__: PluginTraceMiddleware,
    )

    registration_count = registrar.register_all_extensions(
        registry,
        manifest,
        PLUGIN_NAME,
    )

    assert registration_count == 1
    assert [middleware.cls for middleware in started_app.user_middleware] == [
        PluginTraceMiddleware,
        HostAuditMiddleware,
    ]
    assert started_app.middleware_stack is not None
    assert started_app.middleware_stack is not original_stack

    middlewares = registry.get_plugin_middlewares(PLUGIN_NAME)
    assert len(middlewares) == 1
    middleware_entry = middlewares[0]
    assert middleware_entry["name"] == "plugin-trace"
    assert middleware_entry["cls"] is PluginTraceMiddleware
    assert middleware_entry["runtime_middleware"].cls is PluginTraceMiddleware
    assert registrar.get_failed_extensions(PLUGIN_NAME) == []

    registered_stack = started_app.middleware_stack
    registry.unregister_all(PLUGIN_NAME)

    assert registry.get_plugin_middlewares(PLUGIN_NAME) == []
    assert registry.get_registered_count(PLUGIN_NAME) == 0
    assert [middleware.cls for middleware in started_app.user_middleware] == [
        HostAuditMiddleware
    ]
    assert started_app.middleware_stack is not None
    assert started_app.middleware_stack is not registered_stack
