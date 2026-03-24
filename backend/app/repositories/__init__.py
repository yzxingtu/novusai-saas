"""
仓储模块 / Repository Module

导出所有仓储类
Exports all repository classes.
"""

from app.repositories.system import AdminRepository, TenantRepository
from app.repositories.tenant import (
    AttachmentRepository,
    TenantAdminRepository,
    TenantOrgNodeRepository,
    TenantPermissionRoleRepository,
)

__all__ = [
    # 平台级 / Platform scope
    "AdminRepository",
    "TenantRepository",
    # 企业级 / Tenant scope
    "AttachmentRepository",
    "TenantAdminRepository",
    "TenantOrgNodeRepository",
    "TenantPermissionRoleRepository",
]
