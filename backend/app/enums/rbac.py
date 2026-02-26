"""
RBAC 权限相关枚举

定义权限类型、作用域等枚举
"""

from app.enums.base import StrEnum
from app.enums.common import ResourceScopeEnum


class PermissionType(StrEnum):
    """权限类型"""
    
    MENU = ("menu", "enum.permission_type.menu")
    OPERATION = ("operation", "enum.permission_type.operation")


# [DEPRECATED] PermissionScope 已统一为 ResourceScopeEnum，保留别名兼容旧代码引用
# 旧值映射: ADMIN→ADMIN_ONLY, TENANT→ALL_TENANTS, BOTH→ADMIN_AND_ALL
PermissionScope = ResourceScopeEnum


__all__ = [
    "PermissionType",
    "PermissionScope",
]
