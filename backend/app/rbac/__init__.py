"""
RBAC 权限管理模块

提供基于角色的访问控制功能：
- decorators: 权限装饰器（声明式定义权限）
- registry: 权限注册中心
- deps: 权限检查依赖
- services: 权限服务
- sync: 权限同步服务
"""

from app.rbac.decorators import (
    MenuConfig,
    PermissionMeta,
    action_create,
    action_delete,
    action_read,
    action_update,
    permission_action,
    permission_resource,
)
from app.rbac.deps import (
    require_admin_permissions,
    require_any_admin_permission,
    require_any_tenant_admin_permission,
    require_permissions,
    require_tenant_admin_permissions,
)
from app.rbac.registry import permission_registry
from app.rbac.services import PermissionService

__all__ = [
    # 装饰器
    "permission_resource",
    "permission_action",
    "action_read",
    "action_create",
    "action_update",
    "action_delete",
    # 配置
    "MenuConfig",
    "PermissionMeta",
    # 注册中心
    "permission_registry",
    # 权限依赖
    "require_admin_permissions",
    "require_any_admin_permission",
    "require_tenant_admin_permissions",
    "require_any_tenant_admin_permission",
    "require_permissions",
    # 服务
    "PermissionService",
]
