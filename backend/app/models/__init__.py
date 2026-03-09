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
# AI 模型
from app.models.ai import (
    Agent,
    AgentAccess,
    AgentConversation,
    AgentKnowledgeBaseBinding,
    AgentMemoryOverride,
    AgentSkillBinding,
    AgentVersion,
    AIActionLog,
    AICallLog,
    AIModel,
    AIProvider,
    AIQueryLog,
    AITablePolicy,
    AITablePolicyOverride,
    BatchRun,
    ConversationMessage,
    DocumentChunk,
    KnowledgeBase,
    KnowledgeBaseTenantAccess,
    KnowledgeDocument,
    ProviderApiKey,
    Skill,
    SkillCallLog,
    SkillPackage,
    TenantModelRateLimit,
    TenantQuota,
    UsageStat,
)

# RBAC 模型
from app.models.auth import (
    AdminRole,
    Permission,
    TenantAdminRole,
    TenantUserRole,
    admin_role_permissions,
    tenant_admin_role_permissions,
    tenant_user_role_permissions,
)
from app.models.common.notification import Notification
from app.models.common.notification_preference import NotificationPreference

# 通知模型
from app.models.common.notification_template import NotificationTemplate
from app.models.system import (
    Admin,
    OperationLog,
    PeriodicTask,
    Plugin,
    PluginLicense,
    PluginVersion,
    ResourceTenantAssignment,
    SystemAgentAssignment,
    SystemConfig,
    SystemConfigGroup,
    SystemConfigValue,
    TaskLog,
)

# 系统模型（补充）
from app.models.system.email_log import EmailLog

# 租户级模型
from app.models.tenant import (
    Attachment,
    DomainSslCertificate,
    Tenant,
    TenantAdmin,
    TenantDomain,
    TenantPlan,
    TenantUser,
    tenant_plan_permissions,
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
    "DomainSslCertificate",
    "TenantPlan",
    "tenant_plan_permissions",
    "Attachment",
    # RBAC
    "Permission",
    "AdminRole",
    "admin_role_permissions",
    "TenantAdminRole",
    "tenant_admin_role_permissions",
    "TenantUserRole",
    "tenant_user_role_permissions",
    # AI
    "AIProvider",
    "AIModel",
    "ProviderApiKey",
    "AICallLog",
    "UsageStat",
    "TenantModelRateLimit",
    "TenantQuota",
    # 智能体
    "Agent",
    "AgentConversation",
    "ConversationMessage",
    # 批量运行
    "BatchRun",
    # 智能体版本
    "AgentVersion",
    # 智能体访问权限
    "AgentAccess",
    "AgentMemoryOverride",
    # AI 操作审计日志
    "AIActionLog",
    # AI 表策略
    "AITablePolicy",
    "AITablePolicyOverride",
    # 技能包 & 技能
    "SkillPackage",
    "Skill",
    "AgentKnowledgeBaseBinding",
    "AgentSkillBinding",
    "SkillCallLog",
    # 知识库
    "KnowledgeBase",
    "KnowledgeBaseTenantAccess",
    "KnowledgeDocument",
    "DocumentChunk",
    # AI 查询日志
    "AIQueryLog",
    # 系统智能体绑定
    "SystemAgentAssignment",
    # 邮件日志
    "EmailLog",
    # 插件
    "Plugin",
    "PluginVersion",
    "PluginLicense",
    "ResourceTenantAssignment",
    # 通知
    "NotificationTemplate",
    "Notification",
    "NotificationPreference",
]
