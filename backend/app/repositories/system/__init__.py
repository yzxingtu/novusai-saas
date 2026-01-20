"""
平台管理仓储模块

导出系统级仓储类
"""

from app.repositories.system.admin_repository import AdminRepository
from app.repositories.system.admin_role_repository import AdminRoleRepository
from app.repositories.system.tenant_repository import TenantRepository
from app.repositories.system.operation_log_repository import OperationLogRepository


__all__ = [
    "AdminRepository",
    "AdminRoleRepository",
    "TenantRepository",
    "OperationLogRepository",
]
