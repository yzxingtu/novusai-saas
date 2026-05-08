"""Filtering, sorting and data-permission mixin."""

from __future__ import annotations

from typing import Any, Generic

from sqlalchemy import and_, asc, desc
from sqlalchemy.orm import InstrumentedAttribute
from sqlalchemy.sql import Select

from app.schemas.common.query import FilterOp, FilterRule

from .types import ModelType


class RepositoryFilteringMixin(Generic[ModelType]):
    """Filter/sort whitelist and value-casting helpers."""

    model: type[ModelType]
    _scope_fields: dict[str, set[str]]

    def get_allowed_fields(
        self, scope: str | None = None
    ) -> dict[str, InstrumentedAttribute]:
        filterable = getattr(self.model, "__filterable__", {})
        base: dict[str, InstrumentedAttribute] = {}
        for field_name, attr_name in filterable.items():
            if hasattr(self.model, attr_name):
                base[field_name] = getattr(self.model, attr_name)

        if scope and scope in self._scope_fields:
            allowed = self._scope_fields[scope]
            return {k: v for k, v in base.items() if k in allowed}

        return base

    def get_sortable_fields(self) -> dict[str, InstrumentedAttribute]:
        sortable = getattr(self.model, "__sortable_fields__", None)
        if sortable is None:
            sortable_attr = getattr(self.model, "__sortable__", None)
            if isinstance(sortable_attr, dict) and "field" not in sortable_attr:
                sortable = sortable_attr

        if sortable is None:
            sortable = getattr(self.model, "__filterable__", {})

        result: dict[str, InstrumentedAttribute] = {}
        for field_name, attr_name in sortable.items():
            if hasattr(self.model, attr_name):
                result[field_name] = getattr(self.model, attr_name)
        return result

    def _cast_value(self, col: InstrumentedAttribute, value: Any) -> Any:
        from datetime import date, datetime

        if value is None:
            return None
        if isinstance(value, list):
            return value

        try:
            col_type = col.type.python_type
            if isinstance(value, col_type):
                return value
            if col_type is bool:
                if isinstance(value, str):
                    return value.lower() in ("true", "1", "yes")
                return bool(value)
            if col_type is int:
                return int(value)
            if col_type is datetime:
                if isinstance(value, str):
                    for fmt in (
                        "%Y-%m-%d %H:%M:%S",
                        "%Y-%m-%dT%H:%M:%S",
                        "%Y-%m-%dT%H:%M:%SZ",
                        "%Y-%m-%dT%H:%M:%S.%f",
                        "%Y-%m-%dT%H:%M:%S.%fZ",
                        "%Y-%m-%d",
                    ):
                        try:
                            return datetime.strptime(value, fmt)
                        except ValueError:
                            continue
                    return value
                return value
            if col_type is date:
                if isinstance(value, str):
                    try:
                        return datetime.strptime(value, "%Y-%m-%d").date()
                    except ValueError:
                        return value
                return value
            return col_type(value)
        except (ValueError, TypeError, AttributeError):
            return value

    def _apply_filters(
        self,
        query: Select,
        rules: list[FilterRule],
        allowed_fields: dict[str, InstrumentedAttribute],
    ) -> Select:
        predicates = []
        for rule in rules:
            if rule.field not in allowed_fields:
                raise ValueError("errors.filters.unknown_field")

            col = allowed_fields[rule.field]
            v1 = self._cast_value(col, rule.value)
            v2 = self._cast_value(col, rule.value2)

            match rule.op:
                case FilterOp.eq:
                    predicates.append(col == v1)
                case FilterOp.ne:
                    predicates.append(col != v1)
                case FilterOp.lt:
                    predicates.append(col < v1)
                case FilterOp.lte:
                    predicates.append(col <= v1)
                case FilterOp.gt:
                    predicates.append(col > v1)
                case FilterOp.gte:
                    predicates.append(col >= v1)
                case FilterOp.like:
                    escaped = str(v1).replace("%", r"\%").replace("_", r"\_")
                    predicates.append(col.like(f"%{escaped}%", escape="\\"))
                case FilterOp.ilike:
                    escaped = str(v1).replace("%", r"\%").replace("_", r"\_")
                    predicates.append(col.ilike(f"%{escaped}%", escape="\\"))
                case FilterOp.in_:
                    if isinstance(v1, str):
                        vals = [x.strip() for x in v1.split(",") if x.strip()]
                    else:
                        vals = v1 if isinstance(v1, list) else [v1]
                    if len(vals) > 100:
                        raise ValueError("errors.filters.in_too_many_values")
                    predicates.append(col.in_(vals))
                case FilterOp.between:
                    if v1 is None or v2 is None:
                        raise ValueError("errors.filters.between_requires_two_values")
                    predicates.append(col.between(v1, v2))
                case FilterOp.isnull:
                    predicates.append(col.is_(None))
                case FilterOp.notnull:
                    predicates.append(col.is_not(None))

        if predicates:
            query = query.where(and_(*predicates))
        return query

    def _apply_data_permission_if_needed(self, query: Select) -> Select:
        from app.core.data_permission import apply_data_permission_if_needed

        return apply_data_permission_if_needed(query, self.model)

    def _build_data_permission_condition(self):
        from app.core.data_permission import (
            build_data_permission_condition,
            data_permission_ctx,
        )

        ctx = data_permission_ctx.get()
        if not ctx:
            return None
        return build_data_permission_condition(
            self.model,
            ctx.get("current_user_id"),
            ctx=ctx,
        )

    def _apply_data_permission_create_defaults(
        self,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        from app.core.data_permission import (
            data_permission_ctx,
            is_data_permission_enabled,
        )

        if not is_data_permission_enabled(self.model):
            return data

        ctx = data_permission_ctx.get()
        if not ctx:
            return data

        result = dict(data)
        if (
            "created_by" not in result
            and ctx.get("current_user_id") is not None
            and hasattr(self.model, "created_by")
        ):
            result["created_by"] = ctx["current_user_id"]
        if (
            "org_node_id" not in result
            and ctx.get("primary_org_id") is not None
            and hasattr(self.model, "org_node_id")
        ):
            result["org_node_id"] = ctx["primary_org_id"]
        if (
            "dept_id" not in result
            and ctx.get("primary_department_id") is not None
            and hasattr(self.model, "dept_id")
        ):
            result["dept_id"] = ctx["primary_department_id"]
        return result

    def _apply_sort(
        self,
        query: Select,
        sorts: list[str],
        allowed_fields: dict[str, InstrumentedAttribute],
    ) -> Select:
        if not sorts:
            if hasattr(self.model, "created_at"):
                return query.order_by(desc(self.model.created_at))
            return query.order_by(desc(self.model.id))

        order_exprs = []
        for s in sorts:
            desc_flag = s.startswith("-")
            field_name = s[1:] if desc_flag else s
            if field_name not in allowed_fields:
                raise ValueError("errors.sorts.unknown_field")
            col = allowed_fields[field_name]
            order_exprs.append(desc(col) if desc_flag else asc(col))

        return query.order_by(*order_exprs)
