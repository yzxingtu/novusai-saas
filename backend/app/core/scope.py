"""
统一作用域判定工具 / Unified Scope Determination Utility

提供全平台通用的资源作用域可见性判定（ResourceScopeEnum 五类）。
Provides resource-scope visibility checks for the five canonical resource scopes.

注意区分 / Note: This module handles 「Resource Scope」(ResourceScopeEnum), unrelated to:
  - PermissionScope — RBAC 权限端别 / RBAC permission endpoint
  - JWT Token Scope (TOKEN_SCOPE_ADMIN etc.) — 认证身份标识 / Authentication identity
  - ASGI Scope (Starlette.types.Scope) — HTTP 请求元数据 / HTTP request metadata
  - BaseRepository._scope_fields — API 端字段过滤标识 / API endpoint field filter identifier
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.enums.common import ResourceScopeEnum

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


# 管理端可见的资源 scope / Admin-visible resource scopes
_ADMIN_VISIBLE_SCOPES = frozenset({
    ResourceScopeEnum.ADMIN_ONLY.value,
    ResourceScopeEnum.GLOBAL_SHARED.value,
    ResourceScopeEnum.ADMIN_AND_SELECTED_TENANTS.value,
})

# 对所有企业可见（无需分配表）/ Visible to every tenant without assignment table
_ALL_TENANTS_VISIBLE_SCOPES = frozenset({
    ResourceScopeEnum.ALL_TENANTS.value,
    ResourceScopeEnum.GLOBAL_SHARED.value,
})

# 需要 ResourceTenantAssignment 的 scope / Scopes requiring assignment rows
_ASSIGNMENT_REQUIRED_SCOPES = frozenset({
    ResourceScopeEnum.SELECTED_TENANTS.value,
    ResourceScopeEnum.ADMIN_AND_SELECTED_TENANTS.value,
})

_TENANT_POSSIBLE_SCOPES = _ALL_TENANTS_VISIBLE_SCOPES | _ASSIGNMENT_REQUIRED_SCOPES


class ScopeChecker:
    """
    统一资源作用域判定 / Unified resource scope checker
    """

    @staticmethod
    def is_visible_to_admin(scope: str) -> bool:
        """管理端是否可见此资源 / Whether admin UI may use this resource"""
        return scope in _ADMIN_VISIBLE_SCOPES

    @staticmethod
    def is_visible_to_all_tenants(scope: str) -> bool:
        """是否对所有企业可见且无需查分配表 / All tenants, no assignment query"""
        return scope in _ALL_TENANTS_VISIBLE_SCOPES

    @staticmethod
    async def is_visible_to_tenant(
        scope: str,
        resource_type: str,
        resource_id: int,
        tenant_id: int,
        db: AsyncSession,
    ) -> bool:
        """指定企业是否可见此资源 / Whether tenant may use this resource"""
        if scope in _ALL_TENANTS_VISIBLE_SCOPES:
            return True
        if scope in _ASSIGNMENT_REQUIRED_SCOPES:
            return await _check_assignment(resource_type, resource_id, tenant_id, db)
        return False

    @staticmethod
    def requires_tenant_assignment(scope: str) -> bool:
        """是否需要维护分配企业列表 / Whether RTA rows are required"""
        return scope in _ASSIGNMENT_REQUIRED_SCOPES

    @staticmethod
    def get_admin_visible_scopes() -> list[str]:
        return list(_ADMIN_VISIBLE_SCOPES)

    @staticmethod
    def get_all_tenants_visible_scopes() -> list[str]:
        return list(_ALL_TENANTS_VISIBLE_SCOPES)

    @staticmethod
    def get_tenant_possible_scopes() -> list[str]:
        return list(_TENANT_POSSIBLE_SCOPES)

    @staticmethod
    def get_assignment_required_scopes() -> list[str]:
        return list(_ASSIGNMENT_REQUIRED_SCOPES)


async def _check_assignment(
    resource_type: str,
    resource_id: int,
    tenant_id: int,
    db: AsyncSession,
) -> bool:
    """查询 ResourceTenantAssignment 是否存在且启用 / Check RTA active row"""
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
