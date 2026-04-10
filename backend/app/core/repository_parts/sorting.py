"""Sortable helpers mixin."""

from __future__ import annotations

from typing import Any, Generic

from sqlalchemy import func, select, update

from .types import ModelType


class RepositorySortingMixin(Generic[ModelType]):
    """Sortable field configuration and batch sort update helpers."""

    db: Any
    model: type[ModelType]

    def _get_sortable_config(self) -> dict[str, Any] | None:
        return getattr(self.model, "__sortable__", None)

    async def get_next_sort_order(self, **scope_filters: Any) -> int:
        sortable = self._get_sortable_config()
        if not sortable:
            raise ValueError(
                f"Model {self.model.__name__} does not have __sortable__ configuration"
            )

        sort_field = sortable.get("field", "sort_order")
        step = sortable.get("step", 1000)
        scope_fields = sortable.get("scope_fields", [])

        if not hasattr(self.model, sort_field):
            raise ValueError(
                f"Model {self.model.__name__} does not have field '{sort_field}'"
            )

        sort_column = getattr(self.model, sort_field)
        query = select(func.coalesce(func.max(sort_column), 0)).where(
            self.model.is_deleted.is_(False)
        )
        for field in scope_fields:
            if field in scope_filters and hasattr(self.model, field):
                query = query.where(getattr(self.model, field) == scope_filters[field])

        result = await self.db.execute(query)
        max_value = result.scalar() or 0
        return max_value + step

    async def batch_update_sort_order(
        self,
        ordered_ids: list[int],
        **scope_filters: Any,
    ) -> int:
        _ = scope_filters
        if not ordered_ids:
            return 0

        sortable = self._get_sortable_config()
        if not sortable:
            raise ValueError(
                f"Model {self.model.__name__} does not have __sortable__ configuration"
            )

        sort_field = sortable.get("field", "sort_order")
        step = sortable.get("step", 1000)
        if not hasattr(self.model, sort_field):
            raise ValueError(
                f"Model {self.model.__name__} does not have field '{sort_field}'"
            )

        from sqlalchemy import case

        cases = {
            record_id: step * index
            for index, record_id in enumerate(ordered_ids, start=1)
        }
        stmt = (
            update(self.model)
            .where(
                self.model.id.in_(ordered_ids),
                self.model.is_deleted.is_(False),
            )
            .values(**{sort_field: case(cases, value=self.model.id)})
        )
        result = await self.db.execute(stmt)
        return result.rowcount
