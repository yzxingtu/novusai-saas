"""
RBAC Service Layer
RBAC 服务层

Provides permission check business services.
提供权限检查相关的业务服务。
"""

from app.rbac.services.permission_service import PermissionService

__all__ = [
    "PermissionService",
]
