"""
RBAC 权限相关枚举 / RBAC Permission Enums

定义权限类型、权限所属端别（与资源作用域 ResourceScopeEnum 完全分离）
Defines permission type and endpoint scope (decoupled from ResourceScopeEnum).
"""

from app.enums.base import LabeledStrEnum, StrEnum


class PermissionType(StrEnum):
    """Permission Type / 权限类型"""

    MENU = ("menu", "enum.permission_type.menu")
    OPERATION = ("operation", "enum.permission_type.operation")


class PermissionScope(LabeledStrEnum):
    """权限所属端别 / Permission endpoint (stored in permissions.scope)

    与 ResourceScopeEnum 无关；表示菜单/权限点出现在哪一端。
    Unrelated to resource scope; indicates which app endpoint owns this permission row.

    BOTH: 管理端与企业端菜单树均挂载（权限端别，非资源作用域）
    """

    ADMIN = ("admin", "enum.permission_scope.admin")
    TENANT = ("tenant", "enum.permission_scope.tenant")
    USER = ("user", "enum.permission_scope.user")
    BOTH = ("both", "enum.permission_scope.both")


# 文档与类型提示别名：强调与 ResourceScopeEnum 分离 / Alias for docs & typing clarity
PermissionEndpointScope = PermissionScope


__all__ = [
    "PermissionEndpointScope",
    "PermissionType",
    "PermissionScope",
]
