"""
RBAC 权限相关枚举 / RBAC Permission Enums

定义权限类型、作用域等枚举
Defines permission type, scope and other enums.
"""

from app.enums.base import StrEnum
from app.enums.common import ResourceScopeEnum


class PermissionType(StrEnum):
    """Permission Type / 权限类型"""

    MENU = ("menu", "enum.permission_type.menu")
    OPERATION = ("operation", "enum.permission_type.operation")


# [DEPRECATED] PermissionScope unified to ResourceScopeEnum, alias kept for backward compat / PermissionScope 已统一为 ResourceScopeEnum，保留别名兼容旧代码引用
# Old value mapping / 旧值映射: ADMIN→ADMIN_ONLY, TENANT→ALL_TENANTS, BOTH→ADMIN_AND_ALL
PermissionScope = ResourceScopeEnum


__all__ = [
    "PermissionType",
    "PermissionScope",
]
