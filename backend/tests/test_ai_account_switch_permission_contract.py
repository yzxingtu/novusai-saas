"""
Test type: behavioral
Regression for: BUG-2026-05-02-AI-ACCOUNT-003
Scope: Account-level AI switch management permission helper and route seams.
Mock strategy: Request body transport is represented by a small fake request;
the permission wildcard and explicit-code decision use the real RBAC checker.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.api.shared._ai_account_guard import (
    ORGANIZATION_MANAGE_MEMBER_AI_PERMISSION,
    TENANT_ADMIN_MANAGE_AI_PERMISSION,
    resolve_authorized_ai_enabled_override,
)
from app.core.deps import get_current_active_admin, get_db
from app.enums.rbac import PermissionScope
from app.rbac.registry import permission_registry


def _load_module(relative_path: str, module_name: str):
    module_path = Path(__file__).resolve().parent.parent / relative_path
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    if spec is None or spec.loader is None:
        raise AssertionError(f"Unable to load module {relative_path}")
    spec.loader.exec_module(module)
    return module


class _AIEnabledPayload(BaseModel):
    ai_enabled: bool = True
    nickname: str | None = None


class _NicknamePayload(BaseModel):
    nickname: str | None = None


class _FakeRequest:
    def __init__(self, *, body: dict[str, Any], permissions: set[str]) -> None:
        self._body = body
        self.state = SimpleNamespace(user_permissions=permissions)

    async def json(self) -> dict[str, Any]:
        return self._body


@pytest.mark.asyncio
async def test_missing_ai_enabled_skips_dedicated_permission_check() -> None:
    request = _FakeRequest(body={}, permissions=set())
    data = _NicknamePayload(nickname="plain edit")

    result = await resolve_authorized_ai_enabled_override(
        request=request,  # type: ignore[arg-type]
        data=data,
        permission_code=ORGANIZATION_MANAGE_MEMBER_AI_PERMISSION,
    )

    assert result is None


@pytest.mark.asyncio
async def test_explicit_ai_enabled_false_requires_manage_ai_permission() -> None:
    request = _FakeRequest(body={"ai_enabled": False}, permissions=set())
    data = _AIEnabledPayload(ai_enabled=False)

    with pytest.raises(HTTPException) as exc_info:
        await resolve_authorized_ai_enabled_override(
            request=request,  # type: ignore[arg-type]
            data=data,
            permission_code=ORGANIZATION_MANAGE_MEMBER_AI_PERMISSION,
        )

    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_explicit_ai_enabled_false_is_preserved_with_permission() -> None:
    request = _FakeRequest(
        body={"ai_enabled": False},
        permissions={ORGANIZATION_MANAGE_MEMBER_AI_PERMISSION},
    )
    data = _AIEnabledPayload(ai_enabled=False)

    result = await resolve_authorized_ai_enabled_override(
        request=request,  # type: ignore[arg-type]
        data=data,
        permission_code=ORGANIZATION_MANAGE_MEMBER_AI_PERMISSION,
    )

    assert result is False


@pytest.mark.asyncio
async def test_raw_json_ai_enabled_false_requires_permission_when_schema_omits_field() -> None:
    request = _FakeRequest(body={"ai_enabled": False}, permissions={"*"})
    data = _NicknamePayload(nickname="schema without switch")

    result = await resolve_authorized_ai_enabled_override(
        request=request,  # type: ignore[arg-type]
        data=data,
        permission_code=ORGANIZATION_MANAGE_MEMBER_AI_PERMISSION,
    )

    assert result is False


@pytest.mark.asyncio
async def test_explicit_tenant_admin_ai_enabled_false_requires_manage_ai_permission() -> None:
    request = _FakeRequest(body={"ai_enabled": False}, permissions=set())
    data = _AIEnabledPayload(ai_enabled=False)

    with pytest.raises(HTTPException) as exc_info:
        await resolve_authorized_ai_enabled_override(
            request=request,  # type: ignore[arg-type]
            data=data,
            permission_code=TENANT_ADMIN_MANAGE_AI_PERMISSION,
        )

    assert exc_info.value.status_code == 403


def test_ai_switch_permissions_register_under_expected_parent_menus() -> None:
    _load_module(
        "app/api/admin/organization.py",
        "test_admin_org_ai_permission_registration",
    )
    _load_module(
        "app/api/tenant/organization.py",
        "test_tenant_org_ai_permission_registration",
    )
    _load_module(
        "app/api/admin/tenant_admins.py",
        "test_tenant_admin_ai_permission_registration",
    )

    admin_org_perm = permission_registry.get(
        ORGANIZATION_MANAGE_MEMBER_AI_PERMISSION,
        PermissionScope.ADMIN,
    )
    tenant_org_perm = permission_registry.get(
        ORGANIZATION_MANAGE_MEMBER_AI_PERMISSION,
        PermissionScope.TENANT,
    )
    tenant_admin_perm = permission_registry.get(
        TENANT_ADMIN_MANAGE_AI_PERMISSION,
        PermissionScope.ADMIN,
    )

    assert admin_org_perm is not None
    assert admin_org_perm.parent_code == "menu:admin.organization"
    assert tenant_org_perm is not None
    assert tenant_org_perm.parent_code == "menu:tenant.organization"
    assert tenant_admin_perm is not None
    assert tenant_admin_perm.parent_code == "menu:admin.tenant"


def test_platform_tenant_admin_route_requires_manage_ai_for_explicit_switch(
    monkeypatch,
) -> None:
    module = _load_module(
        "app/api/admin/tenant_admins.py",
        "test_platform_tenant_admin_ai_route_permission",
    )
    monkeypatch.setattr(module.AdminTenantAdminController, "_instance", None)
    monkeypatch.setattr(module.AdminTenantAdminController, "_router", None)

    workflow_events: list[dict[str, Any]] = []

    class SentinelWorkflow:
        def __init__(self, *_args):
            workflow_events.append({"event": "constructed"})

        async def create_tenant_admin(self, *, data, tenant_id):
            workflow_events.append(
                {
                    "ai_enabled": data.ai_enabled,
                    "event": "create",
                    "tenant_id": tenant_id,
                }
            )
            return {"ai_enabled": data.ai_enabled, "id": 33}

    monkeypatch.setattr(module, "TenantAdminWorkflowService", SentinelWorkflow)

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

        app.include_router(module.AdminTenantAdminController.get_router())
        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_current_active_admin] = override_admin
        return app

    base_payload = {
        "email": "ops@example.com",
        "nickname": "Ops",
        "password": "secret123",
        "username": "ops_admin",
    }

    with TestClient(make_app({"tenant_admin:create"})) as client:
        response = client.post("/tenants/9/admins", json=base_payload)

    assert response.status_code == 200
    assert workflow_events[-1] == {
        "ai_enabled": True,
        "event": "create",
        "tenant_id": 9,
    }

    workflow_events.clear()
    with TestClient(make_app({"tenant_admin:create"})) as client:
        response = client.post(
            "/tenants/9/admins",
            json={**base_payload, "ai_enabled": False},
        )

    assert response.status_code == 403
    assert workflow_events == []

    with TestClient(
        make_app({"tenant_admin:create", TENANT_ADMIN_MANAGE_AI_PERMISSION})
    ) as client:
        response = client.post(
            "/tenants/9/admins",
            json={**base_payload, "ai_enabled": False},
        )

    assert response.status_code == 200
    assert workflow_events[-1] == {
        "ai_enabled": False,
        "event": "create",
        "tenant_id": 9,
    }
