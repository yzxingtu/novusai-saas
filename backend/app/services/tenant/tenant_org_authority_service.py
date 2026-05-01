"""
Tenant organization authority service / 企业组织节点权限范围服务
"""

from __future__ import annotations

from sqlalchemy import select

from app.models.tenant.tenant_admin import TenantAdmin
from app.repositories.tenant.tenant_org_node_repository import TenantOrgNodeRepository


class TenantOrgAuthorityService:
    """Resolve tenant admin org-node visibility/manageability / 解析企业管理员组织节点可见与可管理范围"""

    def __init__(self, db, admin: TenantAdmin):
        self.db = db
        self.admin = admin
        self.repo = TenantOrgNodeRepository(db, admin.tenant_id)
        self._visible_ids: set[int] | None = None
        self._manageable_ids: set[int] | None = None
        self._member_ai_manageable_ids: set[int] | None = None

    async def get_visible_org_node_ids(self) -> set[int]:
        if self._visible_ids is None:
            self._visible_ids = await self._load_scope_ids(include_own=True)
        return self._visible_ids

    async def get_manageable_org_node_ids(self) -> set[int]:
        if self._manageable_ids is None:
            self._manageable_ids = await self._load_scope_ids(include_own=True)
        return self._manageable_ids

    async def can_view_org_node(self, org_node_id: int) -> bool:
        return org_node_id in await self.get_visible_org_node_ids()

    async def can_manage_org_node(self, org_node_id: int) -> bool:
        return org_node_id in await self.get_manageable_org_node_ids()

    async def can_manage_member_ai_for_node(self, org_node_id: int | None) -> bool:
        """Only node or ancestor leaders can manage member AI switches."""
        if org_node_id is None:
            return False
        return org_node_id in await self.get_member_ai_manageable_org_node_ids()

    async def get_member_ai_manageable_org_node_ids(self) -> set[int]:
        """Return tenant nodes whose member AI switches are owned by this admin."""
        if self._member_ai_manageable_ids is not None:
            return self._member_ai_manageable_ids

        leader_result = await self.db.execute(
            select(self.repo.model.id).where(
                self.repo.model.tenant_id == self.admin.tenant_id,
                self.repo.model.leader_id == self.admin.id,
                self.repo.model.is_deleted.is_(False),
            )
        )
        leader_node_ids = set(leader_result.scalars().all())
        scope_ids: set[int] = set(leader_node_ids)
        for leader_node_id in leader_node_ids:
            scope_ids.update(await self.repo.get_descendant_ids(leader_node_id))
        self._member_ai_manageable_ids = scope_ids
        return scope_ids

    async def can_assign_permissions_for_node(self, org_node_id: int | None) -> bool:
        if self.admin.is_owner:
            return True

        if org_node_id is None:
            return False

        org_node = await self.repo.get_by_id(org_node_id)
        if org_node is None or org_node.is_deleted:
            return False

        if org_node.leader_id == self.admin.id:
            return True

        ancestors = await self.repo.get_ancestors(org_node_id)
        return any(ancestor.leader_id == self.admin.id for ancestor in ancestors)

    async def can_create_under_parent(self, parent_id: int | None) -> bool:
        if self.admin.is_owner:
            return True
        if parent_id is None:
            return False
        return parent_id in await self.get_manageable_org_node_ids()

    async def _load_scope_ids(self, include_own: bool) -> set[int]:
        if self.admin.is_owner:
            result = await self.db.execute(
                select(self.repo.model.id).where(
                    self.repo.model.tenant_id == self.admin.tenant_id,
                    self.repo.model.is_deleted.is_(False),
                )
            )
            return set(result.scalars().all())

        scope_ids: set[int] = set()
        own_org_node_id = self.admin.org_node_id
        if own_org_node_id is not None:
            if include_own:
                scope_ids.add(own_org_node_id)
            scope_ids.update(await self.repo.get_descendant_ids(own_org_node_id))

        leader_result = await self.db.execute(
            select(self.repo.model.id).where(
                self.repo.model.tenant_id == self.admin.tenant_id,
                self.repo.model.leader_id == self.admin.id,
                self.repo.model.is_deleted.is_(False),
            )
        )
        leader_node_ids = set(leader_result.scalars().all())
        scope_ids.update(leader_node_ids)
        for leader_node_id in leader_node_ids:
            scope_ids.update(await self.repo.get_descendant_ids(leader_node_id))

        return scope_ids


__all__ = ["TenantOrgAuthorityService"]
