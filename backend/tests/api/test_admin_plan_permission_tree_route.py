from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _get_endpoint(path: str, method: str):
    from app.api.admin.plans import AdminPlanController

    router = AdminPlanController.get_router()
    for route in router.routes:
        if getattr(route, "path", None) == path and method in route.methods:
            return route.endpoint
    raise AssertionError(f"Route not found: {method} {path}")


@pytest.mark.asyncio
async def test_get_available_permissions_reuses_permission_service_projection() -> None:
    endpoint = _get_endpoint("/plans/available-permissions", "GET")

    db = AsyncMock()
    request = MagicMock()
    admin = SimpleNamespace(id=1)
    raw_permissions = [SimpleNamespace(id=8, parent_id=3)]
    filled_permissions = [
        SimpleNamespace(
            id=3,
            code="menu:tenant_mgmt",
            name="menu.admin.tenant_mgmt",
            type="menu",
            resource="tenant_mgmt",
            parent_id=None,
            sort_order=5,
        ),
        SimpleNamespace(
            id=8,
            code="menu:tenant_plan",
            name="menu.admin.tenant_plan",
            type="menu",
            resource="tenant_plan",
            parent_id=3,
            sort_order=10,
        ),
    ]
    projected_tree = [
        {
            "id": 3,
            "code": "menu:tenant_mgmt",
            "name": "Tenant Management",
            "type": "menu",
            "resource": "tenant_mgmt",
            "parent_id": None,
            "sort_order": 5,
            "children": [],
        }
    ]

    plan_service = MagicMock()
    plan_service.get_available_permissions = AsyncMock(return_value=raw_permissions)
    permission_service = MagicMock()
    permission_service.fill_parent_permissions_for_tree = AsyncMock(
        return_value=filled_permissions
    )
    permission_service.build_simple_permission_tree = MagicMock(
        return_value=projected_tree
    )

    with (
        patch(
            "app.api.admin.plans.TenantPlanService",
            return_value=plan_service,
        ),
        patch(
            "app.api.admin.plans.PermissionService",
            return_value=permission_service,
        ),
    ):
        response = await endpoint(request, db, admin)

    plan_service.get_available_permissions.assert_awaited_once_with()
    permission_service.fill_parent_permissions_for_tree.assert_awaited_once_with(
        raw_permissions
    )
    permission_service.build_simple_permission_tree.assert_called_once_with(
        filled_permissions
    )
    assert response["data"] == projected_tree
