"""
服务基类模块 / Service Base Module

提供业务逻辑层的基类，包括：
Provides base classes for the business logic layer, including:
- BaseService: 通用服务基类 / Generic service base class
- TenantService: 企业级服务基类 / Tenant-scoped service base class
- GlobalService: 全局服务基类 / Global service base class
"""

from __future__ import annotations

from typing import Any, Generic, TypeVar

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_model import BaseModel
from app.core.base_repository import BaseRepository
from app.core.base_schema import PageParams, PageResponse
from app.core.dependency_checker import (
    check_deletion_deps,
    execute_cascade_deps,
    execute_cascade_escalate,
    execute_cascade_restore,
)
from app.core.logging import LogManager
from app.enums.common import DeleteLevelEnum
from app.exceptions.base import DependencyBlockedException
from app.schemas.common.query import FilterRule, QuerySpec
from app.schemas.common.select import SelectResponse

_logger = LogManager.get_logger("db")

# 泛型类型变量 / Generic type variables
ModelType = TypeVar("ModelType", bound=BaseModel)
RepoType = TypeVar("RepoType", bound=BaseRepository)


class BaseService(Generic[ModelType, RepoType]):
    """
    服务基类 / Service Base Class

    提供通用的业务方法和扩展点（钩子方法）
    Provides common business methods and extension points (hook methods).

    使用示例 / Usage:
        class UserService(BaseService[User, UserRepository]):
            model = User
            repository_class = UserRepository
    """

    model: type[ModelType]
    repository_class: type[RepoType]

    def __init__(self, db: AsyncSession):
        """
        初始化服务 / Initialize service

        Args:
            db: 异步数据库会话 / Async database session
        """
        self.db = db
        self.repo: RepoType = self.repository_class(db)

    # ========================================
    # 通用 CRUD 方法 / Common CRUD Methods
    # ========================================

    async def get_by_id(self, id: int) -> ModelType | None:
        """
        根据 ID 获取记录 / Get record by ID

        Args:
            id: 记录 ID / Record ID

        Returns:
            模型实例或 None / Model instance or None
        """
        return await self.repo.get_by_id(id)

    async def get_by_ids(self, ids: list[int]) -> list[ModelType]:
        """
        根据 ID 列表获取记录 / Get records by ID list

        Args:
            ids: ID 列表 / List of IDs

        Returns:
            模型实例列表 / List of model instances
        """
        return await self.repo.get_by_ids(ids)

    async def get_list(
        self,
        skip: int = 0,
        limit: int = 100,
        **filters: Any,
    ) -> list[ModelType]:
        """
        获取记录列表 / Get record list

        Args:
            skip: 跳过的记录数 / Records to skip
            limit: 返回的最大记录数 / Max records to return
            **filters: 过滤条件 / Filter conditions

        Returns:
            模型实例列表 / List of model instances
        """
        return await self.repo.get_list(skip=skip, limit=limit, **filters)

    async def get_paginated(
        self,
        page_params: PageParams,
        **filters: Any,
    ) -> PageResponse[ModelType]:
        """
        获取分页记录 / Get paginated records

        Args:
            page_params: 分页参数 / Pagination parameters
            **filters: 过滤条件 / Filter conditions

        Returns:
            分页响应 / Paginated response
        """
        items = await self.repo.get_list(
            skip=page_params.skip,
            limit=page_params.limit,
            **filters,
        )
        total = await self.repo.count(**filters)

        return PageResponse.create(
            items=items,
            total=total,
            page=page_params.page,
            page_size=page_params.page_size,
        )

    async def count(self, **filters: Any) -> int:
        """
        统计记录数量 / Count records

        Args:
            **filters: 过滤条件 / Filter conditions

        Returns:
            记录数量 / Record count
        """
        return await self.repo.count(**filters)

    async def create(self, data: dict[str, Any]) -> ModelType:
        """
        创建记录 / Create a record

        Args:
            data: 创建数据字典 / Creation data dictionary

        Returns:
            创建的模型实例 / Created model instance
        """
        # 创建前钩子 / Pre-create hook
        await self._before_create(data)

        # 执行创建 / Execute creation
        instance = await self.repo.create(data)

        # 创建后钩子 / Post-create hook
        await self._after_create(instance)

        return instance

    async def update(self, id: int, data: dict[str, Any]) -> ModelType | None:
        """
        更新记录 / Update a record

        Args:
            id: 记录 ID / Record ID
            data: 更新数据字典 / Update data dictionary

        Returns:
            更新后的模型实例或 None / Updated model instance or None
        """
        # 更新前钩子 / Pre-update hook
        await self._before_update(id, data)

        # 执行更新 / Execute update
        instance = await self.repo.update(id, data)

        # 更新后钩子 / Post-update hook
        if instance:
            await self._after_update(instance)

        return instance

    # 软删除默认层级，子类覆盖 / Default soft-delete level, overridable by subclasses
    _default_delete_level: str = DeleteLevelEnum.ADMIN.value

    async def delete(self, id: int, soft: bool = True) -> bool:
        """
        删除记录（软删除时进入回收站） / Delete record (soft-delete enters recycle bin)

        自动执行 __delete_deps__ 声明的依赖检查：
        Automatically executes dependency checks declared in __delete_deps__:
        - BLOCK 依赖存在时抛出 DependencyBlockedException / Raises DependencyBlockedException when BLOCK deps exist
        - CASCADE_SOFT/CASCADE_DELETE/NULLIFY 在软删除后自动执行 / Auto-executed after soft-delete

        Args:
            id: 记录 ID / Record ID
            soft: 是否软删除（默认 True） / Whether to soft-delete (default True)

        Returns:
            是否删除成功 / Whether deletion was successful
        """
        # 删除前钩子（子类可覆盖，如 is_system 保护） / Pre-delete hook (overridable, e.g. is_system protection)
        await self._before_delete(id)

        if soft:
            instance = await self.repo.get_by_id(id)
            if instance is None:
                return False

            # 声明式依赖检查（BLOCK 策略） / Declarative dependency check (BLOCK strategy)
            await self._check_deletion_deps(instance)

            instance.soft_delete(level=self._default_delete_level)
            await self.repo.db.flush()

            # 声明式级联操作 / Declarative cascade operations (CASCADE_SOFT/CASCADE_DELETE/NULLIFY)
            await self._execute_deletion_cascade(instance)
        else:
            result = await self.repo.delete(id, soft=False)
            if not result:
                return False

        # 删除后钩子 / Post-delete hook
        await self._after_delete(id)

        return True

    async def exists(self, id: int) -> bool:
        """
        检查记录是否存在 / Check if record exists

        Args:
            id: 记录 ID / Record ID

        Returns:
            是否存在 / Whether the record exists
        """
        return await self.repo.exists(id)

    async def query_list(
        self,
        spec: QuerySpec,
        scope: str | None = None,
        forced_filters: list[FilterRule] | None = None,
    ) -> tuple[list[ModelType], int]:
        """
        通用列表查询 / Generic list query

        支持 JSON:API 风格筛选、排序、分页
        Supports JSON:API style filtering, sorting, pagination.

        Args:
            spec: 查询规格 / Query specification (contains filters/sort/page/size)
            scope: 作用域 / Scope for restricting filterable fields
            forced_filters: 强制过滤条件 / Forced filter conditions

        Returns:
            (数据列表, 总数) / (data list, total count)
        """
        return await self.repo.query_list(
            spec=spec,
            scope=scope,
            forced_filters=forced_filters,
        )

    async def get_select_options(
        self,
        search: str = "",
        limit: int = 50,
        tree: bool = False,
        parent_id: int | None = None,
        page: int = 0,
        page_size: int = 20,
        **filters: Any,
    ) -> SelectResponse:
        """
        获取下拉选项列表

        支持列表和树型两种模式，列表模式支持分页

        分页模式:
            - page >= 1 时启用分页，返回指定页的数据和分页信息
            - page = 0 时不分页，返回全部数据（受 limit 限制）

        Args:
            search: 搜索关键词
            limit: 最大返回数量（仅非分页模式有效）
            tree: 是否返回树型结构（不支持分页）
            parent_id: 父节点 ID（树型模式下用于懒加载）
            page: 页码（0=不分页，>=1=分页）
            page_size: 每页数量（分页模式有效）
            **filters: 额外过滤条件

        Returns:
            SelectResponse 响应（包含 items 和分页信息）
        """
        items, total = await self.repo.get_select_options(
            search=search,
            limit=limit,
            filters=filters if filters else None,
            tree=tree,
            parent_id=parent_id,
            page=page,
            page_size=page_size,
        )

        # 构建响应
        if page >= 1:
            # 分页模式，返回分页信息
            has_more = (page * page_size) < total
            return SelectResponse(
                items=items,
                total=total,
                page=page,
                page_size=page_size,
                has_more=has_more,
            )
        else:
            # 非分页模式，不返回分页信息
            return SelectResponse(items=items)

    # ========================================
    # 钩子方法（子类可重写） / Hook Methods (overridable by subclasses)
    # ========================================

    async def _before_create(self, data: dict[str, Any]) -> None:
        """
        创建前钩子 / Pre-create hook

        可用于：数据校验、默认值注入、权限检查等
        Useful for: data validation, default value injection, permission checks, etc.

        自动处理 / Auto-processing:
        - 如果模型配置了 __sortable__ 且未传入排序值，自动计算 / Auto-calculates sort order if model has __sortable__ and no value provided

        Args:
            data: 创建数据字典（可修改） / Creation data dict (mutable)
        """
        # 自动计算排序值 / Auto-calculate sort order
        await self._auto_set_sort_order(data)

    async def _after_create(self, instance: ModelType) -> None:
        """
        创建后钩子 / Post-create hook

        可用于：发送事件、记录日志、触发通知等
        Useful for: sending events, logging, triggering notifications, etc.

        Args:
            instance: 创建的模型实例 / Created model instance
        """
        pass

    async def _before_update(self, id: int, data: dict[str, Any]) -> None:
        """
        更新前钩子 / Pre-update hook

        可用于：数据校验、权限检查、记录变更等
        Useful for: data validation, permission checks, change tracking, etc.

        Args:
            id: 记录 ID / Record ID
            data: 更新数据字典（可修改） / Update data dict (mutable)
        """
        pass

    async def _after_update(self, instance: ModelType) -> None:
        """
        更新后钩子 / Post-update hook

        可用于：发送事件、记录日志、同步缓存等
        Useful for: sending events, logging, cache synchronization, etc.

        Args:
            instance: 更新后的模型实例 / Updated model instance
        """
        pass

    async def _before_delete(self, id: int) -> None:
        """
        删除前钩子 / Pre-delete hook

        可用于：关联检查、权限验证等（如 is_system 保护）。
        Useful for: association checks, permission validation (e.g. is_system protection).
        此钩子在依赖检查之前执行。 / This hook executes before dependency checks.

        Args:
            id: 记录 ID / Record ID
        """
        pass

    async def _after_delete(self, id: int) -> None:
        """
        删除后钩子 / Post-delete hook

        可用于：清理关联数据、记录日志等
        Useful for: cleaning up associated data, logging, etc.

        Args:
            id: 已删除的记录 ID / Deleted record ID
        """
        pass

    # ========================================
    # 回收站钩子方法（子类可重写） / Recycle Bin Hook Methods (overridable)
    # ========================================

    async def _before_restore(self, id: int) -> None:
        """恢复前钩子 / Pre-restore hook"""
        pass

    async def _after_restore(self, instance: ModelType) -> None:
        """恢复后钩子 / Post-restore hook"""
        pass

    async def _before_permanent_delete(self, id: int) -> None:
        """永久删除前钩子 / Pre-permanent-delete hook"""
        pass

    # ========================================
    # 回收站方法 / Recycle Bin Methods
    # ========================================

    async def query_deleted_list(
        self,
        spec: QuerySpec,
        delete_level: str | None = None,
        scope: str | None = None,
        forced_filters: list[FilterRule] | None = None,
    ) -> tuple[list[ModelType], int]:
        """
        查询回收站列表 / Query recycle bin list

        Args:
            spec: 查询规格 / Query specification
            delete_level: 删除层级过滤 / Delete level filter
            scope: 作用域 / Scope
            forced_filters: 强制过滤条件 / Forced filter conditions

        Returns:
            (数据列表, 总数) / (data list, total count)
        """
        return await self.repo.query_deleted(
            spec=spec,
            delete_level=delete_level,
            scope=scope,
            forced_filters=forced_filters,
        )

    async def count_deleted(self, delete_level: str | None = None) -> int:
        """统计回收站记录数量 / Count recycle bin records"""
        return await self.repo.count_deleted(delete_level=delete_level)

    async def restore(self, id: int) -> ModelType | None:
        """
        恢复已删除记录 / Restore a deleted record

        自动级联恢复 __delete_deps__ 中 CASCADE_SOFT 声明的子记录。
        Automatically cascades restore to child records declared as CASCADE_SOFT in __delete_deps__.

        Args:
            id: 记录 ID / Record ID

        Returns:
            恢复后的模型实例或 None / Restored model instance or None
        """
        await self._before_restore(id)
        instance = await self.repo.restore_by_id(id)
        if instance:
            tenant_id = getattr(self, "tenant_id", None)
            await execute_cascade_restore(self.db, instance, tenant_id=tenant_id)
            await self._after_restore(instance)
        return instance

    async def escalate_delete(self, id: int) -> ModelType | None:
        """
        升级删除层级 / Escalate delete level (tenant → admin)

        自动级联升级 __delete_deps__ 中 CASCADE_SOFT 声明的子记录。
        Automatically cascades escalation to child records declared as CASCADE_SOFT in __delete_deps__.

        Args:
            id: 记录 ID / Record ID

        Returns:
            更新后的模型实例或 None / Updated model instance or None
        """
        instance = await self.repo.escalate_delete_by_id(id)
        if instance is not None:
            tenant_id = getattr(self, "tenant_id", None)
            await execute_cascade_escalate(self.db, instance, tenant_id=tenant_id)
        return instance

    async def permanent_delete(self, id: int) -> bool:
        """
        永久删除记录 / Permanently delete a record

        Args:
            id: 记录 ID / Record ID

        Returns:
            是否删除成功 / Whether deletion was successful
        """
        await self._before_permanent_delete(id)
        return await self.repo.permanent_delete(id)

    async def batch_restore(self, ids: list[int]) -> int:
        """批量恢复（逐条执行，触发级联恢复） / Batch restore (per-item to trigger cascade)"""
        count = 0
        for item_id in ids:
            result = await self.restore(item_id)
            if result:
                count += 1
        return count

    async def batch_permanent_delete(self, ids: list[int]) -> int:
        """批量永久删除（逐条执行，触发级联删除） / Batch permanent delete (per-item to trigger cascade)"""
        count = 0
        for item_id in ids:
            result = await self.permanent_delete(item_id)
            if result:
                count += 1
        return count

    # ========================================
    # 通用排序方法 / Generic Sort Methods
    # ========================================

    def _get_sortable_config(self) -> dict[str, Any] | None:
        """
        获取模型的排序配置 / Get model's sort configuration

        Returns:
            排序配置字典或 None / Sort config dict or None
        """
        return getattr(self.model, "__sortable__", None)

    async def _auto_set_sort_order(self, data: dict[str, Any]) -> None:
        """
        自动设置排序值

        如果模型配置了 __sortable__ 且包含排序字段配置（"field" 键），
        且模型实际拥有该排序字段，才自动计算排序值。

        注意：__sortable__ 有两种用法：
        1. 排序配置: {"field": "sort_order", "step": 1000, "scope_fields": []}
        2. 字段白名单: {"id": "id", "name": "name", ...}（仅用于 JSON:API 排序）
        只有第一种才需要自动设置排序值。

        Args:
            data: 创建数据字典（可修改）
        """
        sortable = self._get_sortable_config()
        if not sortable:
            return

        # 只有包含 "field" 键的才是排序配置，否则只是字段白名单
        if "field" not in sortable:
            return

        sort_field = sortable.get("field", "sort_order")
        scope_fields = sortable.get("scope_fields", [])

        # 模型上必须有该排序字段
        if not hasattr(self.model, sort_field):
            return

        # 检查是否已传入有效的排序值
        current_value = data.get(sort_field)
        if current_value is not None and current_value > 0:
            return  # 已传入有效值，不自动计算

        # 构建作用域过滤条件
        scope_filters = {}
        for field in scope_fields:
            if field in data:
                scope_filters[field] = data[field]

        # 计算下一个排序值
        next_value = await self.repo.get_next_sort_order(**scope_filters)
        data[sort_field] = next_value

    async def reorder(
        self,
        ordered_ids: list[int],
        **scope_filters: Any,
    ) -> int:
        """
        批量重排序 / Batch reorder

        按 ordered_ids 顺序重新分配排序值
        Reassign sort values in ordered_ids order.

        Args:
            ordered_ids: 有序的 ID 列表 / Ordered list of IDs
            **scope_filters: 作用域过滤条件 / Scope filter conditions

        Returns:
            更新的记录数 / Number of updated records

        Raises:
            ValueError: 模型未配置 __sortable__ / Model has no __sortable__ config
        """
        return await self.repo.batch_update_sort_order(ordered_ids, **scope_filters)


    # ========================================
    # 声明式依赖保护（内部方法） / Declarative Dependency Protection (internal)
    # ========================================

    async def preview_delete(self, id: int) -> dict:
        """
        Preview deletion impact without performing the delete.
        预览删除影响（不执行删除）。

        Returns:
            {
                "blocked": bool,
                "blockers": [...],
                "cascade_soft": [...],
                "cascade_delete": [...],
                "nullify": [...]
            }
        """
        instance = await self.repo.get_by_id(id)
        if not instance:
            return {"blocked": False, "blockers": [], "cascade_soft": [], "cascade_delete": [], "nullify": []}

        tenant_id = getattr(self, "tenant_id", None)
        result = await check_deletion_deps(self.db, instance, tenant_id=tenant_id)

        def _dep_to_dict(info) -> dict:
            return {
                "type": info.model_name,
                "count": info.count,
                "items": info.items,
                "strategy": info.strategy,
            }

        return {
            "blocked": result.blocked,
            "blockers": [_dep_to_dict(b) for b in result.blockers],
            "cascade_soft": [_dep_to_dict(d) for d in result.cascade_soft],
            "cascade_delete": [_dep_to_dict(d) for d in result.cascade_delete],
            "nullify": [_dep_to_dict(d) for d in result.nullify],
        }

    async def _check_deletion_deps(self, instance: ModelType) -> None:
        """
        读取 __delete_deps__ 声明，检查 BLOCK 策略依赖。
        Read __delete_deps__ declaration and check BLOCK strategy dependencies.

        如果存在活跃依赖，抛出 DependencyBlockedException。
        Raises DependencyBlockedException if active dependencies exist.
        无 __delete_deps__ 声明时静默跳过。 / Silently skips when no __delete_deps__ declared.
        """
        deps = getattr(instance.__class__, "__delete_deps__", None)
        if not deps:
            return

        from app.core.i18n import _

        tenant_id = getattr(self, "tenant_id", None)
        result = await check_deletion_deps(
            self.db, instance, tenant_id=tenant_id,
        )
        if result.blocked:
            raise DependencyBlockedException(
                message=_("common.error.has_dependencies"),
                dependencies=[
                    {
                        "type": b.model_name,
                        "count": b.count,
                        "items": b.items,
                    }
                    for b in result.blockers
                ],
            )

    async def _execute_deletion_cascade(self, instance: ModelType) -> None:
        """
        执行 __delete_deps__ 中的非 BLOCK 级联操作。
        Execute non-BLOCK cascade operations from __delete_deps__.

        在 soft_delete 之后调用。 / Called after soft_delete.
        无 __delete_deps__ 声明时静默跳过。 / Silently skips when no __delete_deps__ declared.
        """
        deps = getattr(instance.__class__, "__delete_deps__", None)
        if not deps:
            return

        tenant_id = getattr(self, "tenant_id", None)
        stats = await execute_cascade_deps(
            self.db,
            instance,
            delete_level=self._default_delete_level,
            tenant_id=tenant_id,
        )
        if stats:
            _logger.info(
                "Deletion cascade for %s#%d: %s",
                instance.__class__.__name__, instance.id, stats,
            )


class TenantService(BaseService[ModelType, RepoType]):
    """
    企业级服务基类 / Tenant Service Base Class

    自动注入企业隔离逻辑
    Automatically injects tenant isolation logic.
    """

    _default_delete_level: str = DeleteLevelEnum.TENANT.value

    def __init__(self, db: AsyncSession, tenant_id: int | None):
        """
        初始化企业服务 / Initialize tenant service

        Args:
            db: 异步数据库会话 / Async database session
            tenant_id: 企业 ID / Tenant ID (None for global/admin resources)
        """
        self.db = db
        self.tenant_id = tenant_id
        self.repo: RepoType = self.repository_class(db, tenant_id)

    async def _before_create(self, data: dict[str, Any]) -> None:
        """创建前自动注入 tenant_id / Auto-inject tenant_id before create"""
        await super()._before_create(data)
        data["tenant_id"] = self.tenant_id


class GlobalService(BaseService[ModelType, RepoType]):
    """
    全局服务基类 / Global Service Base Class

    用于超管或系统级操作，无企业隔离
    Used for super-admin or system-level operations, no tenant isolation.
    """
    pass


# 导出 / Exports
__all__ = ["BaseService", "TenantService", "GlobalService"]
