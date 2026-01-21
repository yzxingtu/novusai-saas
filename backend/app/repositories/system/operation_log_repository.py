"""
操作日志仓储

提供操作日志的数据访问操作
"""

from datetime import datetime
from typing import Any

from sqlalchemy import select, func, delete

from app.core.base_repository import BaseRepository
from app.enums.log import UserTypeEnum
from app.models.system.operation_log import OperationLog
from app.schemas.common.query import FilterRule, QuerySpec


class OperationLogRepository(BaseRepository[OperationLog]):
    """
    操作日志仓储
    
    提供操作日志的数据访问方法，支持：
    - admin 作用域：平台管理员可查看所有日志
    - tenant 作用域：租户管理员仅可查看本租户日志
    """
    
    model = OperationLog
    
    # 按 scope 限制可过滤字段
    _scope_fields = {
        # 平台管理员可过滤的字段
        "admin": {
            "id", "tenant_id", "user_type", "user_id", "username",
            "module", "action", "resource", "method", "path",
            "response_code", "ip", "created_at",
        },
        # 租户管理员可过滤的字段（不包含 tenant_id）
        "tenant": {
            "id", "user_type", "user_id", "username",
            "module", "action", "resource", "method", "path",
            "response_code", "ip", "created_at",
        },
    }
    
    async def create_log(self, data: dict[str, Any]) -> OperationLog:
        """
        创建操作日志记录
        
        Args:
            data: 日志数据字典
        
        Returns:
            创建的日志实例
        """
        return await self.create(data)
    
    async def query_tenant_logs(
        self,
        tenant_id: int,
        spec: QuerySpec,
    ) -> tuple[list[OperationLog], int]:
        """
        查询租户操作日志
        
        自动添加租户隔离过滤
        
        Args:
            tenant_id: 租户 ID
            spec: 查询规格
        
        Returns:
            (日志列表, 总数)
        """
        # 强制添加租户过滤
        tenant_filter = FilterRule(field="tenant_id", value=tenant_id)
        
        return await self.query_list(
            spec=spec,
            scope="tenant",
            forced_filters=[tenant_filter],
        )
    
    async def delete_logs_by_ids(
        self,
        ids: list[int],
        soft: bool = True,
    ) -> int:
        """
        批量删除日志
        
        Args:
            ids: 日志 ID 列表
            soft: 是否软删除（默认 True）
        
        Returns:
            删除的记录数
        """
        return await self.delete_many(ids, soft=soft)
    
    async def delete_logs_before(
        self,
        before_date: datetime,
        tenant_id: int | None = None,
        hard_delete: bool = False,
    ) -> int:
        """
        删除指定日期之前的日志
        
        用于日志清理任务
        
        Args:
            before_date: 日期阈值
            tenant_id: 租户 ID（可选，为空则删除所有租户）
            hard_delete: 是否硬删除
        
        Returns:
            删除的记录数
        """
        if hard_delete:
            stmt = delete(self.model).where(
                self.model.created_at < before_date
            )
            if tenant_id is not None:
                stmt = stmt.where(self.model.tenant_id == tenant_id)
        else:
            from sqlalchemy import update
            stmt = (
                update(self.model)
                .where(
                    self.model.created_at < before_date,
                    self.model.is_deleted == False,
                )
                .values(is_deleted=True)
            )
            if tenant_id is not None:
                stmt = stmt.where(self.model.tenant_id == tenant_id)
        
        result = await self.db.execute(stmt)
        return result.rowcount
    
    async def get_stats_by_module(
        self,
        tenant_id: int | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """
        按模块统计日志数量
        
        Args:
            tenant_id: 租户 ID（可选）
            start_date: 开始日期（可选）
            end_date: 结束日期（可选）
        
        Returns:
            统计结果列表 [{"module": "auth", "count": 100}, ...]
        """
        query = (
            select(
                self.model.module,
                func.count(self.model.id).label("count")
            )
            .where(self.model.is_deleted == False)
            .group_by(self.model.module)
        )
        
        if tenant_id is not None:
            query = query.where(self.model.tenant_id == tenant_id)
        
        if start_date:
            query = query.where(self.model.created_at >= start_date)
        
        if end_date:
            query = query.where(self.model.created_at <= end_date)
        
        result = await self.db.execute(query)
        rows = result.all()
        
        return [{"module": row.module, "count": row.count} for row in rows]
    
    async def get_stats_by_action(
        self,
        tenant_id: int | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """
        按操作类型统计日志数量
        
        Args:
            tenant_id: 租户 ID（可选）
            start_date: 开始日期（可选）
            end_date: 结束日期（可选）
        
        Returns:
            统计结果列表 [{"action": "create", "count": 50}, ...]
        """
        query = (
            select(
                self.model.action,
                func.count(self.model.id).label("count")
            )
            .where(self.model.is_deleted == False)
            .group_by(self.model.action)
        )
        
        if tenant_id is not None:
            query = query.where(self.model.tenant_id == tenant_id)
        
        if start_date:
            query = query.where(self.model.created_at >= start_date)
        
        if end_date:
            query = query.where(self.model.created_at <= end_date)
        
        result = await self.db.execute(query)
        rows = result.all()
        
        return [{"action": row.action, "count": row.count} for row in rows]
    
    async def query_admin_logs_with_hierarchy(
        self,
        spec: QuerySpec,
        is_super: bool,
        subordinate_user_ids: list[int] | None = None,
    ) -> tuple[list[OperationLog], int]:
        """
        平台端带层级权限的日志查询
        
        Args:
            spec: 查询规格
            is_super: 是否超级管理员
            subordinate_user_ids: 下属用户 ID 列表（非超管时必须）
        
        Returns:
            (日志列表, 总数)
        """
        # 强制只查看平台端日志
        user_type_filter = FilterRule(
            field="user_type", 
            value=UserTypeEnum.ADMIN.value,
        )
        forced_filters = [user_type_filter]
        
        # 非超管需要限制只能看下属的日志
        if not is_super and subordinate_user_ids is not None:
            user_id_filter = FilterRule(
                field="user_id",
                operator="in",
                value=subordinate_user_ids,
            )
            forced_filters.append(user_id_filter)
        
        return await self.query_list(
            spec=spec,
            scope="admin",
            forced_filters=forced_filters,
        )
    
    async def query_tenant_logs_with_hierarchy(
        self,
        tenant_id: int,
        spec: QuerySpec,
        is_owner: bool,
        subordinate_user_ids: list[int] | None = None,
        include_tenant_users: bool = True,
    ) -> tuple[list[OperationLog], int]:
        """
        租户端带层级权限的日志查询
        
        Args:
            tenant_id: 租户 ID
            spec: 查询规格
            is_owner: 是否租户所有者
            subordinate_user_ids: 下属用户 ID 列表（非所有者时必须）
            include_tenant_users: 是否包含租户普通用户日志
        
        Returns:
            (日志列表, 总数)
        """
        # 强制租户隔离
        tenant_filter = FilterRule(field="tenant_id", value=tenant_id)
        
        # 限制只查看租户端日志（tenant_admin / tenant_user）
        allowed_user_types = [UserTypeEnum.TENANT_ADMIN.value]
        if include_tenant_users:
            allowed_user_types.append(UserTypeEnum.TENANT_USER.value)
        
        user_type_filter = FilterRule(
            field="user_type",
            operator="in",
            value=allowed_user_types,
        )
        
        forced_filters = [tenant_filter, user_type_filter]
        
        # 非所有者需要限制只能看下属的日志
        if not is_owner and subordinate_user_ids is not None:
            user_id_filter = FilterRule(
                field="user_id",
                operator="in",
                value=subordinate_user_ids,
            )
            forced_filters.append(user_id_filter)
        
        return await self.query_list(
            spec=spec,
            scope="tenant",
            forced_filters=forced_filters,
        )


__all__ = ["OperationLogRepository"]
