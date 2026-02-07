"""
平台管理后台服务模块

提供平台管理相关的服务
"""

from app.services.system.admin_service import AdminService
from app.services.system.admin_role_service import AdminRoleService
from app.services.system.tenant_service import TenantService
from app.services.system.tenant_domain_service import TenantDomainService, TenantDomainTenantService
from app.services.system.operation_log_service import (
    OperationLogService,
    create_log_async,
)
from app.services.system.system_log_service import (
    SystemLogService,
    LogFileInfo,
    LogCategoryInfo,
    LogContentPage,
)
from app.services.system.attachment_service import AdminAttachmentService
from app.services.system.task_log_service import TaskLogService
from app.services.system.task_manager_service import TaskManagerService
from app.services.system.periodic_task_service import PeriodicTaskService


__all__ = [
    "AdminService",
    "AdminRoleService",
    "TenantService",
    "TenantDomainService",
    "TenantDomainTenantService",
    "OperationLogService",
    "create_log_async",
    "SystemLogService",
    "LogFileInfo",
    "LogCategoryInfo",
    "LogContentPage",
    "AdminAttachmentService",
    "TaskLogService",
    "TaskManagerService",
    "PeriodicTaskService",
]
