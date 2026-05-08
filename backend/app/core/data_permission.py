"""
数据权限过滤模块 / Data Permission Filter Module

根据组织权限上下文对查询结果进行行级过滤。
Row-level filtering based on organization authority context.
"""

from __future__ import annotations

from contextvars import ContextVar
from typing import Any

from sqlalchemy import and_, false, or_, select
from sqlalchemy.sql import ColumnElement, Select

from app.core.security import (
    TOKEN_SCOPE_ADMIN,
    TOKEN_SCOPE_TENANT_ADMIN,
    TOKEN_SCOPE_TENANT_USER,
)
from app.enums.role import DataScope
from app.models import Admin, TenantAdmin, TenantUser

# 数据权限上下文（由 PermissionMiddleware 填充） / Data permission context (filled by PermissionMiddleware)
data_permission_ctx: ContextVar[dict[str, Any] | None] = ContextVar(
    "data_permission_ctx",
    default=None,
)


def is_data_permission_enabled(model: type) -> bool:
    """
    判断模型是否启用数据权限 / Determine whether the model is data-scope aware.

    显式声明 __data_permission__ 时优先使用；否则对常见组织归属字段自动启用。
    Explicit __data_permission__ wins; otherwise auto-enable for common ownership fields.
    """
    explicit = getattr(model, "__data_permission__", None)
    if explicit is not None:
        return bool(explicit)
    if getattr(model, "__data_permission_parent_model__", None) is not None:
        return True
    return any(
        hasattr(model, field)
        for field in (
            "org_node_id",
            "dept_id",
            "created_by",
            "__data_permission_creator_field__",
        )
    )


def build_data_permission_condition(
    model: type,
    current_user_id: int | None = None,
    *,
    ctx: dict[str, Any] | None = None,
) -> ColumnElement[bool] | None:
    """构建数据权限条件 / Build data permission condition."""
    return DataPermissionFilter.build_condition(model, current_user_id, ctx=ctx)


def apply_data_permission_if_needed(query: Select, model: type) -> Select:
    """
    对启用数据权限的模型应用过滤 / Apply data scope when the model supports it.
    """
    condition = build_data_permission_condition(model)
    if condition is None:
        return query
    return query.where(condition)


def enrich_create_data_with_data_permission(
    model: type,
    data: dict[str, Any],
) -> dict[str, Any]:
    """
    根据当前权限上下文自动补全 owner / org 字段
    Auto-fill owner and org fields from current data permission context.
    """
    if not is_data_permission_enabled(model):
        return data

    ctx = data_permission_ctx.get()
    if not ctx:
        return data

    enriched = dict(data)
    creator_field_name = getattr(model, "__data_permission_creator_field__", None)
    if not creator_field_name and hasattr(model, "created_by"):
        creator_field_name = "created_by"
    if (
        creator_field_name
        and creator_field_name not in enriched
        and ctx.get("current_user_id") is not None
        and hasattr(model, creator_field_name)
    ):
        enriched[creator_field_name] = ctx["current_user_id"]
    creator_scope_field_name = getattr(
        model, "__data_permission_creator_scope_field__", None
    )
    if (
        creator_scope_field_name
        and creator_scope_field_name not in enriched
        and ctx.get("current_user_scope")
        and hasattr(model, creator_scope_field_name)
    ):
        enriched[creator_scope_field_name] = ctx["current_user_scope"]
    if (
        "org_node_id" not in enriched
        and ctx.get("primary_org_id") is not None
        and hasattr(model, "org_node_id")
    ):
        enriched["org_node_id"] = ctx["primary_org_id"]
    if (
        "dept_id" not in enriched
        and ctx.get("primary_department_id") is not None
        and hasattr(model, "dept_id")
    ):
        enriched["dept_id"] = ctx["primary_department_id"]
    return enriched


