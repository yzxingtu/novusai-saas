"""
Test type: behavioral / structural
Scope: tenant auth profile response contract.
Mock strategy: service dependencies are replaced with fakes; assertions target
the response shape consumed by the frontend permission store.
"""

from __future__ import annotations

import importlib.util
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

import app.rbac.services as rbac_services_module
import app.services.tenant.tenant_admin_service as tenant_admin_service_module
from app.services.tenant.tenant_admin_service import TenantAdminService


def _load_tenant_auth_module():
    module_path = Path(__file__).resolve().parents[2] / "app/api/tenant/auth.py"
    spec = importlib.util.spec_from_file_location(
        "test_tenant_auth_profile_module",
        module_path,
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _tenant_admin(**overrides):
    data = {
        "ai_enabled": True,
        "avatar": None,
        "created_at": datetime(2026, 5, 14, tzinfo=UTC),
        "email": "owner@example.com",
        "id": 7,
        "is_active": True,
        "is_owner": True,
        "last_login_at": None,
        "nickname": "Owner",
        "phone": None,
        "role": None,
        "role_id": None,
        "tenant_id": 5,
        "username": "owner",
    }
    data.update(overrides)
    return SimpleNamespace(**data)


@pytest.mark.asyncio
async def test_tenant_admin_service_builds_plan_scoped_auth_profile(
    monkeypatch,
) -> None:
    """中文: 测试类型 behavioral；认证资料响应携带套餐内权限码且不返回通配符。

    EN: Test type behavioral; the auth profile response carries plan-scoped
    permission codes and never returns a wildcard for tenant owners.
    """

    class _TenantAdminAuth:
        async def get_profile_flags(self, _tenant_admin):
            return {
                "has_plan": True,
                "plan_name": "Catalog Pro",
            }

    class _AuthService:
        def __init__(self, db):
            self.db = db
            self.tenant_admin_auth = _TenantAdminAuth()

    class _PermissionService:
        def __init__(self, db):
            self.db = db

        async def get_tenant_admin_permissions(self, _tenant_admin):
            return {
                "tenant.catalog:read",
                "menu:tenant.catalog",
            }

    async def _ai_profile(self, _tenant_admin):
        return {
            "ai_unavailable_reason": None,
            "effective_ai_enabled": True,
            "tenant_ai_enabled": True,
        }

    monkeypatch.setattr(tenant_admin_service_module, "AuthService", _AuthService)
    monkeypatch.setattr(
        rbac_services_module,
        "PermissionService",
        _PermissionService,
    )
    monkeypatch.setattr(
        TenantAdminService,
        "get_ai_availability_profile",
        _ai_profile,
    )

    service = TenantAdminService.__new__(TenantAdminService)
    service.db = SimpleNamespace()
    service.tenant_id = 5

    response = await service.build_auth_profile_response(_tenant_admin())

    assert response.has_plan is True
    assert response.plan_name == "Catalog Pro"
    assert response.tenant_ai_enabled is True
    assert response.effective_ai_enabled is True
    assert response.permissions == [
        "tenant.catalog:read",
        "menu:tenant.catalog",
    ]
    assert "*" not in response.permissions


@pytest.mark.asyncio
async def test_tenant_auth_me_delegates_enriched_profile_response(
    monkeypatch,
) -> None:
    """中文: 测试类型 structural；路由只委托服务构建增强认证资料。

    EN: Test type structural; the route delegates enriched auth profile
    response construction to the service layer.
    """
    tenant_auth = _load_tenant_auth_module()
    calls: list[tuple[object, int]] = []
    admin = _tenant_admin()

    class _TenantAdminProfileService:
        def __init__(self, db, tenant_id):
            calls.append((db, tenant_id))

        async def build_auth_profile_response(self, tenant_admin):
            assert tenant_admin is admin
            return tenant_admin_service_module.TenantAdminResponse.from_model(
                tenant_admin,
                has_plan=True,
                permissions=["menu:tenant.catalog"],
            )

    monkeypatch.setattr(
        tenant_auth,
        "TenantAdminService",
        _TenantAdminProfileService,
    )

    db = SimpleNamespace()
    payload = await tenant_auth.get_current_tenant_admin_info(db, admin)

    assert calls == [(db, 5)]
    assert payload["data"]["permissions"] == ["menu:tenant.catalog"]
    assert payload["data"]["has_plan"] is True


@pytest.mark.asyncio
async def test_tenant_auth_profile_delegates_enriched_profile_response(
    monkeypatch,
) -> None:
    """中文: 测试类型 structural；资料更新后返回同一增强认证资料契约。

    EN: Test type structural; profile updates return the same enriched auth
    profile response contract.
    """
    tenant_auth = _load_tenant_auth_module()
    updated_admin = _tenant_admin(nickname="New Owner")
    update_calls: list[dict] = []

    class _TenantAdminAuth:
        async def update_profile(self, *, tenant_admin, profile_data):
            update_calls.append(
                {
                    "profile_data": dict(profile_data),
                    "tenant_admin": tenant_admin,
                }
            )
            return updated_admin

    class _AuthService:
        def __init__(self, db):
            self.db = db
            self.tenant_admin_auth = _TenantAdminAuth()

    class _TenantAdminProfileService:
        def __init__(self, db, tenant_id):
            self.db = db
            self.tenant_id = tenant_id

        async def build_auth_profile_response(self, tenant_admin):
            assert tenant_admin is updated_admin
            return tenant_admin_service_module.TenantAdminResponse.from_model(
                tenant_admin,
                has_plan=True,
                permissions=["menu:tenant.catalog"],
            )

    monkeypatch.setattr(tenant_auth, "AuthService", _AuthService)
    monkeypatch.setattr(
        tenant_auth,
        "TenantAdminService",
        _TenantAdminProfileService,
    )

    db = SimpleNamespace(commit=lambda: None)

    async def _commit():
        return None

    db.commit = _commit
    current_admin = _tenant_admin()
    payload = await tenant_auth.update_profile(
        db,
        current_admin,
        SimpleNamespace(
            model_dump=lambda exclude_unset=True: {
                "nickname": "New Owner",
            }
        ),
    )

    assert update_calls == [
        {
            "profile_data": {"nickname": "New Owner"},
            "tenant_admin": current_admin,
        }
    ]
    assert payload["data"]["nickname"] == "New Owner"
    assert payload["data"]["permissions"] == ["menu:tenant.catalog"]
