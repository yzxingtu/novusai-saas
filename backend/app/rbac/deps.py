"""
RBAC Permission Check Dependencies. / RBAC 权限检查依赖。

Provides FastAPI dependency injection functions for endpoint-level permission control.
提供 FastAPI 依赖注入函数，用于接口级别的权限控制。
"""

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import (
    get_current_active_admin,
    get_current_active_tenant_admin,
    get_db,
)
from app.core.i18n import _
from app.models import Admin, TenantAdmin
from app.rbac.services.permission_service import PermissionService


def require_admin_permissions(*permissions: str) -> Callable:
    """
    Require platform admin to have specified permissions.
    要求平台管理员拥有指定权限。

    Args:
        *permissions: Required permission codes / 需要的权限代码列表

    Returns:
        FastAPI dependency function / FastAPI 依赖函数

    Example:
        @router.get("/users")
        async def list_users(
            admin: Admin = Depends(require_admin_permissions("user:read"))
        ):
            ...
    """
    async def checker(
        db: Annotated[AsyncSession, Depends(get_db)],
        current_admin: Annotated[Admin, Depends(get_current_active_admin)],
    ) -> Admin:
        perm_service = PermissionService(db)
        user_perms = await perm_service.get_admin_permissions(current_admin)

        if not perm_service.check_all_permissions(user_perms, list(permissions)):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=_("rbac.permission_denied"),
            )

        return current_admin

    return checker


def require_any_admin_permission(*permissions: str) -> Callable:
    """
    Require platform admin to have any one of the specified permissions.
    要求平台管理员拥有任意一个指定权限。

    Args:
        *permissions: Required permission codes (any one suffices) / 需要的权限代码列表（满足任意一个即可）

    Returns:
        FastAPI dependency function / FastAPI 依赖函数
    """
    async def checker(
        db: Annotated[AsyncSession, Depends(get_db)],
        current_admin: Annotated[Admin, Depends(get_current_active_admin)],
    ) -> Admin:
        perm_service = PermissionService(db)
        user_perms = await perm_service.get_admin_permissions(current_admin)

        if not perm_service.check_any_permission(user_perms, list(permissions)):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=_("rbac.permission_denied"),
            )

        return current_admin

    return checker


def require_tenant_admin_permissions(*permissions: str) -> Callable:
    """
    Require tenant admin to have specified permissions.
    要求企业管理员拥有指定权限。

    Args:
        *permissions: Required permission codes / 需要的权限代码列表

    Returns:
        FastAPI dependency function / FastAPI 依赖函数

    Example:
        @router.get("/orders")
        async def list_orders(
            admin: TenantAdmin = Depends(require_tenant_admin_permissions("order:read"))
        ):
            ...
    """
    async def checker(
        db: Annotated[AsyncSession, Depends(get_db)],
        current_admin: Annotated[TenantAdmin, Depends(get_current_active_tenant_admin)],
    ) -> TenantAdmin:
        perm_service = PermissionService(db)
        user_perms = await perm_service.get_tenant_admin_permissions(current_admin)

        if not perm_service.check_all_permissions(user_perms, list(permissions)):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=_("rbac.permission_denied"),
            )

        return current_admin

    return checker


def require_any_tenant_admin_permission(*permissions: str) -> Callable:
    """
    Require tenant admin to have any one of the specified permissions.
    要求企业管理员拥有任意一个指定权限。

    Args:
        *permissions: Required permission codes (any one suffices) / 需要的权限代码列表（满足任意一个即可）

    Returns:
        FastAPI dependency function / FastAPI 依赖函数
    """
    async def checker(
        db: Annotated[AsyncSession, Depends(get_db)],
        current_admin: Annotated[TenantAdmin, Depends(get_current_active_tenant_admin)],
    ) -> TenantAdmin:
        perm_service = PermissionService(db)
        user_perms = await perm_service.get_tenant_admin_permissions(current_admin)

        if not perm_service.check_any_permission(user_perms, list(permissions)):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=_("rbac.permission_denied"),
            )

        return current_admin

    return checker


# Alias (compatible with naming in spec docs) / 别名（兼容规范文档中的命名）
require_permissions = require_tenant_admin_permissions


__all__ = [
    # Platform admin / 平台管理员
    "require_admin_permissions",
    "require_any_admin_permission",
    # Tenant admin / 企业管理员
    "require_tenant_admin_permissions",
    "require_any_tenant_admin_permission",
    # Alias / 别名
    "require_permissions",
]
