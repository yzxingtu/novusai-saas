"""
Legacy admin role service compatibility layer / 旧 AdminRole 服务兼容层
"""

from app.services.system.admin_permission_role_service import AdminPermissionRoleService

AdminRoleService = AdminPermissionRoleService

__all__ = ["AdminRoleService"]
