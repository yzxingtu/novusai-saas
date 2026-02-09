"""
数据模型模块

导出所有数据库模型

目录结构:
- system/: 平台级模型 (Admin)
- tenant/: 租户级模型 (Tenant, TenantAdmin, TenantUser)
- auth/: RBAC 模型 (Permission, AdminRole, TenantAdminRole)
- ai/: AI 网关模型 (AIProvider, AIModel, ProviderApiKey, AICallLog)
"""

# 平台级模型
from app.models.system import (
    Admin,
    SystemConfigGroup,
    SystemConfig,
    SystemConfigValue,
    OperationLog,
    TaskLog,
    PeriodicTask,
)

# 租户级模型
from app.models.tenant import (
    Tenant,
    TenantAdmin,
    TenantUser,
    TenantDomain,
    TenantPlan,
    tenant_plan_permissions,
    Attachment,
)

# RBAC 模型
from app.models.auth import (
    Permission,
    AdminRole,
    admin_role_permissions,
    TenantAdminRole,
    tenant_admin_role_permissions,
)

# AI 模型
from app.models.ai import (
    AIProvider,
    AIModel,
    ProviderApiKey,
    AICallLog,
    UsageStat,
    TenantModelRateLimit,
    TenantQuota,
)

__all__ = [
    # 平台级
    "Admin",
    "SystemConfigGroup",
    "SystemConfig",
    "SystemConfigValue",
    "OperationLog",
    "TaskLog",
    "PeriodicTask",
    # 租户级
    "Tenant",
    "TenantAdmin",
    "TenantUser",
    "TenantDomain",
    "TenantPlan",
    "tenant_plan_permissions",
    "Attachment",
    # RBAC
    "Permission",
    "AdminRole",
    "admin_role_permissions",
    "TenantAdminRole",
    "tenant_admin_role_permissions",
    # AI
    "AIProvider",
    "AIModel",
    "ProviderApiKey",
    "AICallLog",
    "UsageStat",
    "TenantModelRateLimit",
    "TenantQuota",
]