class DataPermissionFilter:
    """
    数据权限过滤器 / Data permission filter

    根据当前用户的 scope_mode、effective_scope_org_ids、custom_org_ids 自动添加 WHERE 条件。
    Adds WHERE clauses based on current user's data permission attributes.
    """

    @classmethod
    def apply(
        cls,
        query: Select,
        model: type,
        current_user_id: int | None,
        *,
        ctx: dict[str, Any] | None = None,
    ) -> Select:
        condition = cls.build_condition(model, current_user_id, ctx=ctx)
        if condition is None:
            return query
        return query.where(condition)

    @classmethod
    def build_condition(
        cls,
        model: type,
        current_user_id: int | None = None,
        *,
        ctx: dict[str, Any] | None = None,
        _seen: set[type] | None = None,
    ) -> ColumnElement[bool] | None:
        """
        根据数据权限范围构建条件 / Build condition by data scope.

        返回 None 表示当前模型不需要附加数据范围过滤。
        Returning None means the current model should not be additionally filtered.
        """
        if not is_data_permission_enabled(model):
            return None

        active_ctx = ctx or data_permission_ctx.get()
        if not active_ctx:
            return None

        if cls._should_skip_for_current_scope(model, active_ctx):
            return None

        seen = _seen or set()
        if model in seen:
            return false()
        seen.add(model)

        data_scope = active_ctx.get("scope_mode") or active_ctx.get(
            "max_data_scope",
            DataScope.ALL.value,
        )
        if data_scope == DataScope.ALL.value:
            return None

        resolved_user_id = (
            current_user_id
            if current_user_id is not None
            else active_ctx.get("current_user_id")
        )

        if data_scope == DataScope.SELF_ONLY.value:
            return cls._build_self_only_condition(
                model, resolved_user_id, active_ctx, seen
            )

        effective_scope_org_ids = (
            active_ctx.get("effective_scope_org_ids")
            or active_ctx.get("visible_org_ids")
            or active_ctx.get("all_visible_dept_ids")
            or []
        )
        custom_org_ids = (
            active_ctx.get("custom_org_ids") or active_ctx.get("custom_dept_ids") or []
        )

        if data_scope in (DataScope.DEPT_ONLY.value, DataScope.DEPT_AND_CHILDREN.value):
            target_org_ids = list(effective_scope_org_ids)
        elif data_scope == DataScope.CUSTOM.value:
            target_org_ids = list(custom_org_ids or effective_scope_org_ids)
        else:
            return false()

        return cls._build_org_scope_condition(
            model, target_org_ids, active_ctx, resolved_user_id, seen
        )

    @classmethod
    def _build_self_only_condition(
        cls,
        model: type,
        current_user_id: int | None,
        ctx: dict[str, Any],
        seen: set[type],
    ) -> ColumnElement[bool]:
        creator_field = cls._resolve_creator_field(model)
        if creator_field is not None:
            if current_user_id is None:
                return false()
            predicate = creator_field == current_user_id
            creator_scope_field = cls._resolve_creator_scope_field(model)
            current_user_scope = ctx.get("current_user_scope")
            if creator_scope_field is not None and current_user_scope:
                predicate = and_(predicate, creator_scope_field == current_user_scope)
            return predicate

        parent_condition = cls._build_parent_scope_condition(
            model,
            current_user_id,
            ctx,
            seen,
        )
        return parent_condition if parent_condition is not None else false()

    @classmethod
    def _build_org_scope_condition(
        cls,
        model: type,
        target_org_ids: list[int],
        ctx: dict[str, Any],
        current_user_id: int | None,
        seen: set[type],
    ) -> ColumnElement[bool]:
        if not target_org_ids:
            return false()

        org_field = cls._resolve_org_field(model)
        if org_field is not None:
            return org_field.in_(target_org_ids)

        creator_scope_condition = cls._build_creator_scope_condition(
            model,
            target_org_ids,
            ctx,
        )
        if creator_scope_condition is not None:
            return creator_scope_condition

        parent_condition = cls._build_parent_scope_condition(
            model,
            current_user_id,
            ctx,
            seen,
        )
        if parent_condition is not None:
            return parent_condition

        return false()

    @staticmethod
    def _should_skip_for_current_scope(model: type, ctx: dict[str, Any]) -> bool:
        explicit_scope = getattr(model, "__data_permission_creator_scope__", None)
        current_scope = ctx.get("current_user_scope")
        if explicit_scope and current_scope and explicit_scope != current_scope:
            return True

        scope_field = getattr(model, "__data_permission_creator_scope_field__", None)
        allowed_scopes = getattr(model, "__data_permission_creator_scopes__", None)
        return bool(
            scope_field
            and allowed_scopes
            and current_scope
            and current_scope not in allowed_scopes
        )

    @staticmethod
    def _resolve_org_field(model: type):
        if hasattr(model, "org_node_id"):
            return model.org_node_id
        if hasattr(model, "dept_id"):
            return model.dept_id
        return None

    @staticmethod
    def _resolve_creator_field(model: type):
        field_name = getattr(model, "__data_permission_creator_field__", None)
        if field_name and hasattr(model, field_name):
            return getattr(model, field_name)
        if hasattr(model, "created_by"):
            return model.created_by
        return None

    @staticmethod
    def _resolve_creator_scope_field(model: type):
        field_name = getattr(model, "__data_permission_creator_scope_field__", None)
        if field_name and hasattr(model, field_name):
            return getattr(model, field_name)
        return None

    @classmethod
    def _build_creator_scope_condition(
        cls,
        model: type,
        target_org_ids: list[int],
        ctx: dict[str, Any],
    ) -> ColumnElement[bool] | None:
        creator_field = cls._resolve_creator_field(model)
        if creator_field is None:
            return None

        creator_scope_field = cls._resolve_creator_scope_field(model)
        if creator_scope_field is not None:
            predicates = []
            for creator_scope in getattr(
                model,
                "__data_permission_creator_scopes__",
                [TOKEN_SCOPE_ADMIN, TOKEN_SCOPE_TENANT_ADMIN, TOKEN_SCOPE_TENANT_USER],
            ):
                creator_stmt = cls._build_creator_id_subquery(
                    creator_scope=creator_scope,
                    target_org_ids=target_org_ids,
                    current_tenant_id=ctx.get("current_tenant_id"),
                )
                if creator_stmt is None:
                    continue
                predicates.append(
                    and_(
                        creator_scope_field == creator_scope,
                        creator_field.in_(creator_stmt),
                    )
                )
            return or_(*predicates) if predicates else None

        creator_scope = getattr(
            model, "__data_permission_creator_scope__", None
        ) or ctx.get("current_user_scope")
        creator_stmt = cls._build_creator_id_subquery(
            creator_scope=creator_scope,
            target_org_ids=target_org_ids,
            current_tenant_id=ctx.get("current_tenant_id"),
        )
        if creator_stmt is None:
            return None
        return creator_field.in_(creator_stmt)

    @classmethod
    def _build_parent_scope_condition(
        cls,
        model: type,
        current_user_id: int | None,
        ctx: dict[str, Any],
        seen: set[type],
    ) -> ColumnElement[bool] | None:
        parent_model = getattr(model, "__data_permission_parent_model__", None)
        local_key = getattr(model, "__data_permission_parent_key__", None)
        remote_key = getattr(model, "__data_permission_parent_remote_key__", "id")

        if parent_model is None or not local_key:
            return None
        if not hasattr(model, local_key) or not hasattr(parent_model, remote_key):
            return None

        parent_condition = cls.build_condition(
            parent_model,
            current_user_id,
            ctx=ctx,
            _seen=seen,
        )
        if parent_condition is None:
            return None

        parent_stmt = select(getattr(parent_model, remote_key))
        if hasattr(parent_model, "is_deleted"):
            parent_stmt = parent_stmt.where(parent_model.is_deleted.is_(False))
        parent_stmt = cls._apply_parent_tenant_scope(parent_stmt, parent_model, ctx)
        parent_stmt = parent_stmt.where(parent_condition)
        return getattr(model, local_key).in_(parent_stmt)

    @staticmethod
    def _apply_parent_tenant_scope(
        stmt: Select,
        parent_model: type,
        ctx: dict[str, Any],
    ) -> Select:
        tenant_id = ctx.get("current_tenant_id")
        if tenant_id is None:
            return stmt
        if hasattr(parent_model, "tenant_id"):
            return stmt.where(parent_model.tenant_id == tenant_id)
        if hasattr(parent_model, "owner_tenant_id"):
            return stmt.where(parent_model.owner_tenant_id == tenant_id)
        return stmt

    @staticmethod
    def _build_creator_id_subquery(
        *,
        creator_scope: str | None,
        target_org_ids: list[int],
        current_tenant_id: int | None,
    ):
        if creator_scope == TOKEN_SCOPE_ADMIN:
            return select(Admin.id).where(
                Admin.is_deleted.is_(False),
                Admin.is_active.is_(True),
                Admin.org_node_id.in_(target_org_ids),
            )

        if creator_scope == TOKEN_SCOPE_TENANT_ADMIN:
            if current_tenant_id is None:
                return None
            return select(TenantAdmin.id).where(
                TenantAdmin.is_deleted.is_(False),
                TenantAdmin.is_active.is_(True),
                TenantAdmin.tenant_id == current_tenant_id,
                TenantAdmin.org_node_id.in_(target_org_ids),
            )

        if creator_scope == TOKEN_SCOPE_TENANT_USER:
            if current_tenant_id is None:
                return None
            return select(TenantUser.id).where(
                TenantUser.is_deleted.is_(False),
                TenantUser.is_active.is_(True),
                TenantUser.tenant_id == current_tenant_id,
                TenantUser.org_node_id.in_(target_org_ids),
            )

        return None


__all__ = [
    "DataPermissionFilter",
    "apply_data_permission_if_needed",
    "build_data_permission_condition",
    "data_permission_ctx",
    "enrich_create_data_with_data_permission",
    "is_data_permission_enabled",
]
