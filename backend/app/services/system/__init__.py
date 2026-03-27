"""
平台管理后台服务模块 / Platform Admin Service Module

提供平台管理相关的服务。
Provides platform admin related services.
"""

from importlib import import_module
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.system.admin_org_authority_service import AdminOrgAuthorityService
    from app.services.system.admin_org_node_service import AdminOrgNodeService
    from app.services.system.admin_permission_role_service import (
        AdminPermissionRoleService,
    )
    from app.services.system.admin_role_service import AdminRoleService
    from app.services.system.admin_service import AdminService
    from app.services.system.attachment_service import AdminAttachmentService
    from app.services.system.operation_log_service import (
        OperationLogService,
        create_log_async,
    )
    from app.services.system.system_log_service import (
        LogCategoryInfo,
        LogContentPage,
        LogFileInfo,
        SystemLogService,
    )
    from app.services.system.task_binding_service import TaskBindingService
    from app.services.system.task_definition_service import TaskDefinitionService
    from app.services.system.task_log_service import TaskLogService
    from app.services.system.task_manager_service import TaskManagerService
    from app.services.system.task_run_service import TaskRunService
    from app.services.system.tenant_domain_service import (
        TenantDomainService,
        TenantDomainTenantService,
    )
    from app.services.system.tenant_service import TenantService
    from app.services.system.trace_lookup_service import (
        TraceLookupResult,
        TraceLookupService,
    )

__all__ = [
    "AdminOrgAuthorityService",
    "AdminOrgNodeService",
    "AdminPermissionRoleService",
    "AdminRoleService",
    "AdminService",
    "AdminAttachmentService",
    "OperationLogService",
    "create_log_async",
    "TaskBindingService",
    "TaskDefinitionService",
    "LogCategoryInfo",
    "LogContentPage",
    "LogFileInfo",
    "SystemLogService",
    "TaskLogService",
    "TaskManagerService",
    "TaskRunService",
    "TenantDomainService",
    "TenantDomainTenantService",
    "TenantService",
    "TraceLookupResult",
    "TraceLookupService",
]

_LAZY_EXPORTS = {
    "AdminOrgAuthorityService": "app.services.system.admin_org_authority_service",
    "AdminOrgNodeService": "app.services.system.admin_org_node_service",
    "AdminPermissionRoleService": "app.services.system.admin_permission_role_service",
    "AdminRoleService": "app.services.system.admin_role_service",
    "AdminService": "app.services.system.admin_service",
    "AdminAttachmentService": "app.services.system.attachment_service",
    "OperationLogService": "app.services.system.operation_log_service",
    "create_log_async": "app.services.system.operation_log_service",
    "TaskBindingService": "app.services.system.task_binding_service",
    "TaskDefinitionService": "app.services.system.task_definition_service",
    "LogCategoryInfo": "app.services.system.system_log_service",
    "LogContentPage": "app.services.system.system_log_service",
    "LogFileInfo": "app.services.system.system_log_service",
    "SystemLogService": "app.services.system.system_log_service",
    "TaskLogService": "app.services.system.task_log_service",
    "TaskManagerService": "app.services.system.task_manager_service",
    "TaskRunService": "app.services.system.task_run_service",
    "TenantDomainService": "app.services.system.tenant_domain_service",
    "TenantDomainTenantService": "app.services.system.tenant_domain_service",
    "TenantService": "app.services.system.tenant_service",
    "TraceLookupResult": "app.services.system.trace_lookup_service",
    "TraceLookupService": "app.services.system.trace_lookup_service",
}


def __getattr__(name: str):
    """延迟导出服务对象，避免无关命令触发重型依赖导入。 / Lazy export service symbols to avoid loading heavy dependencies for unrelated commands."""
    module_path = _LAZY_EXPORTS.get(name)
    if not module_path:
        raise AttributeError(f"module 'app.services.system' has no attribute {name!r}")
    module = import_module(module_path)
    return getattr(module, name)


def __dir__() -> list[str]:
    return sorted(__all__)
