"""
平台管理仓储模块 / Platform Admin Repository Module

导出系统级仓储类
Exports system-level repository classes.
"""

from app.repositories.system.admin_repository import AdminRepository
from app.repositories.system.admin_role_repository import AdminRoleRepository
from app.repositories.system.attachment_repository import AdminAttachmentRepository
from app.repositories.system.operation_log_repository import OperationLogRepository
from app.repositories.system.periodic_task_repository import PeriodicTaskRepository
from app.repositories.system.task_log_repository import TaskLogRepository
from app.repositories.system.tenant_domain_repository import TenantDomainRepository
from app.repositories.system.tenant_repository import TenantRepository

__all__ = [
    "AdminRepository",
    "AdminRoleRepository",
    "TenantRepository",
    "TenantDomainRepository",
    "OperationLogRepository",
    "AdminAttachmentRepository",
    "TaskLogRepository",
    "PeriodicTaskRepository",
]
