"""Tenant-scope behaviors layered on top of BaseRepository."""

from __future__ import annotations

from typing import Any, Generic

from sqlalchemy import delete, func, select, update

from app.core.base_model import utc_now
from app.enums.common import RecycleStageEnum
from app.schemas.common.query import FilterRule, QuerySpec
from app.schemas.common.select import SelectOption

from .types import ModelType


class TenantScopeMixin(Generic[ModelType]):
    """Tenant isolation overrides for read/write/batch flows."""

    db: Any
    model: type[ModelType]
    tenant_id: int | None

    def _build_data_permission_condition(self): ...

    def _apply_data_permission_if_needed(self, query): ...

    def _tenant_scope_field_name(self) -> str:
        if hasattr(self.model, "owner_tenant_id"):
            return "owner_tenant_id"
        if hasattr(self.model, "tenant_id"):
            return "tenant_id"
        raise AttributeError(
            f"{self.model.__name__} must define tenant_id or owner_tenant_id"
        )

    def _tenant_scope_column(self):
        return getattr(self.model, self._tenant_scope_field_name())

    async def get_list(
        self,
        skip: int = 0,
        limit: int = 100,
        order_by: Any = None,
        include_deleted: bool = False,
        **filters: Any,
    ) -> list[ModelType]:
        filters[self._tenant_scope_field_name()] = self.tenant_id
        return await super().get_list(
            skip=skip,
            limit=limit,
            order_by=order_by,
            include_deleted=include_deleted,
            **filters,
        )

    async def count(
        self,
        include_deleted: bool = False,
        **filters: Any,
    ) -> int:
        filters[self._tenant_scope_field_name()] = self.tenant_id
        return await super().count(include_deleted=include_deleted, **filters)

    async def create(self, data: dict[str, Any]) -> ModelType:
        data[self._tenant_scope_field_name()] = self.tenant_id
        return await super().create(data)

    async def get_by_id(
        self,
        id: int,
        include_deleted: bool = False,
    ) -> ModelType | None:
        instance = await super().get_by_id(id, include_deleted)
        if instance:
            tenant_value = getattr(
                instance,
                self._tenant_scope_field_name(),
                None,
            )
            if tenant_value != self.tenant_id:
                return None
        return instance

    async def get_by_ids(
        self,
        ids: list[int],
        include_deleted: bool = False,
    ) -> list[ModelType]:
        instances = await super().get_by_ids(ids, include_deleted)
        tenant_field = self._tenant_scope_field_name()
        return [
            inst
            for inst in instances
            if getattr(inst, tenant_field, None) == self.tenant_id
        ]

    async def get_one_by(
        self,
        include_deleted: bool = False,
        **filters: Any,
    ) -> ModelType | None:
        filters[self._tenant_scope_field_name()] = self.tenant_id
        return await super().get_one_by(include_deleted=include_deleted, **filters)

    async def query_list(
        self,
        spec: QuerySpec,
        scope: str | None = None,
        forced_filters: list[FilterRule] | None = None,
        include_deleted: bool = False,
    ) -> tuple[list[ModelType], int]:
        tenant_filter = FilterRule(
            field=self._tenant_scope_field_name(),
            value=self.tenant_id,
        )
        all_forced = [tenant_filter] + (forced_filters or [])
        return await super().query_list(
            spec=spec,
            scope=scope,
            forced_filters=all_forced,
            include_deleted=include_deleted,
        )

    async def get_select_options(
        self,
        search: str = "",
        limit: int = 50,
        filters: dict[str, Any] | None = None,
        tree: bool = False,
        parent_id: int | None = None,
        page: int = 0,
        page_size: int = 20,
    ) -> tuple[list[SelectOption], int]:
        all_filters = filters.copy() if filters else {}
        all_filters[self._tenant_scope_field_name()] = self.tenant_id

        return await super().get_select_options(
            search=search,
            limit=limit,
            filters=all_filters,
            tree=tree,
            parent_id=parent_id,
            page=page,
            page_size=page_size,
        )

    async def query_deleted(
        self,
        spec: QuerySpec,
        delete_level: str | None = None,
        recycle_stage: str | None = None,
        scope: str | None = None,
        forced_filters: list[FilterRule] | None = None,
    ) -> tuple[list[ModelType], int]:
        tenant_filter = FilterRule(
            field=self._tenant_scope_field_name(),
            value=self.tenant_id,
        )
        all_forced = [tenant_filter] + (forced_filters or [])
        return await super().query_deleted(
            spec=spec,
            delete_level=delete_level,
            recycle_stage=recycle_stage,
            scope=scope,
            forced_filters=all_forced,
        )

    async def count_deleted(
        self,
        delete_level: str | None = None,
        recycle_stage: str | None = None,
    ) -> int:
        query = select(func.count(self.model.id)).where(
            self.model.is_deleted.is_(True),
            self._tenant_scope_column() == self.tenant_id,
        )
        query = self._apply_data_permission_if_needed(query)
        if delete_level:
            query = query.where(self.model.delete_level == delete_level)
        if recycle_stage:
            query = query.where(self.model.recycle_stage == recycle_stage)

        result = await self.db.execute(query)
        return result.scalar() or 0

    async def update_many(
        self,
        ids: list[int],
        data: dict[str, Any],
    ) -> int:
        if not ids:
            return 0

        stmt = (
            update(self.model)
            .where(
                self.model.id.in_(ids),
                self.model.is_deleted.is_(False),
                self._tenant_scope_column() == self.tenant_id,
            )
            .values(**data)
        )
        permission_condition = self._build_data_permission_condition()
        if permission_condition is not None:
            stmt = stmt.where(permission_condition)
        result = await self.db.execute(stmt)
        return result.rowcount

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
                .where(
                    self.model.id.in_(ids),
                    self.model.is_deleted.is_(False),
                    self._tenant_scope_column() == self.tenant_id,
                )
                .values(is_deleted=True, deleted_at=utc_now())
            )
        else:
            stmt = delete(self.model).where(
                self.model.id.in_(ids),
                self._tenant_scope_column() == self.tenant_id,
            )

        permission_condition = self._build_data_permission_condition()
        if permission_condition is not None:
            stmt = stmt.where(permission_condition)
        result = await self.db.execute(stmt)
        return result.rowcount

    async def batch_restore(self, ids: list[int]) -> int:
        if not ids:
            return 0

        stmt = (
            update(self.model)
            .where(
                self.model.id.in_(ids),
                self.model.is_deleted.is_(True),
                self._tenant_scope_column() == self.tenant_id,
            )
            .values(
                is_deleted=False,
                deleted_at=None,
                delete_level=None,
                recycle_stage=None,
                promoted_to_global_at=None,
                updated_at=utc_now(),
            )
        )
        permission_condition = self._build_data_permission_condition()
        if permission_condition is not None:
            stmt = stmt.where(permission_condition)
        result = await self.db.execute(stmt)
        return result.rowcount

    async def batch_permanent_delete(self, ids: list[int]) -> int:
        if not ids:
            return 0

        stmt = delete(self.model).where(
            self.model.id.in_(ids),
            self.model.is_deleted.is_(True),
            self.model.recycle_stage == RecycleStageEnum.GLOBAL.value,
            self._tenant_scope_column() == self.tenant_id,
        )
        permission_condition = self._build_data_permission_condition()
        if permission_condition is not None:
            stmt = stmt.where(permission_condition)
        result = await self.db.execute(stmt)
        return result.rowcount
