"""
系统模块模型

平台级别的模型定义
"""

from app.models.system.admin import Admin
from app.models.system.config import (
    SystemConfigGroup,
    SystemConfig,
    SystemConfigValue,
)
from app.models.system.operation_log import OperationLog
from app.models.system.task_log import TaskLog
from app.models.system.periodic_task import PeriodicTask
from app.models.system.plugin import Plugin
from app.models.system.plugin_migration import PluginMigration
from app.models.system.plugin_tenant_assignment import PluginTenantAssignment
from app.models.system.tenant_plugin import TenantPlugin
from app.models.system.agent_assignment import SystemAgentAssignment
from app.models.system.email_log import EmailLog

__all__ = [
    "Admin",
    "SystemConfigGroup",
    "SystemConfig",
    "SystemConfigValue",
    "OperationLog",
    "TaskLog",
    "PeriodicTask",
    "Plugin",
    "PluginMigration",
    "PluginTenantAssignment",
    "TenantPlugin",
    "SystemAgentAssignment",
]
