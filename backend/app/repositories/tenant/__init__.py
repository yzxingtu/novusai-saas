"""
租户级仓储模块

导出租户级别的仓储类
"""

from app.repositories.tenant.tenant_admin_repository import TenantAdminRepository
from app.repositories.tenant.tenant_role_repository import TenantRoleRepository
from app.repositories.tenant.tenant_plan_repository import TenantPlanRepository
from app.repositories.tenant.tenant_domain_repository import TenantDomainRepository


__all__ = [
    "TenantAdminRepository",
    "TenantRoleRepository",
    "TenantPlanRepository",
    "TenantDomainRepository",
]
