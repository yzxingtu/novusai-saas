"""Recycle-bin operations mixin."""

from __future__ import annotations

from typing import Any, Generic

from sqlalchemy import delete, desc, func, select, update

from app.core.base_model import utc_now
from app.enums.common import RecycleStageEnum
from app.schemas.common.query import FilterRule, QuerySpec

from .types import ModelType


class RepositoryRecycleBinMixin(Generic[ModelType]):
    """Soft-delete recovery and cleanup behaviors."""

    db: Any
    model: type[ModelType]

    def get_allowed_fields(self, scope: str | None = None): ...

    def get_sortable_fields(self): ...

    def _apply_data_permission_if_needed(self, query): ...

    def _apply_filters(self, query, rules, allowed_fields): ...

    def _apply_sort(self, query, sorts, allowed_fields): ...

    def _build_data_permission_condition(self): ...

    async def get_by_id(
        self,
        id: int,
        include_deleted: bool = False,
    ) -> ModelType | None: ...

    async def query_deleted(
        self,
        spec: QuerySpec,
        delete_level: str | None = None,
        recycle_stage: str | None = None,
        scope: str | None = None,
        forced_filters: list[FilterRule] | None = None,
    ) -> tuple[list[ModelType], int]:
        allowed_fields = self.get_allowed_fields(scope)
        all_fields = self.get_allowed_fields(None)

        query = select(self.model).where(self.model.is_deleted.is_(True))
        query = self._apply_data_permission_if_needed(query)

        if delete_level:
            query = query.where(self.model.delete_level == delete_level)
        if recycle_stage:
            query = query.where(self.model.recycle_stage == recycle_stage)

        if forced_filters:
            query = self._apply_filters(query, forced_filters, all_fields)

        if spec.filters:
            query = self._apply_filters(query, spec.filters, allowed_fields)

        count_query = select(func.count()).select_from(query.subquery())
        count_result = await self.db.execute(count_query)
        total = count_result.scalar() or 0

        sortable_fields = dict(self.get_sortable_fields())
        if hasattr(self.model, "deleted_at") and "deleted_at" not in sortable_fields:
            sortable_fields["deleted_at"] = self.model.deleted_at
        if (
            hasattr(self.model, "promoted_to_global_at")
            and "promoted_to_global_at" not in sortable_fields
        ):
            sortable_fields["promoted_to_global_at"] = self.model.promoted_to_global_at
        if (
            not spec.sort
            and recycle_stage == RecycleStageEnum.GLOBAL.value
            and hasattr(self.model, "promoted_to_global_at")
        ):
            query = query.order_by(
                desc(self.model.promoted_to_global_at),
                desc(self.model.deleted_at),
            )
        elif not spec.sort and hasattr(self.model, "deleted_at"):
            query = query.order_by(desc(self.model.deleted_at))
        else:
            query = self._apply_sort(query, spec.sort, sortable_fields)

        query = query.offset(spec.offset).limit(spec.limit)

        result = await self.db.execute(query)
        items = list(result.scalars().all())

        return items, total

    async def count_deleted(
        self,
        delete_level: str | None = None,
        recycle_stage: str | None = None,
    ) -> int:
        query = select(func.count(self.model.id)).where(self.model.is_deleted.is_(True))
        query = self._apply_data_permission_if_needed(query)
        if delete_level:
            query = query.where(self.model.delete_level == delete_level)
        if recycle_stage:
            query = query.where(self.model.recycle_stage == recycle_stage)

        result = await self.db.execute(query)
        return result.scalar() or 0

    async def restore_by_id(
        self,
        id: int,
        delete_level: str | None = None,
        recycle_stage: str | None = None,
    ) -> ModelType | None:
        instance = await self.get_by_id(id, include_deleted=True)
        if instance is None or not instance.is_deleted:
            return None
        if delete_level and getattr(instance, "delete_level", None) != delete_level:
            return None
        if recycle_stage and getattr(instance, "recycle_stage", None) != recycle_stage:
            return None

        instance.restore()
        await self.db.flush()
        await self.db.refresh(instance)
        return instance

    async def promote_to_global_by_id(
        self,
        id: int,
        delete_level: str | None = None,
    ) -> ModelType | None:
        instance = await self.get_by_id(id, include_deleted=True)
        if instance is None or not instance.is_deleted:
            return None
        if delete_level and getattr(instance, "delete_level", None) != delete_level:
            return None
        if getattr(instance, "recycle_stage", None) == RecycleStageEnum.GLOBAL.value:
            return instance

        instance.promote_to_global()
        await self.db.flush()
        await self.db.refresh(instance)
        return instance

    async def permanent_delete(
        self,
        id: int,
        delete_level: str | None = None,
        recycle_stage: str | None = RecycleStageEnum.GLOBAL.value,
    ) -> bool:
        instance = await self.get_by_id(id, include_deleted=True)
        if instance is None or not instance.is_deleted:
            return False
        if delete_level and getattr(instance, "delete_level", None) != delete_level:
            return False
        if recycle_stage and getattr(instance, "recycle_stage", None) != recycle_stage:
            return False

        await self.db.delete(instance)
        await self.db.flush()
        return True

    async def batch_restore(self, ids: list[int]) -> int:
        if not ids:
            return 0

        stmt = (
            update(self.model)
            .where(
                self.model.id.in_(ids),
                self.model.is_deleted.is_(True),
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
        )
        permission_condition = self._build_data_permission_condition()
        if permission_condition is not None:
            stmt = stmt.where(permission_condition)
        result = await self.db.execute(stmt)
        return result.rowcount

    async def cleanup_expired(self, days: int = 30) -> int:
        from datetime import timedelta

        cutoff = utc_now() - timedelta(days=days)
        stmt = delete(self.model).where(
            self.model.is_deleted.is_(True),
            self.model.recycle_stage == RecycleStageEnum.GLOBAL.value,
            self.model.promoted_to_global_at.is_not(None),
            self.model.promoted_to_global_at < cutoff,
        )
        permission_condition = self._build_data_permission_condition()
        if permission_condition is not None:
            stmt = stmt.where(permission_condition)
        result = await self.db.execute(stmt)
        return result.rowcount
