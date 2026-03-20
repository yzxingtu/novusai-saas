"""
平台管理后台服务模块 / Platform Admin Service Module

提供平台管理相关的服务。
Provides platform admin related services.
"""

from importlib import import_module
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.system.admin_role_service import AdminRoleService
    from app.services.system.admin_service import AdminService
    from app.services.system.attachment_service import AdminAttachmentService
    from app.services.system.operation_log_service import (
        OperationLogService,
        create_log_async,
    )
    from app.services.system.periodic_task_service import PeriodicTaskService
    from app.services.system.system_log_service import (
        LogCategoryInfo,
        LogContentPage,
        LogFileInfo,
        SystemLogService,
    )
    from app.services.system.task_log_service import TaskLogService
    from app.services.system.task_manager_service import TaskManagerService
    from app.services.system.tenant_domain_service import (
        TenantDomainService,
        TenantDomainTenantService,
    )
    from app.services.system.tenant_service import TenantService

_LAZY_EXPORTS = {
    "AdminRoleService": "app.services.system.admin_role_service",
    "AdminService": "app.services.system.admin_service",
    "AdminAttachmentService": "app.services.system.attachment_service",
    "OperationLogService": "app.services.system.operation_log_service",
    "create_log_async": "app.services.system.operation_log_service",
    "PeriodicTaskService": "app.services.system.periodic_task_service",
    "LogCategoryInfo": "app.services.system.system_log_service",
    "LogContentPage": "app.services.system.system_log_service",
    "LogFileInfo": "app.services.system.system_log_service",
    "SystemLogService": "app.services.system.system_log_service",
    "TaskLogService": "app.services.system.task_log_service",
    "TaskManagerService": "app.services.system.task_manager_service",
    "TenantDomainService": "app.services.system.tenant_domain_service",
    "TenantDomainTenantService": "app.services.system.tenant_domain_service",
    "TenantService": "app.services.system.tenant_service",
}

__all__ = list(_LAZY_EXPORTS)


def __getattr__(name: str):
    """延迟导出服务对象，避免无关命令触发重型依赖导入。 / Lazy export service symbols to avoid loading heavy dependencies for unrelated commands."""
    module_path = _LAZY_EXPORTS.get(name)
    if not module_path:
        raise AttributeError(f"module 'app.services.system' has no attribute {name!r}")
    module = import_module(module_path)
    return getattr(module, name)


def __dir__() -> list[str]:
    return sorted(__all__)
