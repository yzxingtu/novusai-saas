"""
Tenant organization node repository / 企业组织节点仓储
"""

from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload

from app.core.base_repository import TenantRepository
from app.models.org.tenant_org_node import TenantOrgNode, TenantOrgScopePolicy
from app.models.tenant.tenant_admin import TenantAdmin


class TenantOrgNodeRepository(TenantRepository[TenantOrgNode]):
    """Repository for tenant organization nodes / 企业组织节点仓储"""

    model = TenantOrgNode

    _scope_fields = {
        "admin": {
            "id", "tenant_id", "name", "code", "is_system", "is_active",
            "parent_id", "level", "type", "leader_id",
            "created_at", "updated_at",
        },
        "tenant": {
            "id", "name", "code", "is_system", "is_active",
            "parent_id", "level", "type", "leader_id",
            "created_at", "updated_at",
        },
    }

    def _detail_options(self) -> list:
        return [
            selectinload(self.model.children),
            selectinload(self.model.admins),
            selectinload(self.model.users),
            selectinload(self.model.leader),
            selectinload(self.model.scope_policy).selectinload(TenantOrgScopePolicy.targets),
        ]

    async def get_by_code(self, code: str) -> TenantOrgNode | None:
        return await self.get_one_by(code=code)

    async def code_exists(self, code: str, exclude_id: int | None = None) -> bool:
        query = select(self.model.id).where(
            self.model.tenant_id == self.tenant_id,
            self.model.code == code,
            self.model.is_deleted.is_(False),
        )
        if exclude_id:
            query = query.where(self.model.id != exclude_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none() is not None

    async def get_children(
        self,
        parent_id: int | None,
        include_deleted: bool = False,
    ) -> list[TenantOrgNode]:
        query = select(self.model).where(
            self.model.tenant_id == self.tenant_id,
            self.model.parent_id == parent_id if parent_id is not None else self.model.parent_id.is_(None),
        )
        if not include_deleted:
            query = query.where(self.model.is_deleted.is_(False))
        query = query.order_by(self.model.sort_order.asc(), self.model.id.asc())
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_ancestors(
        self,
        org_node_id: int,
        include_deleted: bool = False,
    ) -> list[TenantOrgNode]:
        org_node = await self.get_by_id(org_node_id, include_deleted=include_deleted)
        if not org_node or not org_node.path:
            return []

        parts = [part for part in org_node.path.strip("/").split("/") if part]
        ancestor_ids = [int(part) for part in parts if int(part) != org_node_id]
        if not ancestor_ids:
            return []

        query = select(self.model).where(
            self.model.tenant_id == self.tenant_id,
            self.model.id.in_(ancestor_ids),
        )
        if not include_deleted:
            query = query.where(self.model.is_deleted.is_(False))
        query = query.order_by(self.model.level.asc())
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_descendants(
        self,
        org_node_id: int,
        include_deleted: bool = False,
    ) -> list[TenantOrgNode]:
        org_node = await self.get_by_id(org_node_id, include_deleted=include_deleted)
        if not org_node:
            return []

        path_prefix = org_node.path or f"/{org_node_id}/"
        query = select(self.model).where(
            self.model.tenant_id == self.tenant_id,
            self.model.path.like(f"{path_prefix}%"),
            self.model.id != org_node_id,
        )
        if not include_deleted:
            query = query.where(self.model.is_deleted.is_(False))
        query = query.order_by(self.model.level.asc(), self.model.sort_order.asc(), self.model.id.asc())
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_descendant_ids(
        self,
        org_node_id: int,
        include_deleted: bool = False,
    ) -> list[int]:
        descendants = await self.get_descendants(org_node_id, include_deleted=include_deleted)
        return [item.id for item in descendants]

    async def get_tree(
        self,
        parent_id: int | None = None,
        include_deleted: bool = False,
    ) -> list[TenantOrgNode]:
        if parent_id is None:
            query = select(self.model).where(self.model.tenant_id == self.tenant_id)
        else:
            org_node = await self.get_by_id(parent_id, include_deleted=include_deleted)
            if not org_node:
                return []
            path_prefix = org_node.path or f"/{parent_id}/"
            query = select(self.model).where(
                self.model.tenant_id == self.tenant_id,
                self.model.path.like(f"{path_prefix}%"),
            )

        if not include_deleted:
            query = query.where(self.model.is_deleted.is_(False))
        for option in self._detail_options():
            query = query.options(option)
        query = query.execution_options(populate_existing=True)
        query = query.order_by(self.model.level.asc(), self.model.sort_order.asc(), self.model.id.asc())
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_organization_root_nodes(self, include_deleted: bool = False) -> list[TenantOrgNode]:
        query = select(self.model).where(
            self.model.tenant_id == self.tenant_id,
            self.model.parent_id.is_(None),
        )
        if not include_deleted:
            query = query.where(self.model.is_deleted.is_(False))
        for option in self._detail_options():
            query = query.options(option)
        query = query.execution_options(populate_existing=True)
        query = query.order_by(self.model.sort_order.asc(), self.model.id.asc())
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_children_with_details(
        self,
        parent_id: int,
        include_deleted: bool = False,
    ) -> list[TenantOrgNode]:
        query = select(self.model).where(
            self.model.tenant_id == self.tenant_id,
            self.model.parent_id == parent_id,
        )
        if not include_deleted:
            query = query.where(self.model.is_deleted.is_(False))
        for option in self._detail_options():
            query = query.options(option)
        query = query.execution_options(populate_existing=True)
        query = query.order_by(self.model.sort_order.asc(), self.model.id.asc())
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_members(
        self,
        org_node_id: int,
        search: str | None = None,
        page: int = 1,
        page_size: int = 20,
        include_descendants: bool = True,
        include_deleted: bool = False,
    ) -> tuple[list[TenantAdmin], int]:
        if include_descendants:
            org_node = await self.get_by_id(org_node_id, include_deleted=include_deleted)
            if not org_node:
                return [], 0

            path_prefix = org_node.path or f"/{org_node_id}/"
            org_ids_query = select(self.model.id).where(
                self.model.tenant_id == self.tenant_id,
                or_(
                    self.model.id == org_node_id,
                    self.model.path.like(f"{path_prefix}%"),
                ),
            )
            if not include_deleted:
                org_ids_query = org_ids_query.where(self.model.is_deleted.is_(False))
            org_ids_result = await self.db.execute(org_ids_query)
            org_node_ids = list(org_ids_result.scalars().all())
            if not org_node_ids:
                return [], 0
            base_conditions = [TenantAdmin.org_node_id.in_(org_node_ids)]
        else:
            base_conditions = [TenantAdmin.org_node_id == org_node_id]

        base_conditions.extend(
            [
                TenantAdmin.tenant_id == self.tenant_id,
                TenantAdmin.is_deleted.is_(False) if not include_deleted else True,
            ]
        )
        base_conditions = [condition for condition in base_conditions if condition is not True]

        if search:
            search_pattern = f"%{search}%"
            base_conditions.append(
                or_(
                    TenantAdmin.username.ilike(search_pattern),
                    TenantAdmin.nickname.ilike(search_pattern),
                    TenantAdmin.email.ilike(search_pattern),
                )
            )

        count_query = select(func.count(TenantAdmin.id)).where(*base_conditions)
        count_result = await self.db.execute(count_query)
        total = count_result.scalar() or 0

        query = (
            select(TenantAdmin)
            .where(*base_conditions)
            .options(
                selectinload(TenantAdmin.org_node),
                selectinload(TenantAdmin.role),
            )
            .order_by(TenantAdmin.id.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self.db.execute(query)
        return list(result.scalars().all()), total

    async def get_with_members(
        self,
        org_node_id: int,
        include_deleted: bool = False,
    ) -> TenantOrgNode | None:
        query = select(self.model).where(
            self.model.tenant_id == self.tenant_id,
            self.model.id == org_node_id,
        )
        if not include_deleted:
            query = query.where(self.model.is_deleted.is_(False))
        for option in self._detail_options():
            query = query.options(option)
        query = query.execution_options(populate_existing=True)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()


__all__ = ["TenantOrgNodeRepository"]
