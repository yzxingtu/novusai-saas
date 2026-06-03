"""
Tenant admin permission role repository / 企业管理员权限角色仓储
"""

from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload

from app.core.base_repository import TenantRepository
from app.enums.role import RoleType
from app.models.auth.tenant_admin_role import TenantAdminRole


class TenantPermissionRoleRepository(TenantRepository[TenantAdminRole]):
    """Tenant admin permission role repository / 企业管理员权限角色仓储"""

    model = TenantAdminRole

    _scope_fields = {
        "tenant": {
            "id",
            "name",
            "code",
            "is_system",
            "is_active",
            "sort_order",
            "created_at",
            "updated_at",
        },
    }

    def _base_query(self):
        return (
            select(self.model)
            .options(selectinload(self.model.permissions))
            .where(
                self.model.tenant_id == self.tenant_id,
                self.model.type == RoleType.ROLE.value,
                self.model.parent_id.is_(None),
                self.model.path.is_(None),
                self.model.leader_id.is_(None),
                self.model.level == 1,
            )
        )

    async def get_by_id(
        self,
        id: int,
        include_deleted: bool = False,
    ) -> TenantAdminRole | None:
        query = self._base_query().where(self.model.id == id)
        if not include_deleted:
            query = query.where(self.model.is_deleted.is_(False))
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_by_code(self, code: str) -> TenantAdminRole | None:
        query = self._base_query().where(
            self.model.code == code,
            self.model.is_deleted.is_(False),
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def code_exists(
        self,
        code: str,
        exclude_id: int | None = None,
    ) -> bool:
        query = select(self.model.id).where(
            self.model.tenant_id == self.tenant_id,
            self.model.type == RoleType.ROLE.value,
            self.model.parent_id.is_(None),
            self.model.path.is_(None),
            self.model.leader_id.is_(None),
            self.model.level == 1,
            self.model.code == code,
            self.model.is_deleted.is_(False),
        )
        if exclude_id:
            query = query.where(self.model.id != exclude_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none() is not None

    async def name_exists(
        self,
        name: str,
        exclude_id: int | None = None,
    ) -> bool:
        query = select(self.model.id).where(
            self.model.tenant_id == self.tenant_id,
            self.model.type == RoleType.ROLE.value,
            self.model.parent_id.is_(None),
            self.model.path.is_(None),
            self.model.leader_id.is_(None),
            self.model.level == 1,
            self.model.name == name,
            self.model.is_deleted.is_(False),
        )
        if exclude_id:
            query = query.where(self.model.id != exclude_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none() is not None

    async def create(self, data: dict) -> TenantAdminRole:
        data["type"] = RoleType.ROLE.value
        data["parent_id"] = None
        data["path"] = None
        data["leader_id"] = None
        data["level"] = 1
        return await super().create(data)

    async def get_page(
        self,
        search: str | None = None,
        page: int = 1,
        page_size: int = 20,
        include_deleted: bool = False,
    ) -> tuple[list[TenantAdminRole], int]:
        query = self._base_query()
        count_query = (
            select(func.count())
            .select_from(self.model)
            .where(
                self.model.tenant_id == self.tenant_id,
                self.model.type == RoleType.ROLE.value,
                self.model.parent_id.is_(None),
                self.model.path.is_(None),
                self.model.leader_id.is_(None),
                self.model.level == 1,
            )
        )

        if not include_deleted:
            query = query.where(self.model.is_deleted.is_(False))
            count_query = count_query.where(self.model.is_deleted.is_(False))

        if search:
            pattern = f"%{search}%"
            condition = or_(
                self.model.name.ilike(pattern),
                self.model.code.ilike(pattern),
                self.model.description.ilike(pattern),
            )
            query = query.where(condition)
            count_query = count_query.where(condition)

        count_result = await self.db.execute(count_query)
        total = count_result.scalar() or 0

        query = query.order_by(self.model.sort_order.asc(), self.model.id.asc())
        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(query)
        return list(result.scalars().all()), total


__all__ = ["TenantPermissionRoleRepository"]
