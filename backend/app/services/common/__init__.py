"""
公共服务模块

提供三端共用的服务和 Mixin
"""

from app.services.common.role_tree_mixin import RoleTreeMixin, MAX_ROLE_DEPTH
from app.services.common.auth_service import AuthService
from app.services.common.storage_quota_service import StorageQuotaService


__all__ = [
    "RoleTreeMixin",
    "MAX_ROLE_DEPTH",
    "AuthService",
    "StorageQuotaService",
]
