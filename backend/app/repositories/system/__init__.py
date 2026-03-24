"""
平台管理仓储模块 / Platform Admin Repository Module

导出系统级仓储类
Exports system-level repository classes.
"""

from app.repositories.system.admin_repository import AdminRepository
from app.repositories.system.admin_org_node_repository import AdminOrgNodeRepository
from app.repositories.system.admin_permission_role_repository import AdminPermissionRoleRepository
from app.repositories.system.admin_role_repository import AdminRoleRepository
from app.repositories.system.attachment_repository import AdminAttachmentRepository
from app.repositories.system.operation_log_repository import OperationLogRepository
from app.repositories.system.task_definition_repository import TaskDefinitionRepository
from app.repositories.system.task_run_repository import TaskRunRepository
from app.repositories.system.tenant_domain_repository import TenantDomainRepository
from app.repositories.system.tenant_task_binding_repository import (
    TenantTaskBindingRepository,
)
from app.repositories.system.tenant_repository import TenantRepository

__all__ = [
    "AdminRepository",
    "AdminOrgNodeRepository",
    "AdminPermissionRoleRepository",
    "AdminRoleRepository",
    "TenantRepository",
    "TenantDomainRepository",
    "OperationLogRepository",
    "AdminAttachmentRepository",
    "TaskDefinitionRepository",
    "TenantTaskBindingRepository",
    "TaskRunRepository",
]
