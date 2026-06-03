from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.deps import get_current_active_tenant_admin, get_db


def _load_tenant_configs_module():
    module_path = (
        Path(__file__).resolve().parent.parent / "app" / "api" / "tenant" / "configs.py"
    )
    spec = importlib.util.spec_from_file_location(
        "test_tenant_configs_module",
        module_path,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec is not None
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _build_test_app(mock_db, tenant_configs_module) -> FastAPI:
    app = FastAPI()

    @app.middleware("http")
    async def inject_permissions(request, call_next):
        request.state.user_permissions = {
            "tenant_config:groups",
            "tenant_config:detail",
            "tenant_config:update",
        }
        return await call_next(request)

    app.include_router(tenant_configs_module.TenantConfigController.get_router())

    async def override_db():
        yield mock_db

    async def override_admin():
        return SimpleNamespace(id=9, tenant_id=77, is_active=True)

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_active_tenant_admin] = override_admin
    return app


def test_group_detail_route_delegates_to_workflow_service(monkeypatch) -> None:
    tenant_configs_module = _load_tenant_configs_module()
    monkeypatch.setattr(tenant_configs_module.TenantConfigController, "_instance", None)
    monkeypatch.setattr(tenant_configs_module.TenantConfigController, "_router", None)
    monkeypatch.setattr(
        tenant_configs_module.config_registry,
        "get_group",
        lambda _group_code: SimpleNamespace(
            code="security",
            scope=tenant_configs_module.ConfigScope.ALL_TENANTS,
        ),
    )

    service = SimpleNamespace(
        get_group_response=AsyncMock(
            return_value={"code": "security", "configs": [], "name": "Security"}
        )
    )
    monkeypatch.setattr(
        tenant_configs_module,
        "TenantConfigWorkflowService",
        lambda _db: service,
    )

    app = _build_test_app(SimpleNamespace(), tenant_configs_module)
    with TestClient(app) as client:
        response = client.get("/configs/groups/security")

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 0
    assert payload["data"]["code"] == "security"
    service.get_group_response.assert_awaited_once_with(
        tenant_id=77,
        group_code="security",
    )


def test_update_group_route_delegates_to_workflow_service(monkeypatch) -> None:
    tenant_configs_module = _load_tenant_configs_module()
    monkeypatch.setattr(tenant_configs_module.TenantConfigController, "_instance", None)
    monkeypatch.setattr(tenant_configs_module.TenantConfigController, "_router", None)

    service = SimpleNamespace(
        update_group_configs=AsyncMock(
            return_value={"code": "security", "configs": [{"key": "captcha_provider"}]}
        )
    )
    monkeypatch.setattr(
        tenant_configs_module,
        "TenantConfigWorkflowService",
        lambda _db: service,
    )

    app = _build_test_app(SimpleNamespace(), tenant_configs_module)
    with TestClient(app) as client:
        response = client.put(
            "/configs/groups/security",
            json={"configs": {"captcha_provider": "image"}},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 0
    service.update_group_configs.assert_awaited_once_with(
        configs={"captcha_provider": "image"},
        group_code="security",
        tenant_id=77,
    )


def test_storage_status_route_delegates_to_workflow_service(monkeypatch) -> None:
    tenant_configs_module = _load_tenant_configs_module()
    monkeypatch.setattr(tenant_configs_module.TenantConfigController, "_instance", None)
    monkeypatch.setattr(tenant_configs_module.TenantConfigController, "_router", None)

    service = SimpleNamespace(
        get_storage_status=AsyncMock(
            return_value={
                "effective_mode": "custom",
                "effective_driver": "s3",
                "can_self_config": True,
            }
        )
    )
    monkeypatch.setattr(
        tenant_configs_module,
        "TenantConfigWorkflowService",
        lambda _db: service,
    )

    app = _build_test_app(SimpleNamespace(), tenant_configs_module)
    with TestClient(app) as client:
        response = client.get("/configs/storage/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 0
    assert payload["data"]["effective_driver"] == "s3"
    service.get_storage_status.assert_awaited_once_with(77)


def test_storage_routes_delegate_to_workflow_service(monkeypatch) -> None:
    tenant_configs_module = _load_tenant_configs_module()
    monkeypatch.setattr(tenant_configs_module.TenantConfigController, "_instance", None)
    monkeypatch.setattr(tenant_configs_module.TenantConfigController, "_router", None)

    service = SimpleNamespace(
        list_storage_drivers=AsyncMock(return_value=[{"name": "s3"}]),
        save_storage_config=AsyncMock(return_value=None),
        test_storage_connection=AsyncMock(return_value={"success": True}),
    )
    monkeypatch.setattr(
        tenant_configs_module,
        "TenantConfigWorkflowService",
        lambda _db: service,
    )

    app = _build_test_app(SimpleNamespace(), tenant_configs_module)
    with TestClient(app) as client:
        save_response = client.put(
            "/configs/storage",
            json={
                "tenant_storage_driver": "s3",
                "tenant_storage_root_path": "bucket",
            },
        )
        test_response = client.post(
            "/configs/storage/test-connection",
            json={
                "driver": "s3",
                "root_path": "bucket",
                "base_url": "",
                "config": {"region": "ap-southeast-1"},
            },
        )
        drivers_response = client.get("/configs/storage/drivers")

    assert save_response.status_code == 200
    assert test_response.status_code == 200
    assert drivers_response.status_code == 200
    service.save_storage_config.assert_awaited_once_with(
        data={
            "tenant_storage_driver": "s3",
            "tenant_storage_root_path": "bucket",
        },
        tenant_id=77,
    )
    service.test_storage_connection.assert_awaited_once_with(
        base_url="",
        config={"region": "ap-southeast-1"},
        driver="s3",
        root_path="bucket",
        tenant_id=77,
    )
    service.list_storage_drivers.assert_awaited_once_with()
