"""
系统模块模型 / System Module Models

平台级别的模型定义
Platform-level model definitions.
"""

from app.models.system.admin import Admin
from app.models.system.agent_assignment import SystemAgentAssignment
from app.models.system.config import (
    SystemConfig,
    SystemConfigGroup,
    SystemConfigValue,
)
from app.models.system.email_log import EmailLog
from app.models.system.operation_log import OperationLog
from app.models.system.periodic_task import PeriodicTask
from app.models.system.plugin import Plugin
from app.models.system.plugin_license import PluginLicense
from app.models.system.plugin_version import PluginVersion
from app.models.system.resource_tenant_assignment import ResourceTenantAssignment
from app.models.system.task_log import TaskLog

__all__ = [
    "Admin",
    "SystemConfigGroup",
    "SystemConfig",
    "SystemConfigValue",
    "OperationLog",
    "TaskLog",
    "PeriodicTask",
    "SystemAgentAssignment",
    "EmailLog",
    "Plugin",
    "PluginVersion",
    "PluginLicense",
    "ResourceTenantAssignment",
]
