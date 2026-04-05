from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest


@pytest.mark.asyncio
async def test_tenant_admin_identity_select_options_include_unified_extra_fields(
    mock_db,
):
    from app.services.tenant.tenant_admin_service import TenantAdminService

    service = TenantAdminService.__new__(TenantAdminService)
    service.db = mock_db
    service.tenant_id = 9
    service.repo = AsyncMock()
    service.repo.query_identity_select = AsyncMock(
        return_value=(
            [
                SimpleNamespace(
                    id=12,
                    username="alice",
                    nickname="Alice",
                    avatar="22",
                    org_node_id=5,
                    org_node=SimpleNamespace(name="Ops", leader_id=12),
                    role=SimpleNamespace(name="Owner"),
                    is_active=True,
                    is_owner=True,
                )
            ],
            1,
        )
    )

    response = await service.get_identity_select_options(
        search="ali",
        page=1,
        page_size=20,
    )

    assert response.total == 1
    assert response.items[0].label == "Alice"
    assert response.items[0].value == 12
    assert response.items[0].disabled is False
    assert response.items[0].extra == {
        "display_name": "Alice",
        "username": "alice",
        "nickname": "Alice",
        "avatar": "22",
        "org_node_id": 5,
        "org_node_name": "Ops",
        "role_name": "Owner",
        "user_type": "tenant_admin",
        "is_active": True,
        "is_leader": True,
        "is_owner": True,
    }


@pytest.mark.asyncio
async def test_tenant_user_identity_select_options_include_unified_extra_fields(
    mock_db,
):
    from app.services.tenant.tenant_user_service import TenantUserService

    service = TenantUserService.__new__(TenantUserService)
    service.db = mock_db
    service.tenant_id = 9
    service.repo = AsyncMock()
    service.repo.query_identity_select = AsyncMock(
        return_value=(
            [
                SimpleNamespace(
                    id=21,
                    username="bob",
                    email="bob@example.com",
                    phone=None,
                    nickname="Bob",
                    avatar="33",
                    org_node_id=7,
                    org_node=SimpleNamespace(name="Sales"),
                    role=SimpleNamespace(name="Member"),
                    is_active=False,
                )
            ],
            1,
        )
    )

    response = await service.get_identity_select_options(
        search="bob",
        page=2,
        page_size=10,
    )

    assert response.total == 1
    assert response.page == 2
    assert response.page_size == 10
    assert response.has_more is False
    assert response.items[0].label == "Bob"
    assert response.items[0].value == 21
    assert response.items[0].disabled is True
    assert response.items[0].extra == {
        "display_name": "Bob",
        "username": "bob",
        "nickname": "Bob",
        "avatar": "33",
        "org_node_id": 7,
        "org_node_name": "Sales",
        "role_name": "Member",
        "user_type": "tenant_user",
        "is_active": False,
        "is_leader": False,
        "is_owner": False,
    }
