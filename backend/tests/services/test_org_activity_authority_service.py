from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.services.system.admin_org_authority_service import AdminOrgAuthorityService
from app.services.tenant.tenant_org_authority_service import TenantOrgAuthorityService


class _ScalarResult:
    def __init__(self, values: list[int]) -> None:
        self._values = values

    def all(self) -> list[int]:
        return self._values


class _ExecuteResult:
    def __init__(self, values: list[int]) -> None:
        self._values = values

    def scalars(self) -> _ScalarResult:
        return _ScalarResult(self._values)


class _LeaderNodeDb:
    def __init__(self, leader_node_ids: list[int]) -> None:
        self._leader_node_ids = leader_node_ids

    async def execute(self, _query):
        return _ExecuteResult(self._leader_node_ids)


@pytest.mark.asyncio
async def test_platform_activity_visibility_is_leader_subtree_not_sibling_scope() -> None:
    descendants = {10: [20, 30]}
    leader = SimpleNamespace(id=1, is_super=True)
    sibling_b = SimpleNamespace(id=2, is_super=False)
    sibling_c = SimpleNamespace(id=3, is_super=False)

    leader_authority = AdminOrgAuthorityService(_LeaderNodeDb([10]), leader)
    leader_authority.repo.get_descendant_ids = AsyncMock(
        side_effect=lambda node_id: descendants.get(node_id, [])
    )
    sibling_b_authority = AdminOrgAuthorityService(_LeaderNodeDb([]), sibling_b)
    sibling_b_authority.repo.get_descendant_ids = AsyncMock()
    sibling_c_authority = AdminOrgAuthorityService(_LeaderNodeDb([]), sibling_c)
    sibling_c_authority.repo.get_descendant_ids = AsyncMock()

    assert await leader_authority.can_view_member_activity_for_node(20) is True
    assert await leader_authority.can_view_member_activity_for_node(30) is True
    assert await sibling_b_authority.can_view_member_activity_for_node(30) is False
    assert await sibling_c_authority.can_view_member_activity_for_node(20) is False


@pytest.mark.asyncio
async def test_tenant_activity_visibility_is_leader_subtree_not_sibling_scope() -> None:
    descendants = {10: [20, 30]}
    leader = SimpleNamespace(id=1, tenant_id=5, is_owner=True)
    sibling_b = SimpleNamespace(id=2, tenant_id=5, is_owner=False)
    sibling_c = SimpleNamespace(id=3, tenant_id=5, is_owner=False)

    leader_authority = TenantOrgAuthorityService(_LeaderNodeDb([10]), leader)
    leader_authority.repo.get_descendant_ids = AsyncMock(
        side_effect=lambda node_id: descendants.get(node_id, [])
    )
    sibling_b_authority = TenantOrgAuthorityService(_LeaderNodeDb([]), sibling_b)
    sibling_b_authority.repo.get_descendant_ids = AsyncMock()
    sibling_c_authority = TenantOrgAuthorityService(_LeaderNodeDb([]), sibling_c)
    sibling_c_authority.repo.get_descendant_ids = AsyncMock()

    assert await leader_authority.can_view_member_activity_for_node(20) is True
    assert await leader_authority.can_view_member_activity_for_node(30) is True
    assert await sibling_b_authority.can_view_member_activity_for_node(30) is False
    assert await sibling_c_authority.can_view_member_activity_for_node(20) is False
