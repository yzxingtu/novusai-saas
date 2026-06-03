"""
Test type: behavioral
Regression for: tenant plan permissions bypassed by PermissionMiddleware owner '*'.
Scope: Tenant-admin permission preload must use the same plan-aware resolver as
the rest of RBAC so decorators read a plan-limited permission set.
Mock strategy: The DB/session and authority resolver are fakes; the permission
service return value is the observable contract under test.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.middleware import permission as permission_module


class _Result:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class _SessionContext:
    def __init__(self, db):
        self._db = db

    async def __aenter__(self):
        return self._db

    async def __aexit__(self, *_args):
        return None


class _Authority:
    scope_mode = "all"
    visible_org_ids: list[int] = []
    manageable_org_ids: list[int] = []
    scope_root_ids: list[int] = []
    effective_scope_org_ids: list[int] = []
    primary_org_id = None
    custom_org_ids: list[int] = []


class _OrgAuthorityResolver:
    def __init__(self, _db):
        pass

    async def resolve_tenant_admin(self, _tenant_admin):
        return _Authority()


@pytest.mark.asyncio
async def test_tenant_admin_permissions_are_loaded_from_plan_aware_service(
    monkeypatch,
) -> None:
    tenant_admin = SimpleNamespace(
        id=7,
        is_active=True,
        is_owner=True,
        tenant_id=5,
    )
    db = SimpleNamespace(
        execute=lambda *_args, **_kwargs: _Result(tenant_admin),
    )
    permission_calls: list[SimpleNamespace] = []

    async def execute(*_args, **_kwargs):
        return _Result(tenant_admin)

    db.execute = execute

    class _PermissionService:
        def __init__(self, _db):
            pass

        async def get_tenant_admin_permissions(self, current_admin):
            permission_calls.append(current_admin)
            return {"tenant_dashboard:list"}

    monkeypatch.setattr(
        permission_module,
        "async_session_factory",
        lambda: _SessionContext(db),
    )
    monkeypatch.setattr(
        "app.rbac.services.permission_service.PermissionService",
        _PermissionService,
    )
    monkeypatch.setattr(
        permission_module,
        "OrgAuthorityResolver",
        _OrgAuthorityResolver,
    )

    request = SimpleNamespace(
        state=SimpleNamespace(user_permissions=set(), user=None, data_permission={})
    )
    middleware = permission_module.PermissionMiddleware(app=lambda *_args: None)

    await middleware._load_tenant_admin_permissions(request, tenant_admin.id)

    assert permission_calls == [tenant_admin]
    assert request.state.user is tenant_admin
    assert request.state.user_permissions == {"tenant_dashboard:list"}
