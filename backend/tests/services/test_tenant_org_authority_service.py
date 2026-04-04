from types import SimpleNamespace

import pytest

from app.services.tenant.tenant_org_authority_service import TenantOrgAuthorityService


class _RepoStub:
    def __init__(self, node_map: dict[int, SimpleNamespace], ancestor_map: dict[int, list]):
        self.model = SimpleNamespace(id="id")
        self._node_map = node_map
        self._ancestor_map = ancestor_map

    async def get_by_id(self, org_node_id: int):
        return self._node_map.get(org_node_id)

    async def get_ancestors(self, org_node_id: int):
        return self._ancestor_map.get(org_node_id, [])


@pytest.mark.asyncio
async def test_can_assign_permissions_when_admin_is_current_node_leader():
    admin = SimpleNamespace(id=7, tenant_id=1, org_node_id=None, is_owner=False)
    service = TenantOrgAuthorityService(db=None, admin=admin)
    service.repo = _RepoStub(
        node_map={10: SimpleNamespace(id=10, leader_id=7, is_deleted=False)},
        ancestor_map={10: []},
    )

    assert await service.can_assign_permissions_for_node(10) is True


@pytest.mark.asyncio
async def test_can_assign_permissions_when_admin_is_ancestor_node_leader():
    admin = SimpleNamespace(id=7, tenant_id=1, org_node_id=None, is_owner=False)
    service = TenantOrgAuthorityService(db=None, admin=admin)
    service.repo = _RepoStub(
        node_map={10: SimpleNamespace(id=10, leader_id=9, is_deleted=False)},
        ancestor_map={
            10: [
                SimpleNamespace(id=2, leader_id=7, is_deleted=False),
                SimpleNamespace(id=1, leader_id=3, is_deleted=False),
            ]
        },
    )

    assert await service.can_assign_permissions_for_node(10) is True


@pytest.mark.asyncio
async def test_cannot_assign_permissions_when_admin_is_not_any_relevant_leader():
    admin = SimpleNamespace(id=7, tenant_id=1, org_node_id=None, is_owner=False)
    service = TenantOrgAuthorityService(db=None, admin=admin)
    service.repo = _RepoStub(
        node_map={10: SimpleNamespace(id=10, leader_id=9, is_deleted=False)},
        ancestor_map={
            10: [
                SimpleNamespace(id=2, leader_id=8, is_deleted=False),
                SimpleNamespace(id=1, leader_id=3, is_deleted=False),
            ]
        },
    )

    assert await service.can_assign_permissions_for_node(10) is False


@pytest.mark.asyncio
async def test_owner_can_assign_permissions_for_root_creation():
    admin = SimpleNamespace(id=1, tenant_id=1, org_node_id=None, is_owner=True)
    service = TenantOrgAuthorityService(db=None, admin=admin)
    service.repo = _RepoStub(node_map={}, ancestor_map={})

    assert await service.can_assign_permissions_for_node(None) is True


@pytest.mark.asyncio
async def test_owner_can_assign_permissions_for_root_node_without_leader():
    admin = SimpleNamespace(id=1, tenant_id=1, org_node_id=None, is_owner=True)
    service = TenantOrgAuthorityService(db=None, admin=admin)
    service.repo = _RepoStub(
        node_map={10: SimpleNamespace(id=10, leader_id=None, is_deleted=False)},
        ancestor_map={10: []},
    )

    assert await service.can_assign_permissions_for_node(10) is True
