from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.rbac.services.permission_service import PermissionService
from app.services.tenant.tenant_org_authority_service import TenantOrgAuthorityService


def _perm(
    *, permission_id: int, code: str, enabled: bool = True, deleted: bool = False
):
    return SimpleNamespace(
        id=permission_id,
        code=code,
        is_enabled=enabled,
        is_deleted=deleted,
    )


@pytest.mark.asyncio
async def test_owner_can_assign_permissions_for_root_creation(mock_db):
    admin = SimpleNamespace(id=9, tenant_id=7, is_owner=True)
    service = TenantOrgAuthorityService(mock_db, admin)

    assert await service.can_assign_permissions_for_node(None) is True


@pytest.mark.asyncio
async def test_owner_can_assign_permissions_for_root_node(mock_db):
    admin = SimpleNamespace(id=9, tenant_id=7, is_owner=True)
    service = TenantOrgAuthorityService(mock_db, admin)
    service.repo = SimpleNamespace(
        get_by_id=AsyncMock(
            return_value=SimpleNamespace(id=1, is_deleted=False, leader_id=None)
        ),
        get_ancestors=AsyncMock(return_value=[]),
    )

    assert await service.can_assign_permissions_for_node(1) is True


@pytest.mark.asyncio
async def test_tenant_admin_permissions_use_org_node_permissions_when_available(
    mock_db,
):
    service = PermissionService(mock_db)
    service._get_tenant_plan_permissions = AsyncMock(
        return_value=(
            {"menu:org.read", "menu:org.write"},
            {101, 102},
        )
    )
    service._get_tenant_org_node = AsyncMock(
        return_value=SimpleNamespace(
            permissions=[
                _perm(permission_id=101, code="menu:org.read"),
                _perm(permission_id=999, code="menu:outside.plan"),
            ]
        )
    )

    tenant_admin = SimpleNamespace(
        tenant_id=7,
        org_node_id=3,
        role_id=22,
        is_owner=False,
    )

    permissions = await service.get_tenant_admin_permissions(tenant_admin)

    assert permissions == {"menu:org.read"}


@pytest.mark.asyncio
async def test_tenant_admin_effective_permission_ids_use_org_node_permissions_when_available(
    mock_db,
):
    service = PermissionService(mock_db)
    service._get_tenant_plan_permissions = AsyncMock(
        return_value=(
            {"menu:org.read", "menu:org.write"},
            {101, 102},
        )
    )
    service._get_tenant_org_node = AsyncMock(
        return_value=SimpleNamespace(
            permissions=[
                _perm(permission_id=102, code="menu:org.write"),
                _perm(permission_id=888, code="menu:outside.plan"),
            ]
        )
    )

    tenant_admin = SimpleNamespace(
        tenant_id=7,
        org_node_id=3,
        role_id=22,
        is_owner=False,
    )

    permission_ids = await service.get_tenant_admin_effective_permission_ids(
        tenant_admin
    )

    assert permission_ids == {102}
