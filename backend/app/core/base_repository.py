"""
仓储基类模块 / Repository Base Module

提供数据访问层的基类，封装通用的 CRUD 操作
Provides base classes for the data access layer, encapsulating common CRUD operations.
"""

from typing import Any, Generic, TypeVar

from sqlalchemy import and_, asc, delete, desc, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute
from sqlalchemy.sql import Select

from app.core.base_model import BaseModel, utc_now
from app.enums.common import RecycleStageEnum
from app.schemas.common.query import FilterOp, FilterRule, QuerySpec
from app.schemas.common.select import SelectOption

# 泛型类型变量 / Generic type variable
ModelType = TypeVar("ModelType", bound=BaseModel)


class BaseRepository(Generic[ModelType]):
    """
    仓储基类 / Repository Base Class

    封装数据访问层的通用 CRUD 操作
    Encapsulates common CRUD operations for the data access layer.

    使用示例 / Usage:
        class UserRepository(BaseRepository[User]):
            model = User

    通用筛选支持 / Generic filter support:
        子类可通过 _scope_fields 配置不同 scope 下允许过滤的字段
        Subclasses can configure _scope_fields for allowed filter fields per scope.
    """

    model: type[ModelType]

    # 按 scope 限制可过滤字段，子类可覆盖 / Per-scope filter field restrictions, overridable by subclasses
    # 示例 / Example: {"admin": {"id", "username", "email"}, "tenant": {"id", "username"}}
    _scope_fields: dict[str, set[str]] = {}

    def __init__(self, db: AsyncSession):
        """
        初始化仓储 / Initialize repository

        Args:
            db: 异步数据库会话 / Async database session
        """
        self.db = db

    async def get_by_id(
        self,
        id: int,
        include_deleted: bool = False,
    ) -> ModelType | None:
        """
        根据 ID 获取单条记录 / Get a single record by ID

        Args:
            id: 记录 ID / Record ID
            include_deleted: 是否包含已删除记录 / Whether to include soft-deleted records

        Returns:
            模型实例或 None / Model instance or None
        """
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
        """
        根据 ID 列表获取多条记录 / Get multiple records by ID list

        Args:
            ids: ID 列表 / List of IDs
            include_deleted: 是否包含已删除记录 / Whether to include soft-deleted records

        Returns:
            模型实例列表 / List of model instances
        """
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
        """
        获取记录列表 / Get a list of records

        Args:
            skip: 跳过的记录数 / Number of records to skip
            limit: 返回的最大记录数 / Max number of records to return
            order_by: 排序字段 / Sort field
            include_deleted: 是否包含已删除记录 / Whether to include soft-deleted records
            **filters: 过滤条件 / Filter conditions

        Returns:
            模型实例列表 / List of model instances
        """
        query = select(self.model)

        if not include_deleted:
            query = query.where(self.model.is_deleted.is_(False))

        # 应用过滤条件 / Apply filter conditions
        for key, value in filters.items():
            if hasattr(self.model, key) and value is not None:
                query = query.where(getattr(self.model, key) == value)

        query = self._apply_data_permission_if_needed(query)

        # 排序 / Sort
        if order_by is not None:
            query = query.order_by(order_by)
        else:
            query = query.order_by(self.model.id.desc())

        # 分页 / Pagination
        query = query.offset(skip).limit(limit)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def count(
        self,
        include_deleted: bool = False,
        **filters: Any,
    ) -> int:
        """
        统计记录数量 / Count records

        Args:
            include_deleted: 是否包含已删除记录 / Whether to include soft-deleted records
            **filters: 过滤条件 / Filter conditions

        Returns:
            记录数量 / Record count
        """
        query = select(func.count(self.model.id))

        if not include_deleted:
            query = query.where(self.model.is_deleted.is_(False))

        # 应用过滤条件 / Apply filter conditions
        for key, value in filters.items():
            if hasattr(self.model, key) and value is not None:
                query = query.where(getattr(self.model, key) == value)

        query = self._apply_data_permission_if_needed(query)
        result = await self.db.execute(query)
        return result.scalar() or 0

    async def create(self, data: dict[str, Any]) -> ModelType:
        """
        创建记录 / Create a record

        Args:
            data: 创建数据字典 / Creation data dictionary

        Returns:
            创建的模型实例 / Created model instance
        """
        instance = self.model(**data)
        self.db.add(instance)
        await self.db.flush()
        await self.db.refresh(instance)
        return instance

    async def create_many(self, data_list: list[dict[str, Any]]) -> list[ModelType]:
        """
        批量创建记录 / Batch create records

        Args:
            data_list: 创建数据字典列表 / List of creation data dictionaries

        Returns:
            创建的模型实例列表 / List of created model instances
        """
        instances = [self.model(**data) for data in data_list]
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
        """
        更新记录 / Update a record

        Args:
            id: 记录 ID / Record ID
            data: 更新数据字典 / Update data dictionary

        Returns:
            更新后的模型实例或 None / Updated model instance or None
        """
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
        """
        批量更新记录 / Batch update records

        Args:
            ids: ID 列表 / List of IDs
            data: 更新数据字典 / Update data dictionary

        Returns:
            更新的记录数量 / Number of updated records
        """
        if not ids:
            return 0

        stmt = (
            update(self.model)
            .where(self.model.id.in_(ids))
            .where(self.model.is_deleted.is_(False))
            .values(**data)
        )
        result = await self.db.execute(stmt)
        return result.rowcount

    async def delete(
        self,
        id: int,
        soft: bool = True,
    ) -> bool:
        """
        删除记录 / Delete a record

        Args:
            id: 记录 ID / Record ID
            soft: 是否软删除（默认 True） / Whether to soft-delete (default True)

        Returns:
            是否删除成功 / Whether deletion was successful
        """
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
        """
        批量删除记录 / Batch delete records

        Args:
            ids: ID 列表 / List of IDs
            soft: 是否软删除（默认 True） / Whether to soft-delete (default True)

        Returns:
            删除的记录数量 / Number of deleted records
        """
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

        result = await self.db.execute(stmt)
        return result.rowcount

    async def exists(
        self,
        id: int,
        include_deleted: bool = False,
    ) -> bool:
        """
        检查记录是否存在 / Check if a record exists

        Args:
            id: 记录 ID / Record ID
            include_deleted: 是否包含已删除记录 / Whether to include soft-deleted records

        Returns:
            是否存在 / Whether the record exists
        """
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
        """
        根据条件获取单条记录 / Get a single record by conditions

        Args:
            include_deleted: 是否包含已删除记录 / Whether to include soft-deleted records
            **filters: 过滤条件 / Filter conditions

        Returns:
            模型实例或 None / Model instance or None
        """
        query = select(self.model)

        if not include_deleted:
            query = query.where(self.model.is_deleted.is_(False))

        for key, value in filters.items():
            if hasattr(self.model, key) and value is not None:
                query = query.where(getattr(self.model, key) == value)

        query = self._apply_data_permission_if_needed(query)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    # ==================== 通用筛选方法 / Generic Filter Methods ====================

    def get_allowed_fields(self, scope: str | None = None) -> dict[str, InstrumentedAttribute]:
        """
        获取允许过滤的字段 / Get allowed filter fields

        从模型的 __filterable__ 属性获取可过滤字段，并根据 scope 进行裁剪
        Gets filterable fields from the model's __filterable__ attribute, trimmed by scope.

        Args:
            scope: API 端标识 / API endpoint identifier (e.g. 'admin', 'tenant')

        Returns:
            字段名到 SQLAlchemy 列的映射 / Field name to SQLAlchemy column mapping
        """
        # 从模型获取 __filterable__ 属性 / Get __filterable__ from model
        filterable = getattr(self.model, "__filterable__", {})

        # 构建字段映射 / Build field mapping
        base: dict[str, InstrumentedAttribute] = {}
        for field_name, attr_name in filterable.items():
            if hasattr(self.model, attr_name):
                base[field_name] = getattr(self.model, attr_name)

        # 按 scope 裁剪 / Trim by scope
        if scope and scope in self._scope_fields:
            allowed = self._scope_fields[scope]
            return {k: v for k, v in base.items() if k in allowed}

        return base

    def get_sortable_fields(self) -> dict[str, InstrumentedAttribute]:
        """
        获取允许排序的字段 / Get allowed sort fields

        优先级 / Priority: __sortable_fields__ > __sortable__ (dict format) > __filterable__

        Returns:
            字段名到 SQLAlchemy 列的映射 / Field name to SQLAlchemy column mapping
        """
        # 优先使用 __sortable_fields__（向后兼容） / Prefer __sortable_fields__ (backward compat)
        sortable = getattr(self.model, "__sortable_fields__", None)

        if sortable is None:
            # 检查 __sortable__（如果是字段映射字典而非排序配置） / Check __sortable__ (if it's a field mapping dict, not sort config)
            sortable_attr = getattr(self.model, "__sortable__", None)
            if isinstance(sortable_attr, dict) and "field" not in sortable_attr:
                sortable = sortable_attr

        if sortable is None:
            # 回退到 __filterable__ / Fallback to __filterable__
            sortable = getattr(self.model, "__filterable__", {})

        result: dict[str, InstrumentedAttribute] = {}
        for field_name, attr_name in sortable.items():
            if hasattr(self.model, attr_name):
                result[field_name] = getattr(self.model, attr_name)

        return result

    def _cast_value(self, col: InstrumentedAttribute, value: Any) -> Any:
        """
        根据列类型转换值 / Cast value based on column type

        Args:
            col: SQLAlchemy 列对象 / SQLAlchemy column object
            value: 原始值 / Raw value

        Returns:
            转换后的值 / Casted value
        """
        from datetime import date, datetime

        if value is None:
            return None

        # 列表类型不进行转换（用于 IN 操作符） / Skip conversion for lists (used in IN operator)
        if isinstance(value, list):
            return value

        try:
            # 获取列的 Python 类型 / Get column's Python type
            col_type = col.type.python_type

            # 如果已经是正确类型，直接返回 / Already correct type, return directly
            if isinstance(value, col_type):
                return value

            # 处理布尔类型 / Handle boolean type
            if col_type is bool:
                if isinstance(value, str):
                    return value.lower() in ("true", "1", "yes")
                return bool(value)

            # 处理整数类型 / Handle integer type
            if col_type is int:
                return int(value)

            # 处理日期时间类型 / Handle datetime type
            if col_type is datetime:
                if isinstance(value, str):
                    # 尝试多种日期时间格式 / Try multiple datetime formats
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
                    # 如果所有格式都失败，返回原值 / If all formats fail, return raw value
                    return value
                return value

            # 处理日期类型 / Handle date type
            if col_type is date:
                if isinstance(value, str):
                    try:
                        return datetime.strptime(value, "%Y-%m-%d").date()
                    except ValueError:
                        return value
                return value

            # 其他类型尝试直接转换 / Other types, try direct conversion
            return col_type(value)
        except (ValueError, TypeError, AttributeError):
            # 转换失败，返回原值 / Conversion failed, return raw value
            return value

    def _apply_filters(
        self,
        query: Select,
        rules: list[FilterRule],
        allowed_fields: dict[str, InstrumentedAttribute],
    ) -> Select:
        """
        应用筛选条件 / Apply filter conditions

        Args:
            query: SQLAlchemy 查询对象 / SQLAlchemy query object
            rules: 筛选规则列表 / List of filter rules
            allowed_fields: 允许的字段映射 / Allowed field mapping

        Returns:
            应用筛选后的查询对象 / Query with filters applied

        Raises:
            ValueError: 字段不在允许列表中 / Field not in allowed list
        """
        predicates = []

        for rule in rules:
            # 验证字段是否允许 / Validate field is allowed
            if rule.field not in allowed_fields:
                raise ValueError("errors.filters.unknown_field")

            col = allowed_fields[rule.field]
            # 根据列类型转换值 / Cast value based on column type
            v1 = self._cast_value(col, rule.value)
            v2 = self._cast_value(col, rule.value2)

            # 根据操作符构建条件 / Build condition based on operator
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
                    # 支持逗号分隔的字符串或列表 / Support comma-separated strings or lists
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
        """
        对声明 __data_permission__ 的 Model 应用数据权限过滤
        Apply data permission filter for models with __data_permission__ = True.
        """
        if not getattr(self.model, "__data_permission__", False):
            return query
        from app.core.data_permission import DataPermissionFilter, data_permission_ctx

        ctx = data_permission_ctx.get()
        if not ctx:
            return query
        return DataPermissionFilter.apply(query, self.model, ctx.get("current_user_id"))

    def _apply_sort(
        self,
        query: Select,
        sorts: list[str],
        allowed_fields: dict[str, InstrumentedAttribute],
    ) -> Select:
        """
        应用排序 / Apply sorting

        Args:
            query: SQLAlchemy 查询对象 / SQLAlchemy query object
            sorts: 排序字段列表，前缀 - 表示降序 / Sort fields, prefix - for descending
            allowed_fields: 允许的字段映射 / Allowed field mapping

        Returns:
            应用排序后的查询对象 / Query with sorting applied

        Raises:
            ValueError: 排序字段不在允许列表中 / Sort field not in allowed list
        """
        if not sorts:
            # 默认按 created_at 或 id 降序 / Default sort by created_at or id descending
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

    async def query_list(
        self,
        spec: QuerySpec,
        scope: str | None = None,
        forced_filters: list[FilterRule] | None = None,
        include_deleted: bool = False,
    ) -> tuple[list[ModelType], int]:
        """
        通用列表查询 / Generic list query

        支持筛选、排序、分页，并返回总数
        Supports filtering, sorting, pagination and returns total count.

        Args:
            spec: 查询规格 / Query specification (contains filters/sort/page/size)
            scope: 作用域 / Scope for restricting filterable fields per endpoint
            forced_filters: 强制过滤条件 / Forced filters (e.g. tenant isolation), cannot be overridden
            include_deleted: 是否包含已删除记录 / Whether to include soft-deleted records

        Returns:
            (数据列表, 总数) / (data list, total count)

        示例 / Example:
            spec = QuerySpec(
                filters=[FilterRule(field="status", value="active")],
                sort=["-created_at"],
                page=1,
                size=20
            )
            items, total = await repo.query_list(spec, scope="admin")
        """
        # 获取允许的字段（受 scope 限制） / Get allowed fields (scope-restricted)
        allowed_fields = self.get_allowed_fields(scope)
        # 获取所有字段（不受 scope 限制，用于强制过滤条件） / Get all fields (unrestricted, for forced filters)
        all_fields = self.get_allowed_fields(None)

        # 构建基础查询 / Build base query
        query = select(self.model)

        # 应用软删除过滤 / Apply soft-delete filter
        if not include_deleted:
            query = query.where(self.model.is_deleted.is_(False))

        # 先应用强制过滤条件（不受 scope 限制） / Apply forced filters first (unrestricted)
        if forced_filters:
            query = self._apply_filters(query, forced_filters, all_fields)

        # 再应用用户过滤条件（受 scope 限制） / Then apply user filters (scope-restricted)
        if spec.filters:
            query = self._apply_filters(query, spec.filters, allowed_fields)

        # 数据权限过滤（仅对声明 __data_permission__ 的 Model 生效）/ Data permission filter (opt-in via __data_permission__)
        query = self._apply_data_permission_if_needed(query)

        # 查询总数
        count_query = select(func.count()).select_from(query.subquery())
        count_result = await self.db.execute(count_query)
        total = count_result.scalar() or 0

        # 应用排序（使用 __sortable__ 白名单） / Apply sorting (using __sortable__ whitelist)
        sortable_fields = self.get_sortable_fields()
        query = self._apply_sort(query, spec.sort, sortable_fields)

        # 应用分页 / Apply pagination
        query = query.offset(spec.offset).limit(spec.limit)

        # 执行查询 / Execute query
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
        """
        获取下拉选项列表 / Get select option list.

        根据模型的 __selectable__ 配置自动构建查询，支持列表和树型两种模式

        分页模式:
            - page >= 1 时启用分页，返回指定页的数据和总数
            - page = 0 时不分页，返回全部数据（受 limit 限制）

        Args:
            search: 搜索关键词
            limit: 最大返回数量（仅非分页模式有效）
            filters: 额外过滤条件（如 is_active=True）
            tree: 是否返回树型结构
            parent_id: 父节点 ID（树型模式下用于懒加载）
            page: 页码（0=不分页，>=1=分页）
            page_size: 每页数量（分页模式有效）

        Returns:
            (SelectOption 列表, 总数)

        __selectable__ 配置示例:
            __selectable__ = {
                "label": "name",
                "value": "id",
                "search": ["name", "code"],
                "extra": ["code", "type"],
                # 树型配置（可选）
                "tree": {
                    "parent_field": "parent_id",      # 父节点 ID 字段
                    "children_field": "children",     # 子节点关联名称
                    "order_by": "sort_order",         # 排序字段
                }
            }
        """
        # 获取 __selectable__ 配置
        selectable = getattr(self.model, "__selectable__", None)
        if not selectable:
            raise ValueError(
                f"Model {self.model.__name__} does not have __selectable__ configuration"
            )

        label_field = selectable.get("label", "name")
        search_fields = selectable.get("search", [label_field])

        # 树型模式处理（不支持分页）
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
            # 树型模式不支持分页，total 返回 items 数量
            return items, len(items)

        # 列表模式 / List mode
        query = select(self.model).where(self.model.is_deleted.is_(False))

        query = self._apply_data_permission_if_needed(query)

        # 应用额外过滤条件 / Apply extra filters
        if filters:
            for key, value in filters.items():
                if hasattr(self.model, key) and value is not None:
                    query = query.where(getattr(self.model, key) == value)

        # 应用搜索条件（OR 多字段）
        if search:
            escaped_search = str(search).replace("%", r"\%").replace("_", r"\_")
            search_predicates = []
            for field_name in search_fields:
                if hasattr(self.model, field_name):
                    col = getattr(self.model, field_name)
                    search_predicates.append(col.ilike(f"%{escaped_search}%", escape="\\"))
            if search_predicates:
                query = query.where(or_(*search_predicates))

        # 查询总数
        count_query = select(func.count()).select_from(query.subquery())
        count_result = await self.db.execute(count_query)
        total = count_result.scalar() or 0

        # 排序
        if hasattr(self.model, label_field):
            query = query.order_by(asc(getattr(self.model, label_field)))

        # 分页或限制
        if page >= 1:
            # 分页模式
            offset = (page - 1) * page_size
            query = query.offset(offset).limit(page_size)
        else:
            # 非分页模式，使用 limit
            query = query.limit(limit)

        # 执行查询
        result = await self.db.execute(query)
        items = list(result.scalars().all())

        # 构建 SelectOption 列表
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
        """
        获取树型下拉选项 / Get tree select options.

        Args:
            selectable: __selectable__ 配置
            tree_config: 树型配置
            search: 搜索关键词
            limit: 最大返回数量
            filters: 额外过滤条件
            parent_id: 父节点 ID（懒加载时指定）
        """
        parent_field = tree_config.get("parent_field", "parent_id")
        children_field = tree_config.get("children_field", "children")
        order_field = tree_config.get("order_by", "sort_order")
        search_fields = selectable.get("search", [selectable.get("label", "name")])

        # 懒加载模式：仅返回指定父节点的直接子节点 / Lazy load: direct children only
        if parent_id is not None:
            query = select(self.model).where(
                self.model.is_deleted.is_(False),
                getattr(self.model, parent_field) == parent_id,
            )
            query = self._apply_data_permission_if_needed(query)

            # 应用额外过滤条件 / Apply extra filters
            if filters:
                for key, value in filters.items():
                    if hasattr(self.model, key) and value is not None:
                        query = query.where(getattr(self.model, key) == value)

            # 排序
            if hasattr(self.model, order_field):
                query = query.order_by(asc(getattr(self.model, order_field)))

            query = query.limit(limit)
            result = await self.db.execute(query)
            items = list(result.scalars().all())

            # 构建选项（带 is_leaf 标记）
            return self._build_select_options(
                items, selectable, tree_mode=True, children_field=children_field
            )

        # 全量树模式：返回完整树结构 / Full tree mode
        query = select(self.model).where(self.model.is_deleted.is_(False))
        query = self._apply_data_permission_if_needed(query)

        # 应用额外过滤条件 / Apply extra filters
        if filters:
            for key, value in filters.items():
                if hasattr(self.model, key) and value is not None:
                    query = query.where(getattr(self.model, key) == value)

        # 应用搜索条件
        if search:
            escaped_search = str(search).replace("%", r"\%").replace("_", r"\_")
            search_predicates = []
            for field_name in search_fields:
                if hasattr(self.model, field_name):
                    col = getattr(self.model, field_name)
                    search_predicates.append(col.ilike(f"%{escaped_search}%", escape="\\"))
            if search_predicates:
                query = query.where(or_(*search_predicates))

        # 排序
        if hasattr(self.model, order_field):
            query = query.order_by(asc(getattr(self.model, order_field)))

        query = query.limit(limit)
        result = await self.db.execute(query)
        all_items = list(result.scalars().all())

        # 构建树结构
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
        """
        构建 SelectOption 列表 / Build SelectOption list.

        Args:
            items: 模型实例列表
            selectable: __selectable__ 配置
            tree_mode: 是否树型模式（包含 is_leaf 字段）
            children_field: 子节点关联名称
        """
        label_field = selectable.get("label", "name")
        value_field = selectable.get("value", "id")
        extra_fields = selectable.get("extra", [])

        options = []
        for item in items:
            label = getattr(item, label_field, "")
            value = getattr(item, value_field, 0)

            # 构建 extra 数据
            extra = None
            if extra_fields:
                extra = {}
                for ef in extra_fields:
                    if hasattr(item, ef):
                        extra[ef] = getattr(item, ef)

            # 检查是否禁用
            disabled = False
            if hasattr(item, "is_active"):
                disabled = not item.is_active

            option = SelectOption(
                label=str(label),
                value=value,
                extra=extra,
                disabled=disabled,
            )

            # 树型模式时添加 is_leaf 标记
            if tree_mode:
                children = getattr(item, children_field, None)
                if children is not None:
                    # 过滤已删除的子节点
                    active_children = [
                        c for c in children
                        if not getattr(c, "is_deleted", False)
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
        """
        构建树型 SelectOption 结构 / Build tree SelectOption structure.

        Args:
            items: 所有模型实例（平坦列表）
            selectable: __selectable__ 配置
            parent_field: 父节点 ID 字段名
            children_field: 子节点关联名称
        """
        _ = children_field
        label_field = selectable.get("label", "name")
        value_field = selectable.get("value", "id")
        extra_fields = selectable.get("extra", [])

        # 构建 ID -> item 映射
        item_map: dict[int, ModelType] = {}
        for item in items:
            item_map[getattr(item, value_field)] = item

        # 构建 ID -> SelectOption 映射
        option_map: dict[int | str, SelectOption] = {}
        for item in items:
            value = getattr(item, value_field)
            label = getattr(item, label_field, "")

            # 构建 extra 数据
            extra = None
            if extra_fields:
                extra = {}
                for ef in extra_fields:
                    if hasattr(item, ef):
                        extra[ef] = getattr(item, ef)

            # 检查是否禁用
            disabled = False
            if hasattr(item, "is_active"):
                disabled = not item.is_active

            option_map[value] = SelectOption(
                label=str(label),
                value=value,
                extra=extra,
                disabled=disabled,
                children=[],  # 初始化为空列表
                is_leaf=True,  # 默认为叶子节点
            )

        # 构建树结构
        root_options: list[SelectOption] = []
        for item in items:
            value = getattr(item, value_field)
            parent_id = getattr(item, parent_field, None)
            option = option_map[value]

            if parent_id is None or parent_id not in option_map:
                # 根节点
                root_options.append(option)
            else:
                # 子节点，添加到父节点的 children
                parent_option = option_map[parent_id]
                if parent_option.children is not None:
                    parent_option.children.append(option)
                    parent_option.is_leaf = False  # 父节点不是叶子

        return root_options

    # ========================================
    # 通用排序方法 / Generic Sort Methods
    # ========================================

    def _get_sortable_config(self) -> dict[str, Any] | None:
        """
        获取模型的排序配置 / Get model's sort configuration

        Returns:
            排序配置字典或 None / Sort config dict or None

        __sortable__ 配置示例 / Config example:
            __sortable__ = {
                "field": "sort_order",      # 排序字段名 / Sort field name
                "step": 1000,               # 排序步长 / Sort step
                "scope_fields": [],         # 作用域字段 / Scope fields, e.g. ["tenant_id", "parent_id"]
            }
        """
        return getattr(self.model, "__sortable__", None)

    async def get_next_sort_order(self, **scope_filters: Any) -> int:
        """
        获取下一个排序值 / Get next sort order value

        计算方式 / Calculation: current max + step

        Args:
            **scope_filters: 作用域过滤条件 / Scope filters (e.g. tenant_id, parent_id)

        Returns:
            下一个排序值 / Next sort order value

        Raises:
            ValueError: 模型未配置 __sortable__ / Model has no __sortable__ config
        """
        sortable = self._get_sortable_config()
        if not sortable:
            raise ValueError(
                f"Model {self.model.__name__} does not have __sortable__ configuration"
            )

        sort_field = sortable.get("field", "sort_order")
        step = sortable.get("step", 1000)
        scope_fields = sortable.get("scope_fields", [])

        # 检查排序字段是否存在 / Check if sort field exists
        if not hasattr(self.model, sort_field):
            raise ValueError(
                f"Model {self.model.__name__} does not have field '{sort_field}'"
            )

        # 构建查询 / Build query
        sort_column = getattr(self.model, sort_field)
        query = select(func.coalesce(func.max(sort_column), 0)).where(
            self.model.is_deleted.is_(False)
        )

        # 应用作用域过滤 / Apply scope filters
        for field in scope_fields:
            if field in scope_filters and hasattr(self.model, field):
                query = query.where(
                    getattr(self.model, field) == scope_filters[field]
                )

        result = await self.db.execute(query)
        max_value = result.scalar() or 0

        return max_value + step

    async def batch_update_sort_order(
        self,
        ordered_ids: list[int],
        **scope_filters: Any,
    ) -> int:
        """
        批量更新排序值 / Batch update sort order

        按 ordered_ids 顺序分配排序值 / Assign sort values by ordered_ids: step*1, step*2, step*3, ...

        Args:
            ordered_ids: 有序的 ID 列表 / Ordered list of IDs
            **scope_filters: 作用域过滤条件 / Scope filters (for validation)

        Returns:
            更新的记录数 / Number of updated records

        Raises:
            ValueError: 模型未配置 __sortable__ / Model has no __sortable__ config
        """
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

        # 检查排序字段是否存在
        if not hasattr(self.model, sort_field):
            raise ValueError(
                f"Model {self.model.__name__} does not have field '{sort_field}'"
            )

        # 批量更新：使用 CASE WHEN 一次性更新所有记录 / Batch update: use CASE WHEN for single SQL
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


    # ==================== 回收站方法 / Recycle Bin Methods ====================

    async def query_deleted(
        self,
        spec: QuerySpec,
        delete_level: str | None = None,
        recycle_stage: str | None = None,
        scope: str | None = None,
        forced_filters: list[FilterRule] | None = None,
    ) -> tuple[list[ModelType], int]:
        """
        查询回收站（已删除记录） / Query recycle bin (deleted records)

        Args:
            spec: 查询规格 / Query specification (filters/sort/pagination)
            delete_level: 删除侧别过滤 / Delete scope filter ('tenant' or 'admin'), None for all
            recycle_stage: 回收站阶段过滤 / Recycle stage filter ('module' or 'global'), None for all
            scope: 作用域 / Scope
            forced_filters: 强制过滤条件 / Forced filter conditions

        Returns:
            (数据列表, 总数) / (data list, total count)
        """
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
        # 回收站自动允许 deleted_at 排序 / Auto-allow deleted_at sorting in recycle bin
        if hasattr(self.model, "deleted_at") and "deleted_at" not in sortable_fields:
            sortable_fields["deleted_at"] = self.model.deleted_at
        if (
            hasattr(self.model, "promoted_to_global_at")
            and "promoted_to_global_at" not in sortable_fields
        ):
            sortable_fields["promoted_to_global_at"] = self.model.promoted_to_global_at
        # 总回收站默认按进入总回收站时间倒序，模块回收站默认按删除时间倒序
        # Default sort: global stage by promoted_to_global_at desc, module stage by deleted_at desc
        if not spec.sort and recycle_stage == RecycleStageEnum.GLOBAL.value and hasattr(self.model, "promoted_to_global_at"):
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
        """
        统计回收站记录数量 / Count recycle bin records

        Args:
            delete_level: 删除侧别过滤 / Delete scope filter
            recycle_stage: 回收站阶段过滤 / Recycle stage filter

        Returns:
            已删除记录数量 / Count of deleted records
        """
        query = select(func.count(self.model.id)).where(
            self.model.is_deleted.is_(True)
        )
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
        """
        恢复已删除记录 / Restore a deleted record

        Args:
            id: 记录 ID / Record ID

        Returns:
            恢复后的模型实例或 None / Restored model instance or None
        """
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
        """
        推进到总回收站 / Promote a deleted record to the global recycle bin

        Args:
            id: 记录 ID / Record ID
            delete_level: 删除侧别过滤 / Delete scope filter

        Returns:
            更新后的模型实例或 None / Updated model instance or None
        """
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
        """
        物理删除记录 / Permanently delete a record

        Args:
            id: 记录 ID / Record ID

        Returns:
            是否删除成功 / Whether deletion was successful
        """
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
        """
        批量恢复已删除记录 / Batch restore deleted records

        Args:
            ids: ID 列表 / List of IDs

        Returns:
            恢复的记录数量 / Number of restored records
        """
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
        result = await self.db.execute(stmt)
        return result.rowcount

    async def batch_permanent_delete(self, ids: list[int]) -> int:
        """
        批量物理删除记录 / Batch permanently delete records

        Args:
            ids: ID 列表 / List of IDs

        Returns:
            删除的记录数量 / Number of deleted records
        """
        if not ids:
            return 0

        stmt = delete(self.model).where(
            self.model.id.in_(ids),
            self.model.is_deleted.is_(True),
            self.model.recycle_stage == RecycleStageEnum.GLOBAL.value,
        )
        result = await self.db.execute(stmt)
        return result.rowcount

    async def cleanup_expired(self, days: int = 30) -> int:
        """
        清理超过指定天数的已删除记录 / Clean up deleted records older than specified days

        Args:
            days: 保留天数，默认 30 / Retention days, default 30

        Returns:
            清理的记录数量 / Number of cleaned records
        """
        from datetime import timedelta

        cutoff = utc_now() - timedelta(days=days)
        stmt = delete(self.model).where(
            self.model.is_deleted.is_(True),
            self.model.recycle_stage == RecycleStageEnum.GLOBAL.value,
            self.model.promoted_to_global_at.is_not(None),
            self.model.promoted_to_global_at < cutoff,
        )
        result = await self.db.execute(stmt)
        return result.rowcount


class TenantRepository(BaseRepository[ModelType]):
    """
    企业级仓储基类 / Tenant Repository Base Class

    自动在查询中添加 tenant_id 过滤
    Automatically adds tenant_id filtering to queries.
    """

    def __init__(self, db: AsyncSession, tenant_id: int | None):
        """
        初始化企业仓储 / Initialize tenant repository

        Args:
            db: 异步数据库会话 / Async database session
            tenant_id: 企业 ID / Tenant ID (None for global/admin resources)
        """
        super().__init__(db)
        self.tenant_id = tenant_id

    def _tenant_scope_field_name(self) -> str:
        """Resolve tenant ownership field name / 解析租户归属字段名。"""
        if hasattr(self.model, "owner_tenant_id"):
            return "owner_tenant_id"
        if hasattr(self.model, "tenant_id"):
            return "tenant_id"
        raise AttributeError(
            f"{self.model.__name__} must define tenant_id or owner_tenant_id"
        )

    def _tenant_scope_column(self):
        """Resolve tenant ownership column / 解析租户归属列。"""
        return getattr(self.model, self._tenant_scope_field_name())

    async def get_list(
        self,
        skip: int = 0,
        limit: int = 100,
        order_by: Any = None,
        include_deleted: bool = False,
        **filters: Any,
    ) -> list[ModelType]:
        """获取企业级记录列表 / Get tenant-scoped record list"""
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
        """统计企业级记录数量 / Count tenant-scoped records"""
        filters[self._tenant_scope_field_name()] = self.tenant_id
        return await super().count(include_deleted=include_deleted, **filters)

    async def create(self, data: dict[str, Any]) -> ModelType:
        """创建企业级记录，对 __data_permission__ 模型自动填充 created_by / org_node_id / dept_id / Create tenant-scoped record, auto-fill created_by / org_node_id / dept_id for __data_permission__ models"""
        data[self._tenant_scope_field_name()] = self.tenant_id
        if getattr(self.model, "__data_permission__", False):
            from app.core.data_permission import data_permission_ctx

            ctx = data_permission_ctx.get()
            if ctx:
                if "created_by" not in data and ctx.get("current_user_id") is not None and hasattr(self.model, "created_by"):
                    data = {**data, "created_by": ctx["current_user_id"]}
                if "org_node_id" not in data and ctx.get("primary_org_id") is not None and hasattr(self.model, "org_node_id"):
                    data = {**data, "org_node_id": ctx["primary_org_id"]}
                if "dept_id" not in data and ctx.get("primary_department_id") is not None and hasattr(self.model, "dept_id"):
                    data = {**data, "dept_id": ctx["primary_department_id"]}
        return await super().create(data)

    async def get_by_id(
        self,
        id: int,
        include_deleted: bool = False,
        ) -> ModelType | None:
        """根据 ID 获取企业级记录 / Get tenant-scoped record by ID"""
        instance = await super().get_by_id(id, include_deleted)
        # 验证企业归属 / Verify tenant ownership
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
        """根据 ID 列表获取企业级记录，自动过滤非本企业数据 / Get tenant records by IDs, auto-filter non-tenant data"""
        instances = await super().get_by_ids(ids, include_deleted)
        tenant_field = self._tenant_scope_field_name()
        return [
            inst for inst in instances
            if getattr(inst, tenant_field, None) == self.tenant_id
        ]

    async def get_one_by(
        self,
        include_deleted: bool = False,
        **filters: Any,
    ) -> ModelType | None:
        """根据条件获取企业级单条记录，自动注入 tenant_id / Get single tenant record by conditions, auto-inject tenant_id"""
        filters[self._tenant_scope_field_name()] = self.tenant_id
        return await super().get_one_by(include_deleted=include_deleted, **filters)

    async def query_list(
        self,
        spec: QuerySpec,
        scope: str | None = None,
        forced_filters: list[FilterRule] | None = None,
        include_deleted: bool = False,
    ) -> tuple[list[ModelType], int]:
        """
        企业级通用列表查询 / Tenant-scoped generic list query

        自动注入 tenant_id 过滤条件
        Automatically injects tenant_id filter condition.
        """
        # 强制添加企业过滤 / Force add tenant filter
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
        """
        企业级下拉选项列表 / Tenant-level select options list.

        自动注入 tenant_id 过滤，支持列表和树型两种模式

        Args:
            search: 搜索关键词
            limit: 最大返回数量（仅非分页模式有效）
            filters: 额外过滤条件
            tree: 是否返回树型结构
            parent_id: 父节点 ID（树型模式下用于懒加载）
            page: 页码（0=不分页，>=1=分页）
            page_size: 每页数量（分页模式有效）

        Returns:
            (SelectOption 列表, 总数)
        """
        # 自动添加企业过滤
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
        """企业级回收站查询，自动注入 tenant_id / Tenant recycle bin query, auto-inject tenant_id"""
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
        """企业级回收站计数，自动注入 tenant_id / Tenant recycle bin count, auto-inject tenant_id"""
        query = select(func.count(self.model.id)).where(
            self.model.is_deleted.is_(True),
            self._tenant_scope_column() == self.tenant_id,
        )
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
        """企业级批量更新，自动注入 tenant_id 防止跨企业操作 / Tenant batch update, auto-inject tenant_id to prevent cross-tenant operations"""
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
        result = await self.db.execute(stmt)
        return result.rowcount

    async def delete_many(
        self,
        ids: list[int],
        soft: bool = True,
    ) -> int:
        """企业级批量删除，自动注入 tenant_id 防止跨企业操作 / Tenant batch delete, auto-inject tenant_id to prevent cross-tenant operations"""
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

        result = await self.db.execute(stmt)
        return result.rowcount

    async def batch_restore(self, ids: list[int]) -> int:
        """企业级批量恢复，自动注入 tenant_id 防止跨企业操作 / Tenant batch restore, auto-inject tenant_id to prevent cross-tenant operations"""
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
        result = await self.db.execute(stmt)
        return result.rowcount

    async def batch_permanent_delete(self, ids: list[int]) -> int:
        """企业级批量物理删除，自动注入 tenant_id 防止跨企业操作 / Tenant batch permanent delete, auto-inject tenant_id to prevent cross-tenant operations"""
        if not ids:
            return 0

        stmt = delete(self.model).where(
            self.model.id.in_(ids),
            self.model.is_deleted.is_(True),
            self.model.recycle_stage == RecycleStageEnum.GLOBAL.value,
            self._tenant_scope_column() == self.tenant_id,
        )
        result = await self.db.execute(stmt)
        return result.rowcount


# 导出 / Exports
__all__ = ["BaseRepository", "TenantRepository"]
