"""CRUD-focused mixin for repository facade."""

from __future__ import annotations

from typing import Any, Generic

from sqlalchemy import delete, func, select, update

from .types import ModelType


class RepositoryCrudMixin(Generic[ModelType]):
    """Core CRUD operations shared by base repositories."""

    db: Any
    model: type[ModelType]

    def _apply_data_permission_if_needed(self, query): ...

    def _build_data_permission_condition(self): ...

    def _apply_data_permission_create_defaults(
        self,
        data: dict[str, Any],
    ) -> dict[str, Any]: ...

    async def get_by_id(
        self,
        id: int,
        include_deleted: bool = False,
    ) -> ModelType | None:
        query = select(self.model).where(self.model.id == id)
        if not include_deleted:
            query = query.where(self.model.is_deleted.is_(False))

        query = self._apply_data_permission_if_needed(query)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_by_ids(
        self,
        ids: list[int],
        include_deleted: bool = False,
    ) -> list[ModelType]:
        if not ids:
            return []

        query = select(self.model).where(self.model.id.in_(ids))
        if not include_deleted:
            query = query.where(self.model.is_deleted.is_(False))

        query = self._apply_data_permission_if_needed(query)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_list(
        self,
        skip: int = 0,
        limit: int = 100,
        order_by: Any = None,
        include_deleted: bool = False,
        **filters: Any,
    ) -> list[ModelType]:
        query = select(self.model)

        if not include_deleted:
            query = query.where(self.model.is_deleted.is_(False))

        for key, value in filters.items():
            if hasattr(self.model, key) and value is not None:
                query = query.where(getattr(self.model, key) == value)

        query = self._apply_data_permission_if_needed(query)
        if order_by is not None:
            query = query.order_by(order_by)
        else:
            query = query.order_by(self.model.id.desc())
        query = query.offset(skip).limit(limit)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def count(
        self,
        include_deleted: bool = False,
        **filters: Any,
    ) -> int:
        query = select(func.count(self.model.id))
        if not include_deleted:
            query = query.where(self.model.is_deleted.is_(False))

        for key, value in filters.items():
            if hasattr(self.model, key) and value is not None:
                query = query.where(getattr(self.model, key) == value)

        query = self._apply_data_permission_if_needed(query)
        result = await self.db.execute(query)
        return result.scalar() or 0

    async def create(self, data: dict[str, Any]) -> ModelType:
        instance = self.model(**self._apply_data_permission_create_defaults(data))
        self.db.add(instance)
        await self.db.flush()
        await self.db.refresh(instance)
        return instance

    async def create_many(self, data_list: list[dict[str, Any]]) -> list[ModelType]:
        instances = [
            self.model(**self._apply_data_permission_create_defaults(data))
            for data in data_list
        ]
        self.db.add_all(instances)
        await self.db.flush()
        for instance in instances:
            await self.db.refresh(instance)
        return instances

    async def update(
        self,
        id: int,
        data: dict[str, Any],
    ) -> ModelType | None:
        instance = await self.get_by_id(id)
        if instance is None:
            return None

        instance.update_from_dict(data)
        await self.db.flush()
        await self.db.refresh(instance)
        return instance

    async def update_many(
        self,
        ids: list[int],
        data: dict[str, Any],
    ) -> int:
        if not ids:
            return 0

        stmt = (
            update(self.model)
            .where(self.model.id.in_(ids))
            .where(self.model.is_deleted.is_(False))
            .values(**data)
        )
        permission_condition = self._build_data_permission_condition()
        if permission_condition is not None:
            stmt = stmt.where(permission_condition)
        result = await self.db.execute(stmt)
        return result.rowcount

    async def delete(
        self,
        id: int,
        soft: bool = True,
    ) -> bool:
        instance = await self.get_by_id(id)
        if instance is None:
            return False

        if soft:
            instance.soft_delete()
        else:
            await self.db.delete(instance)

        await self.db.flush()
        return True

    async def delete_many(
        self,
        ids: list[int],
        soft: bool = True,
    ) -> int:
        if not ids:
            return 0

        if soft:
            stmt = (
                update(self.model)
                .where(self.model.id.in_(ids))
                .where(self.model.is_deleted.is_(False))
                .values(is_deleted=True)
            )
        else:
            stmt = delete(self.model).where(self.model.id.in_(ids))

        permission_condition = self._build_data_permission_condition()
        if permission_condition is not None:
            stmt = stmt.where(permission_condition)
        result = await self.db.execute(stmt)
        return result.rowcount

    async def exists(
        self,
        id: int,
        include_deleted: bool = False,
    ) -> bool:
        query = select(func.count(self.model.id)).where(self.model.id == id)

        if not include_deleted:
            query = query.where(self.model.is_deleted.is_(False))

        query = self._apply_data_permission_if_needed(query)
        result = await self.db.execute(query)
        count = result.scalar() or 0
        return count > 0

    async def get_one_by(
        self,
        include_deleted: bool = False,
        **filters: Any,
    ) -> ModelType | None:
        query = select(self.model)

        if not include_deleted:
            query = query.where(self.model.is_deleted.is_(False))

        for key, value in filters.items():
            if hasattr(self.model, key) and value is not None:
                query = query.where(getattr(self.model, key) == value)

        query = self._apply_data_permission_if_needed(query)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
