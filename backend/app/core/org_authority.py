"""
Organization authority resolver / 组织权限解析器
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums.role import DataScope
from app.models.org import AdminOrgNode, TenantOrgNode
from app.models.system.admin import Admin
from app.models.tenant.tenant_admin import TenantAdmin
from app.models.tenant.tenant_user import TenantUser


@dataclass
class OrgAuthorityResult:
    scope_mode: str = DataScope.SELF_ONLY.value
    visible_org_ids: list[int] = field(default_factory=list)
    manageable_org_ids: list[int] = field(default_factory=list)
    scope_root_ids: list[int] = field(default_factory=list)
    effective_scope_org_ids: list[int] = field(default_factory=list)
    primary_org_id: int | None = None
    custom_org_ids: list[int] = field(default_factory=list)


class OrgAuthorityResolver:
    """Resolve organization visibility and data scope / 解析组织可见性与数据范围"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def resolve_admin(self, admin: Admin) -> OrgAuthorityResult:
        if admin.is_super:
            all_ids = await self._load_all_admin_org_ids()
            return OrgAuthorityResult(
                scope_mode=DataScope.ALL.value,
                visible_org_ids=all_ids,
                manageable_org_ids=all_ids,
                scope_root_ids=[],
                effective_scope_org_ids=all_ids,
                primary_org_id=admin.org_node_id,
            )

        visible_roots = await self._resolve_admin_root_ids(admin)
        scope_roots = await self._resolve_admin_scope_root_ids(admin)
        return await self._build_admin_result(visible_roots, scope_roots)

    async def resolve_tenant_admin(self, admin: TenantAdmin) -> OrgAuthorityResult:
        if admin.is_owner:
            all_ids = await self._load_all_tenant_org_ids(admin.tenant_id)
            return OrgAuthorityResult(
                scope_mode=DataScope.ALL.value,
                visible_org_ids=all_ids,
                manageable_org_ids=all_ids,
                scope_root_ids=[],
                effective_scope_org_ids=all_ids,
                primary_org_id=admin.org_node_id,
            )

        visible_roots = await self._resolve_tenant_admin_root_ids(admin)
        scope_roots = await self._resolve_tenant_admin_scope_root_ids(admin)
        return await self._build_tenant_result(admin.tenant_id, visible_roots, scope_roots)

    async def resolve_tenant_user(self, user: TenantUser) -> OrgAuthorityResult:
        return OrgAuthorityResult(
            scope_mode=DataScope.SELF_ONLY.value,
            visible_org_ids=[user.org_node_id] if user.org_node_id else [],
            manageable_org_ids=[],
            scope_root_ids=[],
            effective_scope_org_ids=[],
            primary_org_id=user.org_node_id,
        )

    async def _resolve_admin_root_ids(self, admin: Admin) -> list[int]:
        root_ids: list[int] = []
        if admin.org_node_id:
            root_ids.append(admin.org_node_id)

        leader_ids = await self.db.execute(
            select(AdminOrgNode.id).where(
                AdminOrgNode.leader_id == admin.id,
                AdminOrgNode.is_deleted.is_(False),
            )
        )
        root_ids.extend(list(leader_ids.scalars().all()))
        return list(dict.fromkeys(root_ids))

    async def _resolve_admin_scope_root_ids(self, admin: Admin) -> list[int]:
        leader_ids = await self.db.execute(
            select(AdminOrgNode.id).where(
                AdminOrgNode.leader_id == admin.id,
                AdminOrgNode.is_deleted.is_(False),
            )
        )
        ids = list(leader_ids.scalars().all())
        if ids:
            return list(dict.fromkeys(ids))
        return [admin.org_node_id] if admin.org_node_id else []

    async def _resolve_tenant_admin_root_ids(self, admin: TenantAdmin) -> list[int]:
        root_ids: list[int] = []
        if admin.org_node_id:
            root_ids.append(admin.org_node_id)

        leader_ids = await self.db.execute(
            select(TenantOrgNode.id).where(
                TenantOrgNode.tenant_id == admin.tenant_id,
                TenantOrgNode.leader_id == admin.id,
                TenantOrgNode.is_deleted.is_(False),
            )
        )
        root_ids.extend(list(leader_ids.scalars().all()))
        return list(dict.fromkeys(root_ids))

    async def _resolve_tenant_admin_scope_root_ids(self, admin: TenantAdmin) -> list[int]:
        leader_ids = await self.db.execute(
            select(TenantOrgNode.id).where(
                TenantOrgNode.tenant_id == admin.tenant_id,
                TenantOrgNode.leader_id == admin.id,
                TenantOrgNode.is_deleted.is_(False),
            )
        )
        ids = list(leader_ids.scalars().all())
        if ids:
            return list(dict.fromkeys(ids))
        return [admin.org_node_id] if admin.org_node_id else []

    async def _build_admin_result(
        self,
        visible_roots: list[int],
        scope_roots: list[int],
    ) -> OrgAuthorityResult:
        visible_ids = await self._collect_admin_subtree_ids(visible_roots)
        scope_mode, effective_scope_org_ids, custom_org_ids = await self._resolve_admin_scope(scope_roots)
        primary_org_id = scope_roots[0] if scope_roots else (visible_roots[0] if visible_roots else None)
        return OrgAuthorityResult(
            scope_mode=scope_mode,
            visible_org_ids=visible_ids,
            manageable_org_ids=visible_ids,
            scope_root_ids=scope_roots,
            effective_scope_org_ids=effective_scope_org_ids,
            primary_org_id=primary_org_id,
            custom_org_ids=custom_org_ids,
        )

    async def _build_tenant_result(
        self,
        tenant_id: int,
        visible_roots: list[int],
        scope_roots: list[int],
    ) -> OrgAuthorityResult:
        visible_ids = await self._collect_tenant_subtree_ids(tenant_id, visible_roots)
        scope_mode, effective_scope_org_ids, custom_org_ids = await self._resolve_tenant_scope(
            tenant_id,
            scope_roots,
        )
        primary_org_id = scope_roots[0] if scope_roots else (visible_roots[0] if visible_roots else None)
        return OrgAuthorityResult(
            scope_mode=scope_mode,
            visible_org_ids=visible_ids,
            manageable_org_ids=visible_ids,
            scope_root_ids=scope_roots,
            effective_scope_org_ids=effective_scope_org_ids,
            primary_org_id=primary_org_id,
            custom_org_ids=custom_org_ids,
        )

    async def _resolve_admin_scope(
        self,
        scope_roots: list[int],
    ) -> tuple[str, list[int], list[int]]:
        if not scope_roots:
            return (DataScope.SELF_ONLY.value, [], [])

        mode_set: set[str] = set()
        effective_ids: list[int] = []

        for node_id in scope_roots:
            node = await self.db.get(AdminOrgNode, node_id)
            if node is None or node.is_deleted:
                continue
            mode, ids = await self._resolve_admin_node_scope(node)
            if mode == DataScope.ALL.value:
                all_ids = await self._load_all_admin_org_ids()
                return (DataScope.ALL.value, all_ids, [])
            mode_set.add(mode)
            effective_ids.extend(ids)

        deduped = list(dict.fromkeys(effective_ids))
        if not deduped:
            return (DataScope.SELF_ONLY.value, [], [])
        final_mode = self._merge_scope_modes(mode_set)
        custom_ids = deduped if final_mode == DataScope.CUSTOM.value else []
        return (final_mode, deduped, custom_ids)

    async def _resolve_tenant_scope(
        self,
        tenant_id: int,
        scope_roots: list[int],
    ) -> tuple[str, list[int], list[int]]:
        if not scope_roots:
            return (DataScope.SELF_ONLY.value, [], [])

        mode_set: set[str] = set()
        effective_ids: list[int] = []

        for node_id in scope_roots:
            node = await self.db.get(TenantOrgNode, node_id)
            if node is None or node.is_deleted or node.tenant_id != tenant_id:
                continue
            mode, ids = await self._resolve_tenant_node_scope(node)
            if mode == DataScope.ALL.value:
                all_ids = await self._load_all_tenant_org_ids(tenant_id)
                return (DataScope.ALL.value, all_ids, [])
            mode_set.add(mode)
            effective_ids.extend(ids)

        deduped = list(dict.fromkeys(effective_ids))
        if not deduped:
            return (DataScope.SELF_ONLY.value, [], [])
        final_mode = self._merge_scope_modes(mode_set)
        custom_ids = deduped if final_mode == DataScope.CUSTOM.value else []
        return (final_mode, deduped, custom_ids)

    async def _resolve_admin_node_scope(
        self,
        node: AdminOrgNode,
    ) -> tuple[str, list[int]]:
        mode = node.scope_mode
        if mode == DataScope.ALL.value:
            return (DataScope.ALL.value, [])
        if mode == DataScope.SELF_ONLY.value:
            return (DataScope.SELF_ONLY.value, [])
        if mode == DataScope.DEPT_ONLY.value:
            return (DataScope.DEPT_ONLY.value, [node.id])
        if mode == DataScope.CUSTOM.value:
            return (DataScope.CUSTOM.value, node.custom_org_node_ids)
        subtree_ids = await self._collect_admin_subtree_ids([node.id])
        return (DataScope.DEPT_AND_CHILDREN.value, subtree_ids)

    async def _resolve_tenant_node_scope(
        self,
        node: TenantOrgNode,
    ) -> tuple[str, list[int]]:
        mode = node.scope_mode
        if mode == DataScope.ALL.value:
            return (DataScope.ALL.value, [])
        if mode == DataScope.SELF_ONLY.value:
            return (DataScope.SELF_ONLY.value, [])
        if mode == DataScope.DEPT_ONLY.value:
            return (DataScope.DEPT_ONLY.value, [node.id])
        if mode == DataScope.CUSTOM.value:
            return (DataScope.CUSTOM.value, node.custom_org_node_ids)
        subtree_ids = await self._collect_tenant_subtree_ids(node.tenant_id, [node.id])
        return (DataScope.DEPT_AND_CHILDREN.value, subtree_ids)

    async def _collect_admin_subtree_ids(self, root_ids: list[int]) -> list[int]:
        if not root_ids:
            return []
        collected: list[int] = []
        for root_id in root_ids:
            node = await self.db.get(AdminOrgNode, root_id)
            if node is None or node.is_deleted:
                continue
            path_prefix = node.path or f"/{node.id}/"
            result = await self.db.execute(
                select(AdminOrgNode.id).where(
                    AdminOrgNode.is_deleted.is_(False),
                    AdminOrgNode.path.startswith(path_prefix),
                )
            )
            collected.extend(list(result.scalars().all()))
        return list(dict.fromkeys(collected))

    async def _collect_tenant_subtree_ids(
        self,
        tenant_id: int,
        root_ids: list[int],
    ) -> list[int]:
        if not root_ids:
            return []
        collected: list[int] = []
        for root_id in root_ids:
            node = await self.db.get(TenantOrgNode, root_id)
            if node is None or node.is_deleted or node.tenant_id != tenant_id:
                continue
            path_prefix = node.path or f"/{node.id}/"
            result = await self.db.execute(
                select(TenantOrgNode.id).where(
                    TenantOrgNode.tenant_id == tenant_id,
                    TenantOrgNode.is_deleted.is_(False),
                    TenantOrgNode.path.startswith(path_prefix),
                )
            )
            collected.extend(list(result.scalars().all()))
        return list(dict.fromkeys(collected))

    async def _load_all_admin_org_ids(self) -> list[int]:
        result = await self.db.execute(
            select(AdminOrgNode.id).where(AdminOrgNode.is_deleted.is_(False))
        )
        return list(result.scalars().all())

    async def _load_all_tenant_org_ids(self, tenant_id: int) -> list[int]:
        result = await self.db.execute(
            select(TenantOrgNode.id).where(
                TenantOrgNode.tenant_id == tenant_id,
                TenantOrgNode.is_deleted.is_(False),
            )
        )
        return list(result.scalars().all())

    @staticmethod
    def _merge_scope_modes(modes: set[str]) -> str:
        if not modes:
            return DataScope.SELF_ONLY.value
        if len(modes) == 1:
            return next(iter(modes))
        return DataScope.CUSTOM.value


__all__ = ["OrgAuthorityResolver", "OrgAuthorityResult"]
