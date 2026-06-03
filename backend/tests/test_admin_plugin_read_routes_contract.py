from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.admin.plugins import AdminPluginController
from app.core.deps import get_current_active_admin, get_db
from app.repositories.system.plugin_repository import PluginRepository
from tests.services.conftest import make_scalar_result, make_scalars_result


def _make_plugin(**overrides):
    defaults = {
        "id": 7,
        "name": "demo-plugin",
        "display_name": "Demo Plugin",
        "manifest": {},
        "config": {},
        "status": "enabled",
        "scope": "admin",
    }
    defaults.update(overrides)
    plugin = MagicMock()
    for key, value in defaults.items():
        setattr(plugin, key, value)
    plugin.to_dict.return_value = defaults.copy()
    return plugin


def _make_plugin_service(mock_db):
    from app.services.system.plugin_service import PluginService

    service = PluginService.__new__(PluginService)
    service.db = mock_db
    service.repo = PluginRepository(mock_db)
    return service


def _build_test_app(mock_db) -> FastAPI:
    app = FastAPI()
    app.include_router(AdminPluginController.get_router())

    async def override_db():
        yield mock_db

    async def override_admin():
        return SimpleNamespace(id=1, is_active=True)

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_active_admin] = override_admin
    return app


def _return_plugin_service(service):
    return lambda _self: service


def test_list_plugins_route_keeps_plugin_read_model_facade_chain(monkeypatch) -> None:
    from app.services.system.plugin_read_model_service import PluginReadModelService

    monkeypatch.setattr(AdminPluginController, "_instance", None)
    monkeypatch.setattr(AdminPluginController, "_router", None)

    plugin = _make_plugin()
    mock_db = AsyncMock()
    mock_db.execute.side_effect = [
        make_scalar_result(1),
        make_scalars_result([plugin]),
    ]

    service = _make_plugin_service(mock_db)
    service.get_dependency_status = AsyncMock(return_value={"overall": "installed"})
    service.get_recovery_state = MagicMock(return_value={"state": "healthy"})

    monkeypatch.setattr(
        PluginReadModelService,
        "_get_plugin_service",
        _return_plugin_service(service),
    )

    app = _build_test_app(mock_db)

    with TestClient(app) as client:
        response = client.get("/plugins?page[number]=1&page[size]=20")

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 0
    assert payload["data"]["total"] == 1
    assert payload["data"]["items"][0]["name"] == "demo-plugin"
    assert payload["data"]["items"][0]["dependency_status"] == {"overall": "installed"}
    assert payload["data"]["items"][0]["recovery_state"] == {"state": "healthy"}
    service.get_dependency_status.assert_awaited_once_with(plugin)
    service.get_recovery_state.assert_called_once_with(
        plugin,
        dependency_status={"overall": "installed"},
    )


def test_get_plugin_route_keeps_plugin_read_model_facade_chain(monkeypatch) -> None:
    from app.services.system.plugin_read_model_service import PluginReadModelService

    monkeypatch.setattr(AdminPluginController, "_instance", None)
    monkeypatch.setattr(AdminPluginController, "_router", None)

    plugin = _make_plugin()
    mock_db = AsyncMock()
    mock_db.execute.return_value = make_scalar_result(plugin)

    service = _make_plugin_service(mock_db)
    service.get_dependency_status = AsyncMock(return_value={"overall": "installed"})
    service.get_recovery_state = MagicMock(return_value={"state": "healthy"})
    service.get_readme = AsyncMock(return_value="# Demo")

    monkeypatch.setattr(
        PluginReadModelService,
        "_get_plugin_service",
        _return_plugin_service(service),
    )

    app = _build_test_app(mock_db)

    with TestClient(app) as client:
        response = client.get("/plugins/7?locale=zh-CN")

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 0
    assert payload["data"]["id"] == 7
    assert payload["data"]["name"] == "demo-plugin"
    assert payload["data"]["dependency_status"] == {"overall": "installed"}
    assert payload["data"]["recovery_state"] == {"state": "healthy"}
    assert payload["data"]["readme"] == "# Demo"
    service.get_dependency_status.assert_awaited_once_with(plugin)
    service.get_recovery_state.assert_called_once_with(
        plugin,
        dependency_status={"overall": "installed"},
    )
    service.get_readme.assert_awaited_once_with(7, locale="zh-CN")
