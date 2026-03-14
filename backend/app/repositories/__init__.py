"""
仓储模块 / Repository Module

导出所有仓储类
Exports all repository classes.
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
    # 企业级
    "AttachmentRepository",
    "TenantAdminRepository",
    "TenantRoleRepository",
]
