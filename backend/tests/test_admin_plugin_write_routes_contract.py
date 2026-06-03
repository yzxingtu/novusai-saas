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


def _patch_workflow(monkeypatch, **methods):
    workflow = SimpleNamespace(**methods)
    monkeypatch.setattr(
        AdminPluginController,
        "get_workflow_service",
        lambda *_args, **_kwargs: workflow,
    )
    return workflow


def test_enable_route_delegates_to_workflow(monkeypatch) -> None:
    _reset_controller(monkeypatch)

    workflow = _patch_workflow(monkeypatch, enable_plugin=AsyncMock())
    app = _build_test_app(SimpleNamespace())

    with TestClient(app) as client:
        response = client.post(
            "/plugins/7/enable",
            json={
                "menu_overrides": [
                    {"name": "demo_plugin", "parent": "system_maintenance"}
                ]
            },
        )

    assert response.status_code == 200
    workflow.enable_plugin.assert_awaited_once()
    kwargs = workflow.enable_plugin.await_args.kwargs
    assert kwargs["plugin_id"] == 7
    assert kwargs["admin_id"] == 1
    assert len(kwargs["menu_overrides"]) == 1
    assert kwargs["menu_overrides"][0].name == "demo_plugin"


def test_menu_config_route_delegates_to_workflow(monkeypatch) -> None:
    _reset_controller(monkeypatch)

    workflow = _patch_workflow(monkeypatch, update_menu_config=AsyncMock())
    app = _build_test_app(SimpleNamespace())

    with TestClient(app) as client:
        response = client.put(
            "/plugins/7/menu-config",
            json={
                "menu_overrides": [
                    {
                        "name": "demo_plugin",
                        "parent": "system_maintenance",
                        "tenant_parent": "workspace",
                    }
                ]
            },
        )

    assert response.status_code == 200
    workflow.update_menu_config.assert_awaited_once()
    kwargs = workflow.update_menu_config.await_args.kwargs
    assert kwargs["plugin_id"] == 7
    assert kwargs["menu_overrides"][0].tenant_parent == "workspace"


def test_upload_icon_route_delegates_to_workflow(monkeypatch) -> None:
    _reset_controller(monkeypatch)

    workflow = _patch_workflow(
        monkeypatch,
        upload_icon=AsyncMock(return_value="icon.png"),
    )
    app = _build_test_app(SimpleNamespace())

    with TestClient(app) as client:
        response = client.post(
            "/plugins/7/icon",
            files={"file": ("icon.png", b"demo", "image/png")},
        )

    assert response.status_code == 200
    workflow.upload_icon.assert_awaited_once()
    kwargs = workflow.upload_icon.await_args.kwargs
    assert kwargs["plugin_id"] == 7
    assert kwargs["file"].filename == "icon.png"


def test_activate_license_route_delegates_to_workflow(monkeypatch) -> None:
    _reset_controller(monkeypatch)

    workflow = _patch_workflow(
        monkeypatch,
        activate_license=AsyncMock(return_value={"success": True}),
    )
    app = _build_test_app(SimpleNamespace())

    with TestClient(app) as client:
        response = client.post(
            "/plugins/7/activate-license",
            json={"license_key": "demo-key"},
        )

    assert response.status_code == 200
    workflow.activate_license.assert_awaited_once_with(
        plugin_id=7,
        license_key="demo-key",
    )


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


def test_uninstall_route_delegates_to_workflow(monkeypatch) -> None:
    _reset_controller(monkeypatch)

    workflow = _patch_workflow(
        monkeypatch,
        uninstall_plugin=AsyncMock(return_value=None),
    )
    app = _build_test_app(SimpleNamespace())

    with TestClient(app) as client:
        response = client.delete(
            "/plugins/7",
            params={"confirm_data_delete": "true", "cleanup_dependencies": "true"},
        )

    assert response.status_code == 200
    workflow.uninstall_plugin.assert_awaited_once_with(
        plugin_id=7,
        admin_id=1,
        confirm_data_delete=True,
        cleanup_dependencies=True,
    )
