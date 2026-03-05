"""
仓储模块

导出所有仓储类
"""

from app.repositories.system import AdminRepository, TenantRepository
from app.repositories.tenant import (
    AttachmentRepository,
    TenantAdminRepository,
    TenantRoleRepository,
)

__all__ = [
    # 平台级
    "AdminRepository",
    "TenantRepository",
    # 租户级
    "AttachmentRepository",
    "TenantAdminRepository",
    "TenantRoleRepository",
]
