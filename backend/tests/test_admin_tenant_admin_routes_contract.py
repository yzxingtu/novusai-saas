from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.deps import get_current_active_admin, get_db


def _load_admin_tenant_admins_module():
    module_path = (
        Path(__file__).resolve().parent.parent
        / "app"
        / "api"
        / "admin"
        / "tenant_admins.py"
    )
    spec = importlib.util.spec_from_file_location(
        "test_admin_tenant_admins_module",
        module_path,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec is not None
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _build_test_app(mock_db, admin_tenant_admins_module) -> FastAPI:
    app = FastAPI()

    @app.middleware("http")
    async def inject_permissions(request, call_next):
        request.state.user_permissions = {
            "tenant_admin:list",
            "tenant_admin:detail",
            "tenant_admin:create",
            "tenant_admin:update",
            "tenant_admin:force_logout",
        }
        return await call_next(request)

    app.include_router(
        admin_tenant_admins_module.AdminTenantAdminController.get_router()
    )

    async def override_db():
        yield mock_db

    async def override_admin():
        return SimpleNamespace(id=1, username="admin", is_active=True)

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_active_admin] = override_admin
    return app


def test_tenant_admin_routes_delegate_to_workflow(monkeypatch) -> None:
    admin_module = _load_admin_tenant_admins_module()
    monkeypatch.setattr(admin_module.AdminTenantAdminController, "_instance", None)
    monkeypatch.setattr(admin_module.AdminTenantAdminController, "_router", None)

    workflow = SimpleNamespace(
        list_tenant_admins=AsyncMock(return_value=[]),
        select_tenant_admins=AsyncMock(return_value={"items": [], "total": 0}),
        get_tenant_admin_detail=AsyncMock(
            return_value={
                "id": 7,
                "username": "demo",
                "email": "demo@example.com",
                "phone": None,
                "nickname": "Demo",
                "avatar": None,
                "is_active": True,
                "is_owner": False,
                "tenant_id": 5,
                "created_at": None,
                "updated_at": None,
                "last_login_at": None,
                "last_login_ip": None,
                "role_id": None,
                "role_name": None,
                "org_node_id": None,
                "org_node_name": None,
                "display_name": "Demo",
                "display_role_name": None,
                "user_type": "tenant_admin",
            }
        ),
        create_tenant_admin=AsyncMock(return_value={"id": 7, "username": "demo"}),
        update_tenant_admin=AsyncMock(return_value={"id": 7, "username": "demo"}),
        toggle_admin_status=AsyncMock(return_value={"id": 7, "is_active": True}),
        force_logout_tenant_admin=AsyncMock(return_value="ok"),
    )
    monkeypatch.setattr(
        admin_module,
        "TenantAdminWorkflowService",
        lambda _db: workflow,
    )

    app = _build_test_app(SimpleNamespace(), admin_module)
    with TestClient(app) as client:
        list_response = client.get("/tenants/5/admins")
        select_response = client.get(
            "/tenants/5/admins/select",
            params={"search": "a", "page": 1, "page_size": 20},
        )
        detail_response = client.get("/tenants/5/admins/7")
        create_response = client.post(
            "/tenants/5/admins",
            json={
                "username": "demo",
                "email": "demo@example.com",
                "password": "secret123",
                "nickname": "Demo",
                "role_id": None,
                "org_node_id": None,
            },
        )
        update_response = client.put(
            "/tenants/5/admins/7",
            json={
                "nickname": "Demo",
                "is_active": True,
            },
        )
        status_response = client.put(
            "/tenants/5/admins/7/status",
            json={"is_active": True},
        )
        logout_response = client.post("/tenants/5/admins/7/force-logout")

    assert list_response.status_code == 200
    assert select_response.status_code == 200
    assert detail_response.status_code == 200
    assert create_response.status_code == 200
    assert update_response.status_code == 200
    assert status_response.status_code == 200
    assert logout_response.status_code == 200
    workflow.list_tenant_admins.assert_awaited_once_with(tenant_id=5)
    workflow.select_tenant_admins.assert_awaited_once()
    workflow.get_tenant_admin_detail.assert_awaited_once_with(
        tenant_id=5,
        admin_id=7,
    )
    workflow.create_tenant_admin.assert_awaited_once()
    workflow.update_tenant_admin.assert_awaited_once()
    workflow.toggle_admin_status.assert_awaited_once()
    workflow.force_logout_tenant_admin.assert_awaited_once_with(
        tenant_id=5,
        admin_id=7,
    )
