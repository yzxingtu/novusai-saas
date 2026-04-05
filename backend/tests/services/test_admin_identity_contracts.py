from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.api.admin.organization import _serialize_member
from app.api.admin.tenant_admins import router as admin_tenant_admins_router
from app.api.admin.users import router as admin_users_router
from app.services.system.admin_service import AdminService
from app.services.tenant.tenant_admin_service import TenantAdminService


def test_admin_identity_select_routes_registered() -> None:
    paths = {route.path for route in admin_users_router.routes}
    assert "/users/select" in paths

    tenant_paths = {route.path for route in admin_tenant_admins_router.routes}
    assert "/tenants/{tenant_id}/admins/select" in tenant_paths


@pytest.mark.asyncio
async def test_admin_identity_select_options_include_rich_extra() -> None:
    admin = SimpleNamespace(
        id=42,
        username="platform_admin",
        nickname="平台管理员",
        avatar="avatar-1",
        org_node_id=7,
        is_active=True,
        is_super=True,
        role=SimpleNamespace(name="平台角色"),
        org_node=SimpleNamespace(name="平台组织", leader_id=42),
    )
    service = object.__new__(AdminService)
    service.repo = SimpleNamespace(
        query_identity_select=AsyncMock(return_value=([admin], 1))
    )

    response = await AdminService.get_identity_select_options(
        service,
        search="platform",
        page=1,
        page_size=20,
    )

    assert response.total == 1
    assert response.page == 1
    assert response.page_size == 20
    assert response.has_more is False
    assert len(response.items) == 1

    option = response.items[0]
    assert option.label == "平台管理员"
    assert option.value == 42
    assert option.disabled is False
    assert option.extra == {
        "username": "platform_admin",
        "nickname": "平台管理员",
        "avatar": "avatar-1",
        "org_node_id": 7,
        "org_node_name": "平台组织",
        "role_name": "平台角色",
        "user_type": "admin",
        "is_active": True,
        "is_leader": True,
        "is_owner": False,
    }


@pytest.mark.asyncio
async def test_tenant_admin_identity_select_options_include_rich_extra() -> None:
    tenant_admin = SimpleNamespace(
        id=9,
        username="tenant_owner",
        nickname="企业所有者",
        avatar="avatar-9",
        org_node_id=88,
        is_active=False,
        is_owner=True,
        role=SimpleNamespace(name="企业角色"),
        org_node=SimpleNamespace(name="企业组织", leader_id=9),
    )
    service = object.__new__(TenantAdminService)
    service.repo = SimpleNamespace(
        query_identity_select=AsyncMock(return_value=([tenant_admin], 1))
    )

    response = await TenantAdminService.get_identity_select_options(
        service,
        search="owner",
        page=1,
        page_size=10,
    )

    assert response.total == 1
    assert response.page == 1
    assert response.page_size == 10
    assert response.has_more is False
    assert len(response.items) == 1

    option = response.items[0]
    assert option.label == "企业所有者"
    assert option.value == 9
    assert option.disabled is True
    assert option.extra == {
        "display_name": "企业所有者",
        "username": "tenant_owner",
        "nickname": "企业所有者",
        "avatar": "avatar-9",
        "org_node_id": 88,
        "org_node_name": "企业组织",
        "role_name": "企业角色",
        "user_type": "tenant_admin",
        "is_active": False,
        "is_leader": True,
        "is_owner": True,
    }


def test_admin_org_member_serialization_includes_role_alignment() -> None:
    now = datetime.now(timezone.utc)
    member = SimpleNamespace(
        id=101,
        username="org_admin",
        nickname="组织成员",
        avatar="avatar-101",
        email="org_admin@example.com",
        is_active=True,
        created_at=now,
        updated_at=now,
        org_node_id=12,
        role_id=5,
        org_node=SimpleNamespace(name="组织节点", leader_id=101),
        role=SimpleNamespace(name="权限角色"),
    )

    serialized = _serialize_member(member)

    assert serialized.role_id == 5
    assert serialized.role_name == "权限角色"
    assert serialized.permission_role_id == 5
    assert serialized.permission_role_name == "权限角色"
    assert serialized.org_node_name == "组织节点"
    assert serialized.is_leader is True
