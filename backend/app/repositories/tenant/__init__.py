"""
企业级仓储模块 / Tenant Repository Module

导出企业级别的仓储类
Exports tenant-level repository classes.
"""

from app.repositories.tenant.attachment_repository import AttachmentRepository
from app.repositories.tenant.tenant_admin_repository import TenantAdminRepository
from app.repositories.tenant.tenant_domain_tenant_repository import (
    TenantDomainTenantRepository,
)
from app.repositories.tenant.tenant_plan_repository import TenantPlanRepository
from app.repositories.tenant.tenant_role_repository import TenantRoleRepository
from app.repositories.tenant.tenant_user_repository import TenantUserRepository
from app.repositories.tenant.tenant_user_role_repository import (
    TenantUserRoleRepository,
)

__all__ = [
    "AttachmentRepository",
    "TenantAdminRepository",
    "TenantRoleRepository",
    "TenantPlanRepository",
    "TenantDomainTenantRepository",
    "TenantUserRepository",
    "TenantUserRoleRepository",
]
