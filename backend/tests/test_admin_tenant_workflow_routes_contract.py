from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.deps import get_current_active_admin, get_db


def _load_admin_tenants_module():
    module_path = (
        Path(__file__).resolve().parent.parent / "app" / "api" / "admin" / "tenants.py"
    )
    spec = importlib.util.spec_from_file_location(
        "test_admin_tenants_workflow_module",
        module_path,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec is not None
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _build_test_app(mock_db, admin_tenants_module) -> FastAPI:
    app = FastAPI()

    @app.middleware("http")
    async def inject_permissions(request, call_next):
        request.state.user_permissions = {
            "tenant:detail",
            "tenant:update",
            "tenant:impersonate",
        }
        return await call_next(request)

    app.include_router(admin_tenants_module.AdminTenantController.get_router())

    async def override_db():
        yield mock_db

    async def override_admin():
        return SimpleNamespace(id=1, username="admin", is_active=True)

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_active_admin] = override_admin
    return app


def test_impersonate_route_delegates_to_service(monkeypatch) -> None:
    admin_tenants_module = _load_admin_tenants_module()
    monkeypatch.setattr(admin_tenants_module.AdminTenantController, "_instance", None)
    monkeypatch.setattr(admin_tenants_module.AdminTenantController, "_router", None)

    service = SimpleNamespace(
        issue_tenant_admin_token=AsyncMock(
            return_value={
                "impersonate_token": "token-123",
                "tenant_code": "t-demo",
                "tenant_name": "Demo Tenant",
                "expires_in": 60,
            }
        )
    )
    monkeypatch.setattr(
        admin_tenants_module,
        "TenantImpersonationService",
        lambda _db: service,
    )

    app = _build_test_app(SimpleNamespace(), admin_tenants_module)
    with TestClient(app) as client:
        response = client.post("/tenants/7/impersonate", json={"role_id": 11})

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 0
    assert payload["data"]["impersonate_token"] == "token-123"

    awaited = service.issue_tenant_admin_token.await_args
    assert awaited.kwargs["tenant_id"] == 7
    assert awaited.kwargs["role_id"] == 11
    assert awaited.kwargs["current_admin"].id == 1


def test_storage_routes_delegate_to_service(monkeypatch) -> None:
    admin_tenants_module = _load_admin_tenants_module()
    monkeypatch.setattr(admin_tenants_module.AdminTenantController, "_instance", None)
    monkeypatch.setattr(admin_tenants_module.AdminTenantController, "_router", None)

    service = SimpleNamespace(
        get_tenant_storage_config=AsyncMock(
            return_value={"tenant_id": 7, "tenant_storage_driver": "s3"}
        ),
        update_tenant_storage_config=AsyncMock(return_value=None),
        test_tenant_storage_connection=AsyncMock(return_value={"success": True}),
    )
    monkeypatch.setattr(
        admin_tenants_module,
        "TenantStorageAdminService",
        lambda _db: service,
    )

    app = _build_test_app(SimpleNamespace(), admin_tenants_module)
    with TestClient(app) as client:
        get_response = client.get("/tenants/7/storage-config")
        update_response = client.put(
            "/tenants/7/storage-config",
            json={
                "tenant_storage_driver": "s3",
                "tenant_storage_mode": "admin_override",
            },
        )
        test_response = client.post(
            "/tenants/7/storage-config/test",
            json={
                "driver": "s3",
                "root_path": "bucket",
                "base_url": "",
                "config": {"region": "us-east-1"},
            },
        )

    assert get_response.status_code == 200
    assert update_response.status_code == 200
    assert test_response.status_code == 200
    service.get_tenant_storage_config.assert_awaited_once_with(7)
    service.update_tenant_storage_config.assert_awaited_once_with(
        tenant_id=7,
        data={"tenant_storage_driver": "s3", "tenant_storage_mode": "admin_override"},
    )
    service.test_tenant_storage_connection.assert_awaited_once_with(
        driver="s3",
        root_path="bucket",
        base_url="",
        config={"region": "us-east-1"},
    )
