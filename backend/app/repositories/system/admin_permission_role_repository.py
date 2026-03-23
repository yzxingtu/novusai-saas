"""
Admin permission role repository / 管理后台权限角色仓储
"""

from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload

from app.core.base_repository import BaseRepository
from app.enums.role import RoleType
from app.models.auth.admin_role import AdminRole


class AdminPermissionRoleRepository(BaseRepository[AdminRole]):
    """Repository for admin permission roles / 管理后台权限角色仓储"""

    model = AdminRole

    _scope_fields = {
        "admin": {
            "id", "name", "code", "is_system", "is_active",
            "created_at", "updated_at",
        },
    }

    def _base_query(self):
        query = select(self.model)
        if hasattr(self.model, "permissions"):
            query = query.options(selectinload(self.model.permissions))
        if hasattr(self.model, "type"):
            query = query.where(
                self.model.type == RoleType.ROLE.value,
                self.model.parent_id.is_(None),
                self.model.path.is_(None),
                self.model.leader_id.is_(None),
                self.model.level == 1,
            )
        return query

    async def get_by_id(
        self,
        id: int,
        include_deleted: bool = False,
    ) -> AdminRole | None:
        query = self._base_query().where(self.model.id == id)
        if not include_deleted:
            query = query.where(self.model.is_deleted.is_(False))
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_by_code(self, code: str) -> AdminRole | None:
        query = self._base_query().where(
            self.model.code == code,
            self.model.is_deleted.is_(False),
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def code_exists(self, code: str, exclude_id: int | None = None) -> bool:
        query = select(self.model.id).where(
            self.model.code == code,
            self.model.parent_id.is_(None),
            self.model.path.is_(None),
            self.model.leader_id.is_(None),
            self.model.level == 1,
            self.model.is_deleted.is_(False),
        )
        if hasattr(self.model, "type"):
            query = query.where(self.model.type == RoleType.ROLE.value)
        if exclude_id:
            query = query.where(self.model.id != exclude_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none() is not None

    async def get_list(
        self,
        skip: int = 0,
        limit: int = 100,
        order_by=None,
        include_deleted: bool = False,
        **filters,
    ) -> list[AdminRole]:
        query = self._base_query()
        if not include_deleted:
            query = query.where(self.model.is_deleted.is_(False))
        for key, value in filters.items():
            if hasattr(self.model, key) and value is not None:
                query = query.where(getattr(self.model, key) == value)
        query = query.order_by(self.model.sort_order.asc(), self.model.id.asc())
        query = query.offset(skip).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def count(self, include_deleted: bool = False, **filters) -> int:
        query = select(self.model.id)
        if hasattr(self.model, "type"):
            query = query.where(
                self.model.type == RoleType.ROLE.value,
                self.model.parent_id.is_(None),
                self.model.path.is_(None),
                self.model.leader_id.is_(None),
                self.model.level == 1,
            )
        if not include_deleted:
            query = query.where(self.model.is_deleted.is_(False))
        for key, value in filters.items():
            if hasattr(self.model, key) and value is not None:
                query = query.where(getattr(self.model, key) == value)
        result = await self.db.execute(select(func.count()).select_from(query.subquery()))
        return result.scalar() or 0

    async def create(self, data: dict) -> AdminRole:
        if hasattr(self.model, "type"):
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
    ) -> tuple[list[AdminRole], int]:
        query = self._base_query()
        count_query = select(func.count()).select_from(self.model)

        if hasattr(self.model, "type"):
            query = query.where(
                self.model.type == RoleType.ROLE.value,
                self.model.parent_id.is_(None),
                self.model.path.is_(None),
                self.model.leader_id.is_(None),
                self.model.level == 1,
            )
            count_query = count_query.where(
                self.model.type == RoleType.ROLE.value,
                self.model.parent_id.is_(None),
                self.model.path.is_(None),
                self.model.leader_id.is_(None),
                self.model.level == 1,
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


__all__ = ["AdminPermissionRoleRepository"]
