from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.admin import tenant_users as admin_tenant_users_module
from app.api.admin.organization import _serialize_member
from app.api.admin.tenant_admins import router as admin_tenant_admins_router
from app.api.admin.tenant_users import router as admin_tenant_users_router
from app.api.admin.users import router as admin_users_router
from app.api.common.identity import (
    serialize_admin_identity_detail,
    serialize_tenant_admin_identity_detail,
    serialize_tenant_user_identity_detail,
)
from app.api.tenant.admins import router as tenant_admins_router
from app.api.tenant.users import router as tenant_users_router
from app.core.deps import get_current_active_admin, get_db
from app.core.identity import resolve_identity_display_role_name
from app.services.system.admin_service import AdminService
from app.services.tenant.tenant_admin_service import TenantAdminService


def test_admin_identity_select_routes_registered() -> None:
    paths = {route.path for route in admin_users_router.routes}
    assert "/users/select" in paths

    tenant_paths = {route.path for route in admin_tenant_admins_router.routes}
    assert "/tenants/{tenant_id}/admins/select" in tenant_paths

    admin_tenant_user_paths = {route.path for route in admin_tenant_users_router.routes}
    assert "/tenants/{tenant_id}/users/select" in admin_tenant_user_paths


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
        "display_name": "平台管理员",
        "username": "platform_admin",
        "nickname": "平台管理员",
        "avatar": "avatar-1",
        "org_node_id": 7,
        "org_node_name": "平台组织",
        "role_name": "平台角色",
        "display_role_name": "平台角色",
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
        "display_role_name": "企业角色",
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


def test_identity_detail_routes_registered() -> None:
    admin_paths = {route.path for route in admin_users_router.routes}
    assert "/users/{user_id}" in admin_paths

    tenant_paths = {route.path for route in admin_tenant_admins_router.routes}
    assert "/tenants/{tenant_id}/admins/{admin_id}" in tenant_paths

    admin_tenant_user_paths = {route.path for route in admin_tenant_users_router.routes}
    assert "/tenants/{tenant_id}/users/{user_id}" in admin_tenant_user_paths

    tenant_admin_paths = {route.path for route in tenant_admins_router.routes}
    assert "/admins/{admin_id}" in tenant_admin_paths

    tenant_user_paths = {route.path for route in tenant_users_router.routes}
    assert "/users/{user_id}" in tenant_user_paths


def test_admin_tenant_user_detail_exposes_activity_to_platform_admin(
    monkeypatch,
) -> None:
    user = SimpleNamespace(
        id=9,
        username="tenant_user",
        last_login_at="2026-05-15T03:54:44+00:00",
    )
    tenant_user_service = SimpleNamespace(
        get_identity_detail=AsyncMock(return_value=user),
    )

    monkeypatch.setattr(
        admin_tenant_users_module,
        "TenantUserService",
        lambda _db, _tenant_id: tenant_user_service,
    )
    monkeypatch.setattr(
        admin_tenant_users_module,
        "serialize_tenant_user_identity_detail",
        lambda payload_user, **kwargs: {
            "id": payload_user.id,
            "can_view_activity": kwargs["can_view_activity"],
            "last_login_at": payload_user.last_login_at,
        },
    )

    app = FastAPI()
    app.include_router(admin_tenant_users_module.router)

    async def override_db():
        yield SimpleNamespace()

    async def override_admin():
        return SimpleNamespace(id=1, username="platform_admin", is_active=True)

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_active_admin] = override_admin

    with TestClient(app) as client:
        response = client.get("/tenants/5/users/9")

    assert response.status_code == 200
    assert response.json()["data"] == {
        "id": 9,
        "can_view_activity": True,
        "last_login_at": "2026-05-15T03:54:44+00:00",
    }


