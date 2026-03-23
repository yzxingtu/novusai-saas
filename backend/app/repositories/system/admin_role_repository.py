"""
Legacy admin role repository compatibility layer / 旧 AdminRole 仓储兼容层
"""

from app.repositories.system.admin_permission_role_repository import AdminPermissionRoleRepository

AdminRoleRepository = AdminPermissionRoleRepository

__all__ = ["AdminRoleRepository"]
