"""
统一作用域判定工具

提供全平台通用的作用域可见性判定方法，替代各模块零散的 scope 判定逻辑。

注意区分：本模块处理的是「资源作用域」（ResourceScopeEnum），与以下概念无关：
  - JWT Token Scope (TOKEN_SCOPE_ADMIN 等) — 认证身份标识
  - ASGI Scope (Starlette.types.Scope) — HTTP 请求元数据
  - BaseRepository._scope_fields — API 端字段过滤标识
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.enums.common import ResourceScopeEnum

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


# 管理端可见的 scope 集合
_ADMIN_VISIBLE_SCOPES = frozenset({
    ResourceScopeEnum.ADMIN_ONLY.value,
    ResourceScopeEnum.ADMIN_AND_ALL.value,
    ResourceScopeEnum.ADMIN_AND_ASSIGNED.value,
})

# 所有租户可见的 scope 集合（无需分配表）
_ALL_TENANTS_VISIBLE_SCOPES = frozenset({
    ResourceScopeEnum.ALL_TENANTS.value,
    ResourceScopeEnum.ADMIN_AND_ALL.value,
})

# 需要租户分配表的 scope 集合
_ASSIGNMENT_REQUIRED_SCOPES = frozenset({
    ResourceScopeEnum.ASSIGNED_TENANTS.value,
    ResourceScopeEnum.ADMIN_AND_ASSIGNED.value,
})

# 租户端可能可见的 scope 集合（全部租户 + 部分租户）
_TENANT_POSSIBLE_SCOPES = _ALL_TENANTS_VISIBLE_SCOPES | _ASSIGNMENT_REQUIRED_SCOPES


class ScopeChecker:
    """
    统一作用域判定工具

    所有需要判断资源可见性的代码统一调用此类的静态方法，
    避免各模块各自硬编码 scope 判定逻辑。

    Usage::

        from app.core.scope import ScopeChecker

        # 管理端是否可见
        if ScopeChecker.is_visible_to_admin(resource.scope):
            ...

        # 租户端是否可见（需要异步查分配表）
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
        管理端是否可见

        admin_only / admin_and_all / admin_and_assigned → True
        all_tenants / assigned_tenants → False
        """
        return scope in _ADMIN_VISIBLE_SCOPES

    @staticmethod
    def is_visible_to_all_tenants(scope: str) -> bool:
        """
        是否对所有租户可见（无需分配表查询）

        all_tenants / admin_and_all → True
        其他 → False
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
        指定租户是否可见

        - all_tenants / admin_and_all → True（全部租户可见）
        - assigned_tenants / admin_and_assigned → 查 ResourceTenantAssignment
        - admin_only → False

        Args:
            scope: 资源的作用域值
            resource_type: 资源类型（如 "skill_package" / "plugin"）
            resource_id: 资源 ID
            tenant_id: 目标租户 ID
            db: 数据库会话

        Returns:
            该租户是否可见此资源
        """
        if scope in _ALL_TENANTS_VISIBLE_SCOPES:
            return True

        if scope in _ASSIGNMENT_REQUIRED_SCOPES:
            return await _check_assignment(resource_type, resource_id, tenant_id, db)

        return False  # admin_only

    @staticmethod
    def requires_tenant_assignment(scope: str) -> bool:
        """
        是否需要手动分配租户

        assigned_tenants / admin_and_assigned → True
        其他 → False
        """
        return scope in _ASSIGNMENT_REQUIRED_SCOPES

    @staticmethod
    def get_admin_visible_scopes() -> list[str]:
        """返回管理端可见的 scope 值列表（用于 SQL IN 查询）"""
        return list(_ADMIN_VISIBLE_SCOPES)

    @staticmethod
    def get_all_tenants_visible_scopes() -> list[str]:
        """返回所有租户可见的 scope 值列表（无需分配表）"""
        return list(_ALL_TENANTS_VISIBLE_SCOPES)

    @staticmethod
    def get_tenant_possible_scopes() -> list[str]:
        """返回租户端可能可见的所有 scope 值列表（含需要分配表的）"""
        return list(_TENANT_POSSIBLE_SCOPES)

    @staticmethod
    def get_assignment_required_scopes() -> list[str]:
        """返回需要租户分配表的 scope 值列表"""
        return list(_ASSIGNMENT_REQUIRED_SCOPES)


async def _check_assignment(
    resource_type: str,
    resource_id: int,
    tenant_id: int,
    db: AsyncSession,
) -> bool:
    """查询 ResourceTenantAssignment 是否存在且启用"""
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