def test_identity_detail_helpers_include_expected_flags() -> None:
    now = datetime.now(timezone.utc)

    admin = SimpleNamespace(
        id=1,
        username="platform_admin",
        nickname="平台管理员",
        avatar="avatar-1",
        email="admin@example.com",
        phone="123",
        is_active=True,
        org_node=SimpleNamespace(id=10, name="平台组织", leader_id=1),
        role=SimpleNamespace(id=5, name="平台角色"),
        created_at=now,
        updated_at=now,
        last_login_at=now,
        last_login_ip="127.0.0.1",
    )
    admin_detail = serialize_admin_identity_detail(admin)
    assert admin_detail["display_name"] == "平台管理员"
    assert admin_detail["user_type"] == "admin"
    assert admin_detail["is_leader"] is True
    assert admin_detail["can_view_activity"] is True
    assert admin_detail["org_node_name"] == "平台组织"
    assert admin_detail["display_role_name"] == "平台角色"

    tenant_admin = SimpleNamespace(
        id=2,
        username="tenant_admin",
        nickname="企业管理员",
        avatar="avatar-2",
        email="ta@example.com",
        phone="456",
        tenant_id=99,
        is_active=False,
        is_owner=True,
        org_node=SimpleNamespace(id=20, name="企业组织", leader_id=2),
        role=SimpleNamespace(id=8, name="企业角色"),
        created_at=now,
        updated_at=now,
        last_login_at=now,
        last_login_ip="10.0.0.1",
    )
    tenant_admin_detail = serialize_tenant_admin_identity_detail(tenant_admin)
    assert tenant_admin_detail["display_name"] == "企业管理员"
    assert tenant_admin_detail["user_type"] == "tenant_admin"
    assert tenant_admin_detail["is_owner"] is True
    assert tenant_admin_detail["tenant_id"] == 99
    assert tenant_admin_detail["can_view_activity"] is True
    assert tenant_admin_detail["display_role_name"] == "企业角色"

    tenant_user = SimpleNamespace(
        id=3,
        username="tenant_user",
        nickname="企业用户",
        avatar="avatar-3",
        email="tu@example.com",
        phone="789",
        tenant_id=100,
        is_active=True,
        approval_status="approved",
        org_node=SimpleNamespace(id=30, name="业务部门"),
        role=SimpleNamespace(id=11, name="业务角色"),
        created_at=now,
        updated_at=now,
        last_login_at=now,
        last_login_ip="192.168.0.1",
        gender=1,
    )
    tenant_user_detail = serialize_tenant_user_identity_detail(tenant_user)
    assert tenant_user_detail["display_name"] == "企业用户"
    assert tenant_user_detail["user_type"] == "tenant_user"
    assert tenant_user_detail["tenant_id"] == 100
    assert tenant_user_detail["approval_status"] == "approved"
    assert tenant_user_detail["can_view_activity"] is True
    assert tenant_user_detail["display_role_name"] == "业务角色"


def test_identity_detail_helpers_suppress_activity_fields_when_unauthorized() -> None:
    now = datetime.now(timezone.utc)
    admin = SimpleNamespace(
        id=12,
        username="activity_admin",
        nickname="活动管理员",
        avatar=None,
        email="activity_admin@example.com",
        phone=None,
        is_active=True,
        org_node=SimpleNamespace(id=18, name="平台管理组", leader_id=99),
        role=None,
        created_at=now,
        updated_at=now,
        last_login_at=now,
        last_login_ip="127.0.0.1",
    )

    admin_detail = serialize_admin_identity_detail(admin, can_view_activity=False)

    assert admin_detail["can_view_activity"] is False
    assert admin_detail["created_at"] is None
    assert admin_detail["updated_at"] is None
    assert admin_detail["last_login_at"] is None
    assert admin_detail["last_login_ip"] is None


def test_identity_role_presentation_suppresses_architecture_duplicates() -> None:
    assert resolve_identity_display_role_name("平台管理组", "平台管理组") is None
    assert resolve_identity_display_role_name(" 平台管理组 ", "平台管理组") is None
    assert (
        resolve_identity_display_role_name("平台审核角色", "平台管理组")
        == "平台审核角色"
    )


@pytest.mark.asyncio
async def test_admin_identity_select_suppresses_redundant_role_in_extra() -> None:
    admin = SimpleNamespace(
        id=77,
        username="dup_role_admin",
        nickname="重复角色管理员",
        avatar=None,
        org_node_id=17,
        is_active=True,
        is_super=False,
        role=SimpleNamespace(name="平台管理组"),
        org_node=SimpleNamespace(name="平台管理组", leader_id=None),
    )
    service = object.__new__(AdminService)
    service.repo = SimpleNamespace(
        query_identity_select=AsyncMock(return_value=([admin], 1))
    )

    response = await AdminService.get_identity_select_options(
        service,
        search="dup",
        page=1,
        page_size=20,
    )

    assert response.items[0].extra["role_name"] == "平台管理组"
    assert response.items[0].extra["display_role_name"] is None


def test_identity_detail_helpers_suppress_redundant_role_display_name() -> None:
    now = datetime.now(timezone.utc)
    admin = SimpleNamespace(
        id=11,
        username="arch_admin",
        nickname="架构管理员",
        avatar=None,
        email="arch_admin@example.com",
        phone=None,
        is_active=True,
        org_node=SimpleNamespace(id=18, name="平台管理组", leader_id=11),
        role=SimpleNamespace(id=19, name="平台管理组"),
        created_at=now,
        updated_at=now,
        last_login_at=now,
        last_login_ip="127.0.0.1",
    )

    admin_detail = serialize_admin_identity_detail(admin)

    assert admin_detail["role_name"] == "平台管理组"
    assert admin_detail["display_role_name"] is None
