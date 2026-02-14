"""
服务基类模块

提供业务逻辑层的基类，包括：
- BaseService: 通用服务基类
- TenantService: 租户级服务基类
- GlobalService: 全局服务基类
"""

from __future__ import annotations

from typing import Any, Generic, TypeVar, Type

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_model import BaseModel
from app.core.base_repository import BaseRepository, TenantRepository
from app.core.base_schema import PageParams, PageResponse
from app.schemas.common.query import QuerySpec, FilterRule
from app.schemas.common.select import SelectOption, SelectResponse

# 泛型类型变量
ModelType = TypeVar("ModelType", bound=BaseModel)
RepoType = TypeVar("RepoType", bound=BaseRepository)


class BaseService(Generic[ModelType, RepoType]):
    """
    服务基类
    
    提供通用的业务方法和扩展点（钩子方法）
    
    使用示例:
        class UserService(BaseService[User, UserRepository]):
            model = User
            repository_class = UserRepository
    """
    
    model: Type[ModelType]
    repository_class: Type[RepoType]
    
    def __init__(self, db: AsyncSession):
        """
        初始化服务
        
        Args:
            db: 异步数据库会话
        """
        self.db = db
        self.repo: RepoType = self.repository_class(db)
    
    # ========================================
    # 通用 CRUD 方法
    # ========================================
    
    async def get_by_id(self, id: int) -> ModelType | None:
        """
        根据 ID 获取记录
        
        Args:
            id: 记录 ID
        
        Returns:
            模型实例或 None
        """
        return await self.repo.get_by_id(id)
    
    async def get_by_ids(self, ids: list[int]) -> list[ModelType]:
        """
        根据 ID 列表获取记录
        
        Args:
            ids: ID 列表
        
        Returns:
            模型实例列表
        """
        return await self.repo.get_by_ids(ids)
    
    async def get_list(
        self,
        skip: int = 0,
        limit: int = 100,
        **filters: Any,
    ) -> list[ModelType]:
        """
        获取记录列表
        
        Args:
            skip: 跳过的记录数
            limit: 返回的最大记录数
            **filters: 过滤条件
        
        Returns:
            模型实例列表
        """
        return await self.repo.get_list(skip=skip, limit=limit, **filters)
    
    async def get_paginated(
        self,
        page_params: PageParams,
        **filters: Any,
    ) -> PageResponse[ModelType]:
        """
        获取分页记录
        
        Args:
            page_params: 分页参数
            **filters: 过滤条件
        
        Returns:
            分页响应
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
        统计记录数量
        
        Args:
            **filters: 过滤条件
        
        Returns:
            记录数量
        """
        return await self.repo.count(**filters)
    
    async def create(self, data: dict[str, Any]) -> ModelType:
        """
        创建记录
        
        Args:
            data: 创建数据字典
        
        Returns:
            创建的模型实例
        """
        # 创建前钩子
        await self._before_create(data)
        
        # 执行创建
        instance = await self.repo.create(data)
        
        # 创建后钩子
        await self._after_create(instance)
        
        return instance
    
    async def update(self, id: int, data: dict[str, Any]) -> ModelType | None:
        """
        更新记录
        
        Args:
            id: 记录 ID
            data: 更新数据字典
        
        Returns:
            更新后的模型实例或 None
        """
        # 更新前钩子
        await self._before_update(id, data)
        
        # 执行更新
        instance = await self.repo.update(id, data)
        
        # 更新后钩子
        if instance:
            await self._after_update(instance)
        
        return instance
    
    # 软删除默认层级，子类覆盖
    _default_delete_level: str = "admin"

    async def delete(self, id: int, soft: bool = True) -> bool:
        """
        删除记录（软删除时进入回收站）
        
        Args:
            id: 记录 ID
            soft: 是否软删除（默认 True）
        
        Returns:
            是否删除成功
        """
        # 删除前钩子
        await self._before_delete(id)
        
        if soft:
            instance = await self.repo.get_by_id(id)
            if instance is None:
                return False
            instance.soft_delete(level=self._default_delete_level)
            await self.repo.db.flush()
        else:
            result = await self.repo.delete(id, soft=False)
            if not result:
                return False
        
        # 删除后钩子
        await self._after_delete(id)
        
        return True
    
    async def exists(self, id: int) -> bool:
        """
        检查记录是否存在
        
        Args:
            id: 记录 ID
        
        Returns:
            是否存在
        """
        return await self.repo.exists(id)
    
    async def query_list(
        self,
        spec: QuerySpec,
        scope: str | None = None,
        forced_filters: list[FilterRule] | None = None,
    ) -> tuple[list[ModelType], int]:
        """
        通用列表查询
        
        支持 JSON:API 风格筛选、排序、分页
        
        Args:
            spec: 查询规格（包含 filters/sort/page/size）
            scope: 作用域，用于按端限制可过滤字段
            forced_filters: 强制过滤条件
        
        Returns:
            (数据列表, 总数)
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
    # 钩子方法（子类可重写）
    # ========================================
    
    async def _before_create(self, data: dict[str, Any]) -> None:
        """
        创建前钩子
        
        可用于：数据校验、默认值注入、权限检查等
        
        自动处理:
        - 如果模型配置了 __sortable__ 且未传入排序值，自动计算
        
        Args:
            data: 创建数据字典（可修改）
        """
        # 自动计算排序值
        await self._auto_set_sort_order(data)
    
    async def _after_create(self, instance: ModelType) -> None:
        """
        创建后钩子
        
        可用于：发送事件、记录日志、触发通知等
        
        Args:
            instance: 创建的模型实例
        """
        pass
    
    async def _before_update(self, id: int, data: dict[str, Any]) -> None:
        """
        更新前钩子
        
        可用于：数据校验、权限检查、记录变更等
        
        Args:
            id: 记录 ID
            data: 更新数据字典（可修改）
        """
        pass
    
    async def _after_update(self, instance: ModelType) -> None:
        """
        更新后钩子
        
        可用于：发送事件、记录日志、同步缓存等
        
        Args:
            instance: 更新后的模型实例
        """
        pass
    
    async def _before_delete(self, id: int) -> None:
        """
        删除前钩子
        
        可用于：关联检查、权限验证等
        
        Args:
            id: 记录 ID
        """
        pass
    
    async def _after_delete(self, id: int) -> None:
        """
        删除后钩子
        
        可用于：清理关联数据、记录日志等
        
        Args:
            id: 已删除的记录 ID
        """
        pass
    
    # ========================================
    # 回收站钩子方法（子类可重写）
    # ========================================

    async def _before_restore(self, id: int) -> None:
        """恢复前钩子"""
        pass

    async def _after_restore(self, instance: ModelType) -> None:
        """恢复后钩子"""
        pass

    async def _before_permanent_delete(self, id: int) -> None:
        """永久删除前钩子"""
        pass

    # ========================================
    # 回收站方法
    # ========================================

    async def query_deleted_list(
        self,
        spec: QuerySpec,
        delete_level: str | None = None,
        scope: str | None = None,
        forced_filters: list[FilterRule] | None = None,
    ) -> tuple[list[ModelType], int]:
        """
        查询回收站列表

        Args:
            spec: 查询规格
            delete_level: 删除层级过滤
            scope: 作用域
            forced_filters: 强制过滤条件

        Returns:
            (数据列表, 总数)
        """
        return await self.repo.query_deleted(
            spec=spec,
            delete_level=delete_level,
            scope=scope,
            forced_filters=forced_filters,
        )

    async def count_deleted(self, delete_level: str | None = None) -> int:
        """统计回收站记录数量"""
        return await self.repo.count_deleted(delete_level=delete_level)

    async def restore(self, id: int) -> ModelType | None:
        """
        恢复已删除记录

        Args:
            id: 记录 ID

        Returns:
            恢复后的模型实例或 None
        """
        await self._before_restore(id)
        instance = await self.repo.restore_by_id(id)
        if instance:
            await self._after_restore(instance)
        return instance

    async def escalate_delete(self, id: int) -> ModelType | None:
        """
        升级删除层级（tenant → admin）

        Args:
            id: 记录 ID

        Returns:
            更新后的模型实例或 None
        """
        return await self.repo.escalate_delete_by_id(id)

    async def permanent_delete(self, id: int) -> bool:
        """
        永久删除记录

        Args:
            id: 记录 ID

        Returns:
            是否删除成功
        """
        await self._before_permanent_delete(id)
        return await self.repo.permanent_delete(id)

    async def batch_restore(self, ids: list[int]) -> int:
        """批量恢复"""
        return await self.repo.batch_restore(ids)

    async def batch_permanent_delete(self, ids: list[int]) -> int:
        """批量永久删除"""
        return await self.repo.batch_permanent_delete(ids)

    # ========================================
    # 通用排序方法
    # ========================================
    
    def _get_sortable_config(self) -> dict[str, Any] | None:
        """
        获取模型的排序配置
        
        Returns:
            排序配置字典或 None
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
        批量重排序
        
        按 ordered_ids 顺序重新分配排序值
        
        Args:
            ordered_ids: 有序的 ID 列表
            **scope_filters: 作用域过滤条件
        
        Returns:
            更新的记录数
        
        Raises:
            ValueError: 模型未配置 __sortable__
        """
        return await self.repo.batch_update_sort_order(ordered_ids, **scope_filters)


class TenantService(BaseService[ModelType, RepoType]):
    """
    租户级服务基类
    
    自动注入租户隔离逻辑
    """
    
    _default_delete_level: str = "tenant"

    def __init__(self, db: AsyncSession, tenant_id: int):
        """
        初始化租户服务
        
        Args:
            db: 异步数据库会话
            tenant_id: 租户 ID
        """
        self.db = db
        self.tenant_id = tenant_id
        self.repo: RepoType = self.repository_class(db, tenant_id)
    
    async def _before_create(self, data: dict[str, Any]) -> None:
        """创建前自动注入 tenant_id"""
        await super()._before_create(data)
        data["tenant_id"] = self.tenant_id


class GlobalService(BaseService[ModelType, RepoType]):
    """
    全局服务基类
    
    用于超管或系统级操作，无租户隔离
    """
    pass


# 导出
__all__ = ["BaseService", "TenantService", "GlobalService"]
