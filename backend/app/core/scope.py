"""
统一作用域判定工具 / Unified Scope Determination Utility

提供全平台通用的作用域可见性判定方法，替代各模块零散的 scope 判定逻辑。
Provides platform-wide scope visibility determination methods, replacing scattered scope logic.

注意区分 / Note: This module handles 「Resource Scope」(ResourceScopeEnum), unrelated to:
  - JWT Token Scope (TOKEN_SCOPE_ADMIN etc.) — 认证身份标识 / Authentication identity
  - ASGI Scope (Starlette.types.Scope) — HTTP 请求元数据 / HTTP request metadata
  - BaseRepository._scope_fields — API 端字段过滤标识 / API endpoint field filter identifier
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.enums.common import ResourceScopeEnum

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


# 管理端可见的 scope 集合 / Admin-visible scope set
_ADMIN_VISIBLE_SCOPES = frozenset({
    ResourceScopeEnum.ADMIN_ONLY.value,
    ResourceScopeEnum.ADMIN_AND_ALL.value,
    ResourceScopeEnum.ADMIN_AND_ASSIGNED.value,
})

# 所有企业可见的 scope 集合（无需分配表） / All-tenants-visible scope set (no assignment table needed)
_ALL_TENANTS_VISIBLE_SCOPES = frozenset({
    ResourceScopeEnum.ALL_TENANTS.value,
    ResourceScopeEnum.ADMIN_AND_ALL.value,
})

# 需要企业分配表的 scope 集合 / Scopes requiring tenant assignment table
_ASSIGNMENT_REQUIRED_SCOPES = frozenset({
    ResourceScopeEnum.ASSIGNED_TENANTS.value,
    ResourceScopeEnum.ADMIN_AND_ASSIGNED.value,
})

# 企业端可能可见的 scope 集合（全部企业 + 部分企业） / Tenant-possibly-visible scopes (all + assigned)
_TENANT_POSSIBLE_SCOPES = _ALL_TENANTS_VISIBLE_SCOPES | _ASSIGNMENT_REQUIRED_SCOPES


class ScopeChecker:
    """
    统一作用域判定工具 / Unified Scope Checker

    所有需要判断资源可见性的代码统一调用此类的静态方法，
    避免各模块各自硬编码 scope 判定逻辑。
    All code requiring resource visibility checks should call this class's static methods,
    avoiding scattered hardcoded scope logic across modules.

    Usage::

        from app.core.scope import ScopeChecker

        # 管理端是否可见
        if ScopeChecker.is_visible_to_admin(resource.scope):
            ...

        # 企业端是否可见（需要异步查分配表）
        if await ScopeChecker.is_visible_to_tenant(
            scope=resource.scope,
            resource_type="skill_package",
            resource_id=resource.id,
            tenant_id=tenant_id,
            db=db,
        ):
            ...
    """

    @staticmethod
    def is_visible_to_admin(scope: str) -> bool:
        """
        管理端是否可见 / Whether visible to admin

        admin_only / admin_and_all / admin_and_assigned → True
        all_tenants / assigned_tenants → False
        """
        return scope in _ADMIN_VISIBLE_SCOPES

    @staticmethod
    def is_visible_to_all_tenants(scope: str) -> bool:
        """
        是否对所有企业可见（无需分配表查询） / Whether visible to all tenants (no assignment query needed)

        all_tenants / admin_and_all → True
        其他 / Others → False
        """
        return scope in _ALL_TENANTS_VISIBLE_SCOPES

    @staticmethod
    async def is_visible_to_tenant(
        scope: str,
        resource_type: str,
        resource_id: int,
        tenant_id: int,
        db: AsyncSession,
    ) -> bool:
        """
        指定企业是否可见 / Whether visible to a specific tenant

        - all_tenants / admin_and_all → True（全部企业可见 / visible to all tenants）
        - assigned_tenants / admin_and_assigned → 查 ResourceTenantAssignment / check assignment table
        - admin_only → False

        Args:
            scope: 资源的作用域值 / Resource scope value
            resource_type: 资源类型（如 "skill_package" / "plugin"） / Resource type
            resource_id: 资源 ID / Resource ID
            tenant_id: 目标企业 ID / Target tenant ID
            db: 数据库会话 / Database session

        Returns:
            该企业是否可见此资源 / Whether the tenant can see this resource
        """
        if scope in _ALL_TENANTS_VISIBLE_SCOPES:
            return True

        if scope in _ASSIGNMENT_REQUIRED_SCOPES:
            return await _check_assignment(resource_type, resource_id, tenant_id, db)

        return False  # admin_only

    @staticmethod
    def requires_tenant_assignment(scope: str) -> bool:
        """
        是否需要手动分配企业 / Whether manual tenant assignment is required

        assigned_tenants / admin_and_assigned → True
        其他 / Others → False
        """
        return scope in _ASSIGNMENT_REQUIRED_SCOPES

    @staticmethod
    def get_admin_visible_scopes() -> list[str]:
        """返回管理端可见的 scope 值列表（用于 SQL IN 查询） / Return admin-visible scope values (for SQL IN)"""
        return list(_ADMIN_VISIBLE_SCOPES)

    @staticmethod
    def get_all_tenants_visible_scopes() -> list[str]:
        """返回所有企业可见的 scope 值列表（无需分配表） / Return all-tenants-visible scope values (no assignment)"""
        return list(_ALL_TENANTS_VISIBLE_SCOPES)

    @staticmethod
    def get_tenant_possible_scopes() -> list[str]:
        """返回企业端可能可见的所有 scope 值列表（含需要分配表的） / Return all tenant-possibly-visible scope values"""
        return list(_TENANT_POSSIBLE_SCOPES)

    @staticmethod
    def get_assignment_required_scopes() -> list[str]:
        """返回需要企业分配表的 scope 值列表 / Return scopes requiring tenant assignment table"""
        return list(_ASSIGNMENT_REQUIRED_SCOPES)


async def _check_assignment(
    resource_type: str,
    resource_id: int,
    tenant_id: int,
    db: AsyncSession,
) -> bool:
    """查询 ResourceTenantAssignment 是否存在且启用 / Check if ResourceTenantAssignment exists and is active"""
    from sqlalchemy import select

    from app.models.system.resource_tenant_assignment import ResourceTenantAssignment

    result = await db.execute(
        select(ResourceTenantAssignment.id).where(
            ResourceTenantAssignment.resource_type == resource_type,
            ResourceTenantAssignment.resource_id == resource_id,
            ResourceTenantAssignment.tenant_id == tenant_id,
            ResourceTenantAssignment.is_active.is_(True),
            ResourceTenantAssignment.is_deleted.is_(False),
        )
    )
    return result.scalar_one_or_none() is not None


__all__ = ["ScopeChecker"]
