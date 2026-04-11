from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import ANY, AsyncMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.admin.plugins import AdminPluginController
from app.core.deps import get_current_active_admin, get_db


def _build_test_app(mock_db) -> FastAPI:
    app = FastAPI()

    @app.middleware("http")
    async def inject_permissions(request, call_next):
        request.state.user_permissions = {"*"}
        return await call_next(request)

    app.include_router(AdminPluginController.get_router())

    async def override_db():
        yield mock_db

    async def override_admin():
        return SimpleNamespace(id=1, is_active=True, is_super=True)

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_active_admin] = override_admin
    return app


def _reset_controller(monkeypatch) -> None:
    monkeypatch.setattr(AdminPluginController, "_instance", None)
    monkeypatch.setattr(AdminPluginController, "_router", None)


def test_update_capabilities_route_delegates_to_service(monkeypatch) -> None:
    _reset_controller(monkeypatch)

    service = SimpleNamespace(update_capabilities=AsyncMock())
    monkeypatch.setattr(
        AdminPluginController,
        "get_service",
        lambda *_args, **_kwargs: service,
    )

    app = _build_test_app(SimpleNamespace())

    with TestClient(app) as client:
        response = client.put(
            "/plugins/7/capabilities",
            json={"capabilities": ["demo.search"]},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 0
    service.update_capabilities.assert_awaited_once_with(7, ["demo.search"])


def test_upgrade_route_delegates_to_plugin_service(monkeypatch) -> None:
    _reset_controller(monkeypatch)

    service = SimpleNamespace(upgrade_plugin=AsyncMock())
    monkeypatch.setattr(
        AdminPluginController,
        "get_service",
        lambda *_args, **_kwargs: service,
    )

    app = _build_test_app(SimpleNamespace())

    with TestClient(app) as client:
        response = client.post(
            "/plugins/7/upgrade",
            files={"file": ("plugin.zip", b"demo", "application/zip")},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 0
    service.upgrade_plugin.assert_awaited_once_with(7, ANY)
    assert service.upgrade_plugin.await_args.args[1].filename == "plugin.zip"


def test_rollback_route_delegates_to_plugin_service(monkeypatch) -> None:
    _reset_controller(monkeypatch)

    service = SimpleNamespace(rollback_plugin=AsyncMock())
    monkeypatch.setattr(
        AdminPluginController,
        "get_service",
        lambda *_args, **_kwargs: service,
    )

    app = _build_test_app(SimpleNamespace())

    with TestClient(app) as client:
        response = client.post(
            "/plugins/7/rollback",
            json={"target_version": "1.2.3"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 0
    service.rollback_plugin.assert_awaited_once_with(7, "1.2.3")
