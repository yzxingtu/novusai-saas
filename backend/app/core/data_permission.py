"""
数据权限过滤模块 / Data Permission Filter Module

根据角色 data_scope 对查询结果进行行级过滤。
Row-level filtering based on role data_scope.
仅对声明 __data_permission__ = True 的 Model 生效。
Only applies to models with __data_permission__ = True.
"""

from contextvars import ContextVar
from typing import Any

from sqlalchemy import false
from sqlalchemy.sql import Select

from app.enums.role import DataScope

# 数据权限上下文（由 PermissionMiddleware 填充） / Data permission context (filled by PermissionMiddleware)
data_permission_ctx: ContextVar[dict[str, Any]] = ContextVar(
    "data_permission_ctx", default={}
)


class DataPermissionFilter:
    """
    数据权限过滤器 / Data permission filter

    根据当前用户的 max_data_scope、all_visible_dept_ids、custom_dept_ids 自动添加 WHERE 条件。
    Adds WHERE clauses based on current user's data permission attributes.
    """

    @staticmethod
    def apply(query: Select, model: type, current_user_id: int | None) -> Select:
        """
        根据数据权限范围添加过滤条件 / Add filter conditions by data scope

        Args:
            query: SQLAlchemy Select 查询 / Select query
            model: 模型类（需有 created_by、dept_id 字段） / Model class
            current_user_id: 当前用户 ID（SELF_ONLY 时用） / Current user ID for SELF_ONLY

        Returns:
            添加过滤条件后的查询 / Query with filters applied
        """
        ctx = data_permission_ctx.get()
        data_scope = ctx.get("max_data_scope", DataScope.ALL.value)
        all_visible_dept_ids = ctx.get("all_visible_dept_ids") or []
        custom_dept_ids = ctx.get("custom_dept_ids") or []

        if data_scope == DataScope.ALL.value:
            return query

        if data_scope == DataScope.SELF_ONLY.value:
            if not hasattr(model, "created_by"):
                return query.where(false())
            if current_user_id is None:
                return query.where(false())
            return query.where(model.created_by == current_user_id)

        if data_scope in (DataScope.DEPT_ONLY.value, DataScope.DEPT_AND_CHILDREN.value):
            if not hasattr(model, "dept_id"):
                return query.where(false())
            if not all_visible_dept_ids:
                return query.where(false())
            return query.where(model.dept_id.in_(all_visible_dept_ids))

        if data_scope == DataScope.CUSTOM.value:
            if not hasattr(model, "dept_id"):
                return query.where(false())
            if not custom_dept_ids:
                return query.where(false())
            return query.where(model.dept_id.in_(custom_dept_ids))

        return query.where(false())
