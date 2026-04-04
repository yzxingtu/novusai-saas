from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.rbac.services.permission_service import PermissionService


def _perm(permission_id: int, code: str, *, enabled: bool = True, deleted: bool = False):
    return SimpleNamespace(
        id=permission_id,
        code=code,
        is_enabled=enabled,
        is_deleted=deleted,
    )


@pytest.mark.asyncio
async def test_tenant_admin_permissions_prefer_org_node_permissions_with_plan_intersection() -> None:
    service = PermissionService(AsyncMock())
    service._get_tenant_plan_permissions = AsyncMock(  # type: ignore[method-assign]
        return_value=(
            {"tenant.dashboard.view", "tenant.user.manage"},
            {11, 12},
        )
    )
    service._get_tenant_org_node = AsyncMock(  # type: ignore[method-assign]
        return_value=SimpleNamespace(
            id=31,
            permissions=[
                _perm(11, "tenant.dashboard.view"),
                _perm(99, "tenant.hidden.debug"),
            ],
        )
    )

    tenant_admin = SimpleNamespace(
        tenant_id=9,
        org_node_id=31,
        is_owner=False,
        role_id=7,
    )

    assert await service.get_tenant_admin_permissions(tenant_admin) == {
        "tenant.dashboard.view"
    }
    assert await service.get_tenant_admin_effective_permission_ids(tenant_admin) == {
        11
    }


@pytest.mark.asyncio
async def test_tenant_admin_org_node_permissions_override_role_when_org_binding_exists() -> None:
    service = PermissionService(AsyncMock())
    service._get_tenant_plan_permissions = AsyncMock(  # type: ignore[method-assign]
        return_value=(
            {"tenant.dashboard.view", "tenant.user.manage"},
            {11, 12},
        )
    )
    service._get_tenant_org_node = AsyncMock(  # type: ignore[method-assign]
        return_value=SimpleNamespace(
            id=31,
            permissions=[_perm(12, "tenant.user.manage")],
        )
    )

    tenant_admin = SimpleNamespace(
        tenant_id=9,
        org_node_id=31,
        is_owner=False,
        role_id=None,
    )

    assert await service.get_tenant_admin_permissions(tenant_admin) == {
        "tenant.user.manage"
    }
    assert await service.get_tenant_admin_effective_permission_ids(tenant_admin) == {
        12
    }
