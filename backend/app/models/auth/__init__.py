"""
认证授权模块模型

RBAC 相关模型：权限、角色、角色-权限关联
"""

from app.models.auth.admin_role import AdminRole, admin_role_permissions
from app.models.auth.permission import Permission
from app.models.auth.tenant_admin_role import (
    TenantAdminRole,
    tenant_admin_role_permissions,
)
from app.models.auth.tenant_user_role import (
    TenantUserRole,
    tenant_user_role_permissions,
)

__all__ = [
    "Permission",
    "AdminRole",
    "admin_role_permissions",
    "TenantAdminRole",
    "tenant_admin_role_permissions",
    "TenantUserRole",
    "tenant_user_role_permissions",
]
