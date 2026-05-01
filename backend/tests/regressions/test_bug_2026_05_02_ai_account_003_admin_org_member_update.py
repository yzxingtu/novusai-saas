"""
Test type: behavioral
Regression for: BUG-2026-05-02-AI-ACCOUNT-003
Scope: PUT /admin/organization/{org_node_id}/members/{admin_id} preserves
ai_enabled=false through route parsing, service call, and response payload;
create member defaults do not grant AI when the operator is not the node leader.
Mock strategy: FastAPI dependencies, org authority, commit, and
AdminOrgNodeService are sentinels; request parsing, permission helper, route
logic, success response, and member serializer run real.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from fastapi import FastAPI, HTTPException, status
from fastapi.testclient import TestClient

from app.api.shared._ai_account_guard import ORGANIZATION_MANAGE_MEMBER_AI_PERMISSION
from app.core.deps import get_current_active_admin, get_db


def _load_module(relative_path: str, module_name: str):
    module_path = Path(__file__).resolve().parents[2] / relative_path
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    if spec is None or spec.loader is None:
        raise AssertionError(f"Unable to load module {relative_path}")
    spec.loader.exec_module(module)
    return module


def test_admin_org_member_update_preserves_explicit_ai_enabled_false(
    monkeypatch,
) -> None:
    module = _load_module(
        "app/api/admin/organization.py",
        "test_admin_org_member_ai_update_route_contract",
    )
    monkeypatch.setattr(module.AdminOrganizationController, "_instance", None)
    monkeypatch.setattr(module.AdminOrganizationController, "_router", None)

    service_events: list[dict[str, Any]] = []
    member_ai_scope_allowed = False

    async def allow_manage(self, db, current_admin, org_node_id):
        return None

    async def gate_member_ai_scope(self, db, current_admin, org_node_id):
        if not member_ai_scope_allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="not leader",
            )

    async def serialize_members(self, db, current_admin, members):
        return [
            module._serialize_member(
                member,
                ai_profile={
                    "effective_ai_enabled": member.ai_enabled,
                    "ai_unavailable_reason": None,
                },
                can_manage_ai=member_ai_scope_allowed,
            )
            for member in members
        ]

    async def passthrough_commit(db, operation):
        return await operation

    class SentinelAuthorityService:
        def __init__(self, *_args):
            pass

        async def can_manage_member_ai_for_node(self, _org_node_id):
            return member_ai_scope_allowed

    class SentinelOrgNodeService:
        def __init__(self, *_args):
            pass

        async def update_member(self, **kwargs):
            service_events.append(kwargs)
            org_node_id = kwargs.get("new_org_node_id") or kwargs["org_node_id"]
            return SimpleNamespace(
                id=kwargs["admin_id"],
                username="adminaa",
                nickname=kwargs.get("nickname"),
                avatar=kwargs.get("avatar"),
                email=kwargs.get("email") or "member@example.com",
                is_active=(
                    kwargs.get("is_active")
                    if kwargs.get("is_active") is not None
                    else True
                ),
                ai_enabled=kwargs["ai_enabled"],
                created_at=None,
                updated_at=None,
                role_id=1,
                role=SimpleNamespace(name="平台管理组"),
                org_node_id=org_node_id,
                org_node=SimpleNamespace(name="平台管理组", leader_id=None),
            )

    monkeypatch.setattr(
        module.AdminOrganizationController,
        "_require_manage",
        allow_manage,
    )
    monkeypatch.setattr(
        module.AdminOrganizationController,
        "_require_manage_member_ai",
        gate_member_ai_scope,
    )
    monkeypatch.setattr(
        module.AdminOrganizationController,
        "_serialize_members_for_operator",
        serialize_members,
    )
    monkeypatch.setattr(module, "commit_or_raise_http", passthrough_commit)
    monkeypatch.setattr(module, "AdminOrgAuthorityService", SentinelAuthorityService)
    monkeypatch.setattr(module, "AdminOrgNodeService", SentinelOrgNodeService)

    async def override_db():
        yield SimpleNamespace()

    async def override_admin():
        return SimpleNamespace(id=1, is_active=True, is_super=False)

    def make_app(permissions: set[str]) -> FastAPI:
        app = FastAPI()

        @app.middleware("http")
        async def inject_permissions(request, call_next):
            request.state.user_permissions = permissions
            return await call_next(request)

        app.include_router(
            module.AdminOrganizationController.get_router(),
            prefix="/admin",
        )
        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_current_active_admin] = override_admin
        return app

    payload = {
        "email": "1034010678@qq.com",
        "phone": None,
        "nickname": None,
        "is_active": True,
        "ai_enabled": False,
        "avatar": "27",
        "org_node_id": 1,
    }

    with TestClient(make_app({"organization:update_member"})) as client:
        response = client.put("/admin/organization/7/members/33", json=payload)

    assert response.status_code == 403
    assert service_events == []

    with TestClient(
        make_app(
            {
                "organization:update_member",
                ORGANIZATION_MANAGE_MEMBER_AI_PERMISSION,
            },
        ),
    ) as client:
        response = client.put("/admin/organization/7/members/33", json=payload)

    assert response.status_code == 403
    assert service_events == []

    member_ai_scope_allowed = True
    with TestClient(
        make_app(
            {
                "organization:update_member",
                ORGANIZATION_MANAGE_MEMBER_AI_PERMISSION,
            },
        ),
    ) as client:
        response = client.put("/admin/organization/7/members/33", json=payload)

    assert response.status_code == 200
    assert service_events[-1]["ai_enabled"] is False
    assert service_events[-1]["update_ai_enabled"] is True
    assert response.json()["data"]["ai_enabled"] is False


def test_admin_org_member_create_defaults_ai_disabled_without_leader_scope(
    monkeypatch,
) -> None:
    module = _load_module(
        "app/api/admin/organization.py",
        "test_admin_org_member_ai_create_route_contract",
    )
    monkeypatch.setattr(module.AdminOrganizationController, "_instance", None)
    monkeypatch.setattr(module.AdminOrganizationController, "_router", None)

    service_events: list[dict[str, Any]] = []
    member_ai_scope_allowed = False

    async def allow_manage(self, db, current_admin, org_node_id):
        return None

    async def gate_member_ai_scope(self, db, current_admin, org_node_id):
        if not member_ai_scope_allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="not leader",
            )

    async def serialize_members(self, db, current_admin, members):
        return [
            module._serialize_member(
                member,
                ai_profile={
                    "effective_ai_enabled": member.ai_enabled,
                    "ai_unavailable_reason": None,
                },
                can_manage_ai=member_ai_scope_allowed,
            )
            for member in members
        ]

    async def passthrough_commit(db, operation):
        return await operation

    class SentinelAuthorityService:
        def __init__(self, *_args):
            pass

        async def can_manage_member_ai_for_node(self, _org_node_id):
            return member_ai_scope_allowed

    class SentinelOrgNodeService:
        def __init__(self, *_args):
            pass

        async def create_member(self, **kwargs):
            service_events.append(kwargs)
            return SimpleNamespace(
                id=44,
                username=kwargs["username"],
                nickname=kwargs.get("nickname"),
                avatar=None,
                email=kwargs["email"],
                is_active=kwargs.get("is_active", True),
                ai_enabled=kwargs["ai_enabled"],
                created_at=None,
                updated_at=None,
                role_id=1,
                role=SimpleNamespace(name="平台管理组"),
                org_node_id=kwargs["org_node_id"],
                org_node=SimpleNamespace(name="平台管理组", leader_id=None),
            )

    monkeypatch.setattr(
        module.AdminOrganizationController,
        "_require_manage",
        allow_manage,
    )
    monkeypatch.setattr(
        module.AdminOrganizationController,
        "_require_manage_member_ai",
        gate_member_ai_scope,
    )
    monkeypatch.setattr(
        module.AdminOrganizationController,
        "_serialize_members_for_operator",
        serialize_members,
    )
    monkeypatch.setattr(module, "commit_or_raise_http", passthrough_commit)
    monkeypatch.setattr(module, "AdminOrgAuthorityService", SentinelAuthorityService)
    monkeypatch.setattr(module, "AdminOrgNodeService", SentinelOrgNodeService)

    async def override_db():
        yield SimpleNamespace()

    async def override_admin():
        return SimpleNamespace(id=1, is_active=True, is_super=False)

    def make_app(permissions: set[str]) -> FastAPI:
        app = FastAPI()

        @app.middleware("http")
        async def inject_permissions(request, call_next):
            request.state.user_permissions = permissions
            return await call_next(request)

        app.include_router(
            module.AdminOrganizationController.get_router(),
            prefix="/admin",
        )
        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_current_active_admin] = override_admin
        return app

    payload = {
        "email": "member@example.com",
        "is_active": True,
        "nickname": "Ops",
        "password": "secret123",
        "phone": None,
        "username": "ops_admin",
    }

    with TestClient(make_app({"organization:create_member"})) as client:
        response = client.post("/admin/organization/7/members/create", json=payload)

    assert response.status_code == 200
    assert service_events[-1]["ai_enabled"] is False
    assert response.json()["data"]["ai_enabled"] is False

    service_events.clear()
    with TestClient(
        make_app(
            {
                "organization:create_member",
                ORGANIZATION_MANAGE_MEMBER_AI_PERMISSION,
            },
        ),
    ) as client:
        response = client.post(
            "/admin/organization/7/members/create",
            json={**payload, "ai_enabled": False},
        )

    assert response.status_code == 403
    assert service_events == []

    member_ai_scope_allowed = True
    with TestClient(
        make_app(
            {
                "organization:create_member",
                ORGANIZATION_MANAGE_MEMBER_AI_PERMISSION,
            },
        ),
    ) as client:
        response = client.post(
            "/admin/organization/7/members/create",
            json={**payload, "ai_enabled": False},
        )

    assert response.status_code == 200
    assert service_events[-1]["ai_enabled"] is False
    assert response.json()["data"]["ai_enabled"] is False
