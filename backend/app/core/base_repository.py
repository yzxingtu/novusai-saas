"""
仓储基类模块

提供数据访问层的基类，封装通用的 CRUD 操作
"""

from typing import Any, Generic, TypeVar, Type

from sqlalchemy import select, func, update, delete, and_, or_, desc, asc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, InstrumentedAttribute
from sqlalchemy.sql import Select

from app.core.base_model import BaseModel
from app.schemas.common.query import FilterOp, FilterRule, QuerySpec
from app.schemas.common.select import SelectOption

# 泛型类型变量
ModelType = TypeVar("ModelType", bound=BaseModel)


class BaseRepository(Generic[ModelType]):
    """
    仓储基类
    
    封装数据访问层的通用 CRUD 操作
    
    使用示例:
        class UserRepository(BaseRepository[User]):
            model = User
    
    通用筛选支持:
        子类可通过 _scope_fields 配置不同 scope 下允许过滤的字段
    """
    
    model: Type[ModelType]
    
    # 按 scope 限制可过滤字段，子类可覆盖
    # 示例: {"admin": {"id", "username", "email"}, "tenant": {"id", "username"}}
    _scope_fields: dict[str, set[str]] = {}
    
    def __init__(self, db: AsyncSession):
        """
        初始化仓储
        
        Args:
            db: 异步数据库会话
        """
        self.db = db
    
    async def get_by_id(
        self,
        id: int,
        include_deleted: bool = False,
    ) -> ModelType | None:
        """
        根据 ID 获取单条记录
        
        Args:
            id: 记录 ID
            include_deleted: 是否包含已删除记录
        
        Returns:
            模型实例或 None
        """
        query = select(self.model).where(self.model.id == id)
        
        if not include_deleted:
            query = query.where(self.model.is_deleted == False)
        
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def get_by_ids(
        self,
        ids: list[int],
        include_deleted: bool = False,
    ) -> list[ModelType]:
        """
        根据 ID 列表获取多条记录
        
        Args:
            ids: ID 列表
            include_deleted: 是否包含已删除记录
        
        Returns:
            模型实例列表
        """
        if not ids:
            return []
        
        query = select(self.model).where(self.model.id.in_(ids))
        
        if not include_deleted:
            query = query.where(self.model.is_deleted == False)
        
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
        获取记录列表
        
        Args:
            skip: 跳过的记录数
            limit: 返回的最大记录数
            order_by: 排序字段
            include_deleted: 是否包含已删除记录
            **filters: 过滤条件
        
        Returns:
            模型实例列表
        """
        query = select(self.model)
        
        if not include_deleted:
            query = query.where(self.model.is_deleted == False)
        
        # 应用过滤条件
        for key, value in filters.items():
            if hasattr(self.model, key) and value is not None:
                query = query.where(getattr(self.model, key) == value)
        
        # 排序
        if order_by is not None:
            query = query.order_by(order_by)
        else:
            query = query.order_by(self.model.id.desc())
        
        # 分页
        query = query.offset(skip).limit(limit)
        
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    async def count(
        self,
        include_deleted: bool = False,
        **filters: Any,
    ) -> int:
        """
        统计记录数量
        
        Args:
            include_deleted: 是否包含已删除记录
            **filters: 过滤条件
        
        Returns:
            记录数量
        """
        query = select(func.count(self.model.id))
        
        if not include_deleted:
            query = query.where(self.model.is_deleted == False)
        
        # 应用过滤条件
        for key, value in filters.items():
            if hasattr(self.model, key) and value is not None:
                query = query.where(getattr(self.model, key) == value)
        
        result = await self.db.execute(query)
        return result.scalar() or 0
    
    async def create(self, data: dict[str, Any]) -> ModelType:
        """
        创建记录
        
        Args:
            data: 创建数据字典
        
        Returns:
            创建的模型实例
        """
        instance = self.model(**data)
        self.db.add(instance)
        await self.db.flush()
        await self.db.refresh(instance)
        return instance
    
    async def create_many(self, data_list: list[dict[str, Any]]) -> list[ModelType]:
        """
        批量创建记录
        
        Args:
            data_list: 创建数据字典列表
        
        Returns:
            创建的模型实例列表
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
        更新记录
        
        Args:
            id: 记录 ID
            data: 更新数据字典
        
        Returns:
            更新后的模型实例或 None
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
        批量更新记录
        
        Args:
            ids: ID 列表
            data: 更新数据字典
        
        Returns:
            更新的记录数量
        """
        if not ids:
            return 0
        
        stmt = (
            update(self.model)
            .where(self.model.id.in_(ids))
            .where(self.model.is_deleted == False)
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
        删除记录
        
        Args:
            id: 记录 ID
            soft: 是否软删除（默认 True）
        
        Returns:
            是否删除成功
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
        批量删除记录
        
        Args:
            ids: ID 列表
            soft: 是否软删除（默认 True）
        
        Returns:
            删除的记录数量
        """
        if not ids:
            return 0
        
        if soft:
            stmt = (
                update(self.model)
                .where(self.model.id.in_(ids))
                .where(self.model.is_deleted == False)
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
        检查记录是否存在
        
        Args:
            id: 记录 ID
            include_deleted: 是否包含已删除记录
        
        Returns:
            是否存在
        """
        query = select(func.count(self.model.id)).where(self.model.id == id)
        
        if not include_deleted:
            query = query.where(self.model.is_deleted == False)
        
        result = await self.db.execute(query)
        count = result.scalar() or 0
        return count > 0
    
    async def get_one_by(
        self,
        include_deleted: bool = False,
        **filters: Any,
    ) -> ModelType | None:
        """
        根据条件获取单条记录
        
        Args:
            include_deleted: 是否包含已删除记录
            **filters: 过滤条件
        
        Returns:
            模型实例或 None
        """
        query = select(self.model)
        
        if not include_deleted:
            query = query.where(self.model.is_deleted == False)
        
        for key, value in filters.items():
            if hasattr(self.model, key) and value is not None:
                query = query.where(getattr(self.model, key) == value)
        
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    # ==================== 通用筛选方法 ====================
    
    def get_allowed_fields(self, scope: str | None = None) -> dict[str, InstrumentedAttribute]:
        """
        获取允许过滤的字段
        
        从模型的 __filterable__ 属性获取可过滤字段，并根据 scope 进行裁剪
        
        Args:
            scope: 作用域（如 'admin', 'tenant'），用于按端限制字段
        
        Returns:
            字段名到 SQLAlchemy 列的映射
        """
        # 从模型获取 __filterable__ 属性
        filterable = getattr(self.model, "__filterable__", {})
        
        # 构建字段映射
        base: dict[str, InstrumentedAttribute] = {}
        for field_name, attr_name in filterable.items():
            if hasattr(self.model, attr_name):
                base[field_name] = getattr(self.model, attr_name)
        
        # 按 scope 裁剪
        if scope and scope in self._scope_fields:
            allowed = self._scope_fields[scope]
            return {k: v for k, v in base.items() if k in allowed}
        
        return base

    def get_sortable_fields(self) -> dict[str, InstrumentedAttribute]:
        """
        获取允许排序的字段

        优先级: __sortable_fields__ > __sortable__ (dict format) > __filterable__

        Returns:
            字段名到 SQLAlchemy 列的映射
        """
        # 优先使用 __sortable_fields__（向后兼容）
        sortable = getattr(self.model, "__sortable_fields__", None)

        if sortable is None:
            # 检查 __sortable__（如果是字段映射字典而非排序配置）
            sortable_attr = getattr(self.model, "__sortable__", None)
            if isinstance(sortable_attr, dict) and "field" not in sortable_attr:
                sortable = sortable_attr

        if sortable is None:
            # 回退到 __filterable__
            sortable = getattr(self.model, "__filterable__", {})

        result: dict[str, InstrumentedAttribute] = {}
        for field_name, attr_name in sortable.items():
            if hasattr(self.model, attr_name):
                result[field_name] = getattr(self.model, attr_name)

        return result
    
    def _cast_value(self, col: InstrumentedAttribute, value: Any) -> Any:
        """
        根据列类型转换值
        
        Args:
            col: SQLAlchemy 列对象
            value: 原始值
        
        Returns:
            转换后的值
        """
        from datetime import datetime, date
        
        if value is None:
            return None
        
        # 列表类型不进行转换（用于 IN 操作符）
        if isinstance(value, list):
            return value
        
        try:
            # 获取列的 Python 类型
            col_type = col.type.python_type
            
            # 如果已经是正确类型，直接返回
            if isinstance(value, col_type):
                return value
            
            # 处理布尔类型
            if col_type is bool:
                if isinstance(value, str):
                    return value.lower() in ("true", "1", "yes")
                return bool(value)
            
            # 处理整数类型
            if col_type is int:
                return int(value)
            
            # 处理日期时间类型
            if col_type is datetime:
                if isinstance(value, str):
                    # 尝试多种日期时间格式
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
                    # 如果所有格式都失败，返回原值
                    return value
                return value
            
            # 处理日期类型
            if col_type is date:
                if isinstance(value, str):
                    try:
                        return datetime.strptime(value, "%Y-%m-%d").date()
                    except ValueError:
                        return value
                return value
            
            # 其他类型尝试直接转换
            return col_type(value)
        except (ValueError, TypeError, AttributeError):
            # 转换失败，返回原值
            return value
    
    def _apply_filters(
        self,
        query: Select,
        rules: list[FilterRule],
        allowed_fields: dict[str, InstrumentedAttribute],
    ) -> Select:
        """
        应用筛选条件
        
        Args:
            query: SQLAlchemy 查询对象
            rules: 筛选规则列表
            allowed_fields: 允许的字段映射
        
        Returns:
            应用筛选后的查询对象
        
        Raises:
            ValueError: 字段不在允许列表中
        """
        predicates = []
        
        for rule in rules:
            # 验证字段是否允许
            if rule.field not in allowed_fields:
                raise ValueError("errors.filters.unknown_field")
            
            col = allowed_fields[rule.field]
            # 根据列类型转换值
            v1 = self._cast_value(col, rule.value)
            v2 = self._cast_value(col, rule.value2)
            
            # 根据操作符构建条件
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
                    predicates.append(col.like(f"%{v1}%"))
                case FilterOp.ilike:
                    predicates.append(col.ilike(f"%{v1}%"))
                case FilterOp.in_:
                    # 支持逗号分隔的字符串或列表
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
    
    def _apply_sort(
        self,
        query: Select,
        sorts: list[str],
        allowed_fields: dict[str, InstrumentedAttribute],
    ) -> Select:
        """
        应用排序
        
        Args:
            query: SQLAlchemy 查询对象
            sorts: 排序字段列表，前缀 - 表示降序
            allowed_fields: 允许的字段映射
        
        Returns:
            应用排序后的查询对象
        
        Raises:
            ValueError: 排序字段不在允许列表中
        """
        if not sorts:
            # 默认按 created_at 或 id 降序
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
        通用列表查询
        
        支持筛选、排序、分页，并返回总数
        
        Args:
            spec: 查询规格（包含 filters/sort/page/size）
            scope: 作用域，用于按端限制可过滤字段
            forced_filters: 强制过滤条件（如多租户隔离），不可被用户覆盖
            include_deleted: 是否包含已删除记录
        
        Returns:
            (数据列表, 总数)
        
        示例:
            spec = QuerySpec(
                filters=[FilterRule(field="status", value="active")],
                sort=["-created_at"],
                page=1,
                size=20
            )
            items, total = await repo.query_list(spec, scope="admin")
        """
        # 获取允许的字段（受 scope 限制）
        allowed_fields = self.get_allowed_fields(scope)
        # 获取所有字段（不受 scope 限制，用于强制过滤条件）
        all_fields = self.get_allowed_fields(None)
        
        # 构建基础查询
        query = select(self.model)
        
        # 应用软删除过滤
        if not include_deleted:
            query = query.where(self.model.is_deleted == False)
        
        # 先应用强制过滤条件（不受 scope 限制）
        if forced_filters:
            query = self._apply_filters(query, forced_filters, all_fields)
        
        # 再应用用户过滤条件（受 scope 限制）
        if spec.filters:
            query = self._apply_filters(query, spec.filters, allowed_fields)
        
        # 查询总数
        count_query = select(func.count()).select_from(query.subquery())
        count_result = await self.db.execute(count_query)
        total = count_result.scalar() or 0
        
        # 应用排序（使用 __sortable__ 白名单）
        sortable_fields = self.get_sortable_fields()
        query = self._apply_sort(query, spec.sort, sortable_fields)
        
        # 应用分页
        query = query.offset(spec.offset).limit(spec.limit)
        
        # 执行查询
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
        获取下拉选项列表
        
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
        value_field = selectable.get("value", "id")
        search_fields = selectable.get("search", [label_field])
        extra_fields = selectable.get("extra", [])
        
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
        
        # 列表模式
        query = select(self.model).where(self.model.is_deleted == False)
        
        # 应用额外过滤条件
        if filters:
            for key, value in filters.items():
                if hasattr(self.model, key) and value is not None:
                    query = query.where(getattr(self.model, key) == value)
        
        # 应用搜索条件（OR 多字段）
        if search:
            search_predicates = []
            for field_name in search_fields:
                if hasattr(self.model, field_name):
                    col = getattr(self.model, field_name)
                    search_predicates.append(col.ilike(f"%{search}%"))
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
        获取树型下拉选项
        
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
        
        # 懒加载模式：仅返回指定父节点的直接子节点
        if parent_id is not None:
            query = select(self.model).where(
                self.model.is_deleted == False,
                getattr(self.model, parent_field) == parent_id,
            )
            
            # 应用额外过滤条件
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
        
        # 全量树模式：返回完整树结构
        query = select(self.model).where(self.model.is_deleted == False)
        
        # 应用额外过滤条件
        if filters:
            for key, value in filters.items():
                if hasattr(self.model, key) and value is not None:
                    query = query.where(getattr(self.model, key) == value)
        
        # 应用搜索条件
        if search:
            search_predicates = []
            for field_name in search_fields:
                if hasattr(self.model, field_name):
                    col = getattr(self.model, field_name)
                    search_predicates.append(col.ilike(f"%{search}%"))
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
        构建 SelectOption 列表
        
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
        构建树型 SelectOption 结构
        
        Args:
            items: 所有模型实例（平坦列表）
            selectable: __selectable__ 配置
            parent_field: 父节点 ID 字段名
            children_field: 子节点关联名称
        """
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
    # 通用排序方法
    # ========================================
    
    def _get_sortable_config(self) -> dict[str, Any] | None:
        """
        获取模型的排序配置
        
        Returns:
            排序配置字典或 None
        
        __sortable__ 配置示例:
            __sortable__ = {
                "field": "sort_order",      # 排序字段名
                "step": 1000,               # 排序步长
                "scope_fields": [],         # 作用域字段，如 ["tenant_id", "parent_id"]
            }
        """
        return getattr(self.model, "__sortable__", None)
    
    async def get_next_sort_order(self, **scope_filters: Any) -> int:
        """
        获取下一个排序值
        
        计算方式: 当前最大值 + 步长
        
        Args:
            **scope_filters: 作用域过滤条件（如 tenant_id, parent_id）
        
        Returns:
            下一个排序值
        
        Raises:
            ValueError: 模型未配置 __sortable__
        """
        sortable = self._get_sortable_config()
        if not sortable:
            raise ValueError(
                f"Model {self.model.__name__} does not have __sortable__ configuration"
            )
        
        sort_field = sortable.get("field", "sort_order")
        step = sortable.get("step", 1000)
        scope_fields = sortable.get("scope_fields", [])
        
        # 检查排序字段是否存在
        if not hasattr(self.model, sort_field):
            raise ValueError(
                f"Model {self.model.__name__} does not have field '{sort_field}'"
            )
        
        # 构建查询
        sort_column = getattr(self.model, sort_field)
        query = select(func.coalesce(func.max(sort_column), 0)).where(
            self.model.is_deleted == False
        )
        
        # 应用作用域过滤
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
        批量更新排序值
        
        按 ordered_ids 顺序分配排序值: step*1, step*2, step*3, ...
        
        Args:
            ordered_ids: 有序的 ID 列表
            **scope_filters: 作用域过滤条件（用于校验）
        
        Returns:
            更新的记录数
        
        Raises:
            ValueError: 模型未配置 __sortable__
        """
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
        
        # 批量更新：使用 CASE WHEN 一次性更新所有记录
        # 这比逐条更新效率更高
        updated_count = 0
        for index, record_id in enumerate(ordered_ids, start=1):
            new_sort_value = step * index
            stmt = (
                update(self.model)
                .where(
                    self.model.id == record_id,
                    self.model.is_deleted == False,
                )
                .values(**{sort_field: new_sort_value})
            )
            result = await self.db.execute(stmt)
            updated_count += result.rowcount
        
        return updated_count


class TenantRepository(BaseRepository[ModelType]):
    """
    租户级仓储基类
    
    自动在查询中添加 tenant_id 过滤
    """
    
    def __init__(self, db: AsyncSession, tenant_id: int):
        """
        初始化租户仓储
        
        Args:
            db: 异步数据库会话
            tenant_id: 租户 ID
        """
        super().__init__(db)
        self.tenant_id = tenant_id
    
    async def get_list(
        self,
        skip: int = 0,
        limit: int = 100,
        order_by: Any = None,
        include_deleted: bool = False,
        **filters: Any,
    ) -> list[ModelType]:
        """获取租户级记录列表"""
        filters["tenant_id"] = self.tenant_id
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
        """统计租户级记录数量"""
        filters["tenant_id"] = self.tenant_id
        return await super().count(include_deleted=include_deleted, **filters)
    
    async def create(self, data: dict[str, Any]) -> ModelType:
        """创建租户级记录"""
        data["tenant_id"] = self.tenant_id
        return await super().create(data)
    
    async def get_by_id(
        self,
        id: int,
        include_deleted: bool = False,
    ) -> ModelType | None:
        """根据 ID 获取租户级记录"""
        instance = await super().get_by_id(id, include_deleted)
        # 验证租户归属
        if instance and hasattr(instance, "tenant_id"):
            if instance.tenant_id != self.tenant_id:
                return None
        return instance
    
    async def query_list(
        self,
        spec: QuerySpec,
        scope: str | None = None,
        forced_filters: list[FilterRule] | None = None,
        include_deleted: bool = False,
    ) -> tuple[list[ModelType], int]:
        """
        租户级通用列表查询
        
        自动注入 tenant_id 过滤条件
        """
        # 强制添加租户过滤
        tenant_filter = FilterRule(field="tenant_id", value=self.tenant_id)
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
        租户级下拉选项列表
        
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
        # 自动添加租户过滤
        all_filters = filters.copy() if filters else {}
        all_filters["tenant_id"] = self.tenant_id
        
        return await super().get_select_options(
            search=search,
            limit=limit,
            filters=all_filters,
            tree=tree,
            parent_id=parent_id,
            page=page,
            page_size=page_size,
        )


# 导出
__all__ = ["BaseRepository", "TenantRepository"]
