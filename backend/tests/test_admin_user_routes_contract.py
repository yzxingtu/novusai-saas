"""
Test type: structural
Scope: admin user route contract and transport-level response shape.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.deps import get_current_active_admin, get_db


def _load_admin_users_module():
    module_path = (
        Path(__file__).resolve().parent.parent / "app" / "api" / "admin" / "users.py"
    )
    spec = importlib.util.spec_from_file_location(
        "test_admin_users_module",
        module_path,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec is not None
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _build_test_app(mock_db, admin_users_module) -> FastAPI:
    app = FastAPI()

    @app.middleware("http")
    async def inject_permissions(request, call_next):
        request.state.user_permissions = {
            "admin_user:list",
            "admin_user:detail",
            "admin_user:force_logout",
        }
        return await call_next(request)

    app.include_router(admin_users_module.AdminUserController.get_router())

    async def override_db():
        yield mock_db

    async def override_admin():
        return SimpleNamespace(id=1, username="admin", is_active=True)

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_active_admin] = override_admin
    return app


def test_admin_user_routes_delegate_to_services(monkeypatch) -> None:
    admin_module = _load_admin_users_module()
    monkeypatch.setattr(admin_module.AdminUserController, "_instance", None)
    monkeypatch.setattr(admin_module.AdminUserController, "_router", None)

    admin = SimpleNamespace(
        id=7,
        username="demo",
        email="demo@example.com",
        phone=None,
        nickname="Demo",
        avatar=None,
        is_active=True,
        is_super=True,
        created_at=None,
        updated_at=None,
        last_login_at=None,
        last_login_ip=None,
        org_node_id=9,
        role=None,
        org_node=None,
    )
    admin_service = SimpleNamespace(
        get_identity_select_options=AsyncMock(return_value={"items": [], "total": 0}),
        get_identity_detail=AsyncMock(return_value=admin),
    )
    auth_service = SimpleNamespace(
        token_sessions=SimpleNamespace(force_logout=AsyncMock(return_value=None)),
    )
    authority_service = SimpleNamespace(
        can_view_member_activity_for_node=AsyncMock(return_value=True),
    )
    ai_access_service = SimpleNamespace(
        get_platform_admin_ai_availability_profile=AsyncMock(return_value={}),
    )

    monkeypatch.setattr(admin_module, "AdminService", lambda _db: admin_service)
    monkeypatch.setattr(admin_module, "AuthService", lambda _db: auth_service)
    monkeypatch.setattr(
        admin_module,
        "AccountAIAccessService",
        lambda _db: ai_access_service,
    )
    monkeypatch.setattr(
        admin_module,
        "AdminOrgAuthorityService",
        lambda _db, _admin: authority_service,
    )
    monkeypatch.setattr(
        admin_module,
        "serialize_admin_identity_detail",
        lambda payload_admin, **_kwargs: {
            "id": payload_admin.id,
            "username": payload_admin.username,
            "can_view_activity": _kwargs["can_view_activity"],
        },
    )

    app = _build_test_app(SimpleNamespace(), admin_module)
    with TestClient(app) as client:
        select_response = client.get(
            "/users/select",
            params={"search": "a", "page": 1, "page_size": 20},
        )
        detail_response = client.get("/users/7")
        logout_response = client.post("/users/7/force-logout")

    assert select_response.status_code == 200
    assert detail_response.status_code == 200
    assert detail_response.json()["data"]["can_view_activity"] is True
    assert logout_response.status_code == 200
    admin_service.get_identity_select_options.assert_awaited_once_with(
        search="a",
        page=1,
        page_size=20,
    )
    assert admin_service.get_identity_detail.await_count >= 1
    admin_service.get_identity_detail.assert_any_await(7)
    ai_access_service.get_platform_admin_ai_availability_profile.assert_awaited_once_with(
        admin
    )
    authority_service.can_view_member_activity_for_node.assert_awaited_once_with(9)
    auth_service.token_sessions.force_logout.assert_awaited_once_with(
        user_type="admin",
        user_id=7,
        tenant_id=None,
    )
