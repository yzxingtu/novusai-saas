"""Query and select-option mixin for repository facade."""

from __future__ import annotations

from typing import Any, Generic

from sqlalchemy import asc, func, or_, select

from app.schemas.common.query import FilterRule, QuerySpec
from app.schemas.common.select import SelectOption

from .types import ModelType


class RepositoryQueryMixin(Generic[ModelType]):
    """High-level list query + select option builders."""

    db: Any
    model: type[ModelType]

    def get_allowed_fields(self, scope: str | None = None): ...

    def get_sortable_fields(self): ...

    def _apply_data_permission_if_needed(self, query): ...

    def _apply_filters(self, query, rules, allowed_fields): ...

    def _apply_sort(self, query, sorts, allowed_fields): ...

    async def query_list(
        self,
        spec: QuerySpec,
        scope: str | None = None,
        forced_filters: list[FilterRule] | None = None,
        include_deleted: bool = False,
    ) -> tuple[list[ModelType], int]:
        allowed_fields = self.get_allowed_fields(scope)
        all_fields = self.get_allowed_fields(None)

        query = select(self.model)
        if not include_deleted:
            query = query.where(self.model.is_deleted.is_(False))

        if forced_filters:
            query = self._apply_filters(query, forced_filters, all_fields)
        if spec.filters:
            query = self._apply_filters(query, spec.filters, allowed_fields)

        query = self._apply_data_permission_if_needed(query)

        count_query = select(func.count()).select_from(query.subquery())
        count_result = await self.db.execute(count_query)
        total = count_result.scalar() or 0

        sortable_fields = self.get_sortable_fields()
        query = self._apply_sort(query, spec.sort, sortable_fields)
        query = query.offset(spec.offset).limit(spec.limit)

        result = await self.db.execute(query)
        items = list(result.scalars().all())
        return items, total

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
        selectable = getattr(self.model, "__selectable__", None)
        if not selectable:
            raise ValueError(
                f"Model {self.model.__name__} does not have __selectable__ configuration"
            )

        label_field = selectable.get("label", "name")
        search_fields = selectable.get("search", [label_field])

        if tree:
            tree_config = selectable.get("tree")
            if not tree_config:
                raise ValueError(
                    f"Model {self.model.__name__} does not have tree configuration in __selectable__"
                )
            items = await self._get_tree_select_options(
                selectable=selectable,
                tree_config=tree_config,
                search=search,
                limit=limit,
                filters=filters,
                parent_id=parent_id,
            )
            return items, len(items)

        query = select(self.model).where(self.model.is_deleted.is_(False))
        query = self._apply_data_permission_if_needed(query)

        if filters:
            for key, value in filters.items():
                if hasattr(self.model, key) and value is not None:
                    query = query.where(getattr(self.model, key) == value)

        if search:
            escaped_search = str(search).replace("%", r"\%").replace("_", r"\_")
            search_predicates = []
            for field_name in search_fields:
                if hasattr(self.model, field_name):
                    col = getattr(self.model, field_name)
                    search_predicates.append(
                        col.ilike(f"%{escaped_search}%", escape="\\")
                    )
            if search_predicates:
                query = query.where(or_(*search_predicates))

        count_query = select(func.count()).select_from(query.subquery())
        count_result = await self.db.execute(count_query)
        total = count_result.scalar() or 0

        if hasattr(self.model, label_field):
            query = query.order_by(asc(getattr(self.model, label_field)))

        if page >= 1:
            offset = (page - 1) * page_size
            query = query.offset(offset).limit(page_size)
        else:
            query = query.limit(limit)

        result = await self.db.execute(query)
        items = list(result.scalars().all())

        return self._build_select_options(items, selectable), total

    async def _get_tree_select_options(
        self,
        selectable: dict[str, Any],
        tree_config: dict[str, Any],
        search: str = "",
        limit: int = 500,
        filters: dict[str, Any] | None = None,
        parent_id: int | None = None,
    ) -> list[SelectOption]:
        parent_field = tree_config.get("parent_field", "parent_id")
        children_field = tree_config.get("children_field", "children")
        order_field = tree_config.get("order_by", "sort_order")
        search_fields = selectable.get("search", [selectable.get("label", "name")])

        if parent_id is not None:
            query = select(self.model).where(
                self.model.is_deleted.is_(False),
                getattr(self.model, parent_field) == parent_id,
            )
            query = self._apply_data_permission_if_needed(query)

            if filters:
                for key, value in filters.items():
                    if hasattr(self.model, key) and value is not None:
                        query = query.where(getattr(self.model, key) == value)

            if hasattr(self.model, order_field):
                query = query.order_by(asc(getattr(self.model, order_field)))

            query = query.limit(limit)
            result = await self.db.execute(query)
            items = list(result.scalars().all())
            return self._build_select_options(
                items, selectable, tree_mode=True, children_field=children_field
            )

        query = select(self.model).where(self.model.is_deleted.is_(False))
        query = self._apply_data_permission_if_needed(query)

        if filters:
            for key, value in filters.items():
                if hasattr(self.model, key) and value is not None:
                    query = query.where(getattr(self.model, key) == value)

        if search:
            escaped_search = str(search).replace("%", r"\%").replace("_", r"\_")
            search_predicates = []
            for field_name in search_fields:
                if hasattr(self.model, field_name):
                    col = getattr(self.model, field_name)
                    search_predicates.append(
                        col.ilike(f"%{escaped_search}%", escape="\\")
                    )
            if search_predicates:
                query = query.where(or_(*search_predicates))

        if hasattr(self.model, order_field):
            query = query.order_by(asc(getattr(self.model, order_field)))

        query = query.limit(limit)
        result = await self.db.execute(query)
        all_items = list(result.scalars().all())
        return self._build_tree_options(
            all_items, selectable, parent_field, children_field
        )

    def _build_select_options(
        self,
        items: list[ModelType],
        selectable: dict[str, Any],
        tree_mode: bool = False,
        children_field: str = "children",
    ) -> list[SelectOption]:
        label_field = selectable.get("label", "name")
        value_field = selectable.get("value", "id")
        extra_fields = selectable.get("extra", [])

        options = []
        for item in items:
            label = getattr(item, label_field, "")
            value = getattr(item, value_field, 0)

            extra = None
            if extra_fields:
                extra = {}
                for ef in extra_fields:
                    if hasattr(item, ef):
                        extra[ef] = getattr(item, ef)

            disabled = False
            if hasattr(item, "is_active"):
                disabled = not item.is_active

            option = SelectOption(
                label=str(label),
                value=value,
                extra=extra,
                disabled=disabled,
            )

            if tree_mode:
                children = getattr(item, children_field, None)
                if children is not None:
                    active_children = [
                        c for c in children if not getattr(c, "is_deleted", False)
                    ]
                    option.is_leaf = len(active_children) == 0
                else:
                    option.is_leaf = True

            options.append(option)

        return options

    def _build_tree_options(
        self,
        items: list[ModelType],
        selectable: dict[str, Any],
        parent_field: str,
        children_field: str,
    ) -> list[SelectOption]:
        _ = children_field
        label_field = selectable.get("label", "name")
        value_field = selectable.get("value", "id")
        extra_fields = selectable.get("extra", [])

        option_map: dict[int | str, SelectOption] = {}
        for item in items:
            value = getattr(item, value_field)
            label = getattr(item, label_field, "")
            extra = None
            if extra_fields:
                extra = {}
                for ef in extra_fields:
                    if hasattr(item, ef):
                        extra[ef] = getattr(item, ef)

            disabled = False
            if hasattr(item, "is_active"):
                disabled = not item.is_active

            option_map[value] = SelectOption(
                label=str(label),
                value=value,
                extra=extra,
                disabled=disabled,
                children=[],
                is_leaf=True,
            )

        root_options: list[SelectOption] = []
        for item in items:
            value = getattr(item, value_field)
            parent_id = getattr(item, parent_field, None)
            option = option_map[value]

            if parent_id is None or parent_id not in option_map:
                root_options.append(option)
            else:
                parent_option = option_map[parent_id]
                if parent_option.children is not None:
                    parent_option.children.append(option)
                    parent_option.is_leaf = False

        return root_options
