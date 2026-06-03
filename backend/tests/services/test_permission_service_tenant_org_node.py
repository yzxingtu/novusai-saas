from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.rbac.services.permission_service import PermissionService


def _perm(
    permission_id: int, code: str, *, enabled: bool = True, deleted: bool = False
):
    return SimpleNamespace(
        id=permission_id,
        code=code,
        is_enabled=enabled,
        is_deleted=deleted,
    )


@pytest.mark.asyncio
async def test_tenant_admin_permissions_merge_role_and_org_node_with_plan_intersection() -> (
    None
):
    """中文: 测试类型 behavioral；账号角色和组织节点直接权限同时生效。

    EN: Test type behavioral; account roles and direct org-node grants both
    contribute to tenant-admin permissions.
    """
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
    service._tenant_admin_permission_domain._get_role = AsyncMock(  # type: ignore[method-assign]
        return_value=SimpleNamespace(
            id=7,
            is_active=True,
            permissions=[
                _perm(12, "tenant.user.manage"),
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
        "tenant.dashboard.view",
        "tenant.user.manage",
    }
    assert await service.get_tenant_admin_effective_permission_ids(tenant_admin) == {
        11,
        12,
    }


@pytest.mark.asyncio
async def test_tenant_admin_org_node_permissions_apply_without_role() -> None:
    """中文: 测试类型 behavioral；未分配权限角色时仍使用组织节点直接授权。

    EN: Test type behavioral; direct org-node grants still apply when no
    permission role is assigned.
    """
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
    assert await service.get_tenant_admin_effective_permission_ids(tenant_admin) == {12}


@pytest.mark.asyncio
async def test_tenant_owner_permissions_are_plan_scoped_without_wildcard() -> None:
    """中文: 测试类型 behavioral；企业所有者权限仍受当前套餐约束。

    EN: Test type behavioral; tenant-owner permissions remain scoped by the
    active plan.
    """
    service = PermissionService(AsyncMock())
    service._get_tenant_plan_permissions = AsyncMock(  # type: ignore[method-assign]
        return_value=(
            {"menu:tenant.catalog", "tenant.catalog:read"},
            {41, 42},
        )
    )
    service._get_tenant_org_node = AsyncMock()  # type: ignore[method-assign]

    tenant_admin = SimpleNamespace(
        tenant_id=9,
        org_node_id=None,
        is_owner=True,
        role_id=None,
    )

    permissions = await service.get_tenant_admin_permissions(tenant_admin)
    permission_ids = await service.get_tenant_admin_effective_permission_ids(
        tenant_admin
    )

    assert permissions == {"menu:tenant.catalog", "tenant.catalog:read"}
    assert "*" not in permissions
    assert permission_ids == {41, 42}
    service._get_tenant_org_node.assert_not_called()


@pytest.mark.asyncio
async def test_tenant_owner_permissions_fail_closed_when_plan_missing() -> None:
    """中文: 测试类型 behavioral；无有效套餐时企业所有者不会回退到全量权限。

    EN: Test type behavioral; tenant owners do not fall back to broad
    permissions when the active plan is missing.
    """
    service = PermissionService(AsyncMock())
    service._get_tenant_plan_permissions = AsyncMock(  # type: ignore[method-assign]
        return_value=None
    )

    tenant_admin = SimpleNamespace(
        tenant_id=9,
        org_node_id=None,
        is_owner=True,
        role_id=None,
    )

    assert await service.get_tenant_admin_permissions(tenant_admin) == set()
    assert (
        await service.get_tenant_admin_effective_permission_ids(tenant_admin) == set()
    )
