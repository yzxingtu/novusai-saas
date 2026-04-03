"""
数据模型模块 / Data Model Module

导出所有数据库模型
Exports all database models.

目录结构 / Directory structure:
- system/: 平台级模型 / Platform models (Admin)
- tenant/: 企业级模型 / Tenant models (Tenant, TenantAdmin, TenantUser)
- auth/: RBAC 模型 / RBAC models (Permission, AdminRole, TenantAdminRole)
- ai/: AI 网关模型 / AI gateway models (AIProvider, AIModel, ProviderApiKey, AICallLog)
"""

# 平台级模型 / Platform Models
# AI 模型 / AI Models
from app.models.ai import (
    Agent,
    AgentAccess,
    AgentConversation,
    AgentKnowledgeBaseBinding,
    AgentMemoryOverride,
    AgentSkillGrant,
    AgentVersion,
    AIActionLog,
    AICallLog,
    AIModel,
    AIProvider,
    AIQueryLog,
    AITablePolicy,
    AITablePolicyOverride,
    BatchRun,
    Capability,
    ConversationMessage,
    DocumentChunk,
    ExecutionDecision,
    ExecutionTrustPolicy,
    KnowledgeBase,
    KnowledgeDocument,
    MemoryRecord,
    ProfileSnapshot,
    ProviderApiKey,
    Skill,
    SkillCallLog,
    SkillCapabilityBinding,
    SkillPackage,
    SkillResource,
    TenantAgentPlatformKbSuppression,
    TenantAgentPublication,
    TenantModelRateLimit,
    TenantQuota,
)

# RBAC 模型 / RBAC models
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

# 通知模型 / Notification models
from app.models.common.notification_template import NotificationTemplate

# 用户偏好 / User preferences
from app.models.common.user_preference import UserPreference
from app.models.org import (
    AdminOrgNode,
    AdminOrgScopePolicy,
    AdminOrgScopeTarget,
    TenantOrgNode,
    TenantOrgScopePolicy,
    TenantOrgScopeTarget,
    admin_org_node_permissions,
)
from app.models.system import (
    Admin,
    CodegenConfig,
    CodegenConfigVersion,
    OperationLog,
    Plugin,
    PluginLicense,
    PluginVersion,
    ResourceTenantAssignment,
    SystemAgentAssignment,
    SystemConfig,
    SystemConfigGroup,
    SystemConfigValue,
    TaskDefinition,
    TaskRun,
    TenantTaskBinding,
)

# 系统模型（补充）/ System models (supplement)
from app.models.system.email_log import EmailLog

# 企业级模型 / Tenant models
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
    # 平台级 / Platform
    "Admin",
    "SystemConfigGroup",
    "SystemConfig",
    "SystemConfigValue",
    "OperationLog",
    "TaskDefinition",
    "TenantTaskBinding",
    "TaskRun",
    # 企业级 / Tenant
    "Tenant",
    "TenantAdmin",
    "TenantUser",
    "TenantDomain",
    "DomainSslCertificate",
    "TenantPlan",
    "tenant_plan_permissions",
    "Attachment",
    # RBAC / 基于角色的访问控制
    "Permission",
    "AdminRole",
    "admin_role_permissions",
    "TenantAdminRole",
    "tenant_admin_role_permissions",
    "TenantUserRole",
    "tenant_user_role_permissions",
    # Organization / 组织架构
    "AdminOrgNode",
    "AdminOrgScopePolicy",
    "AdminOrgScopeTarget",
    "admin_org_node_permissions",
    "TenantOrgNode",
    "TenantOrgScopePolicy",
    "TenantOrgScopeTarget",
    # AI / 模型与用量等 AI 基础表
    "AIProvider",
    "AIModel",
    "MemoryRecord",
    "ProfileSnapshot",
    "ProviderApiKey",
    "AICallLog",
    "TenantModelRateLimit",
    "TenantQuota",
    "TenantAgentPlatformKbSuppression",
    # 智能体 / Agents
    "Agent",
    "AgentConversation",
    "ConversationMessage",
    "ExecutionDecision",
    "ExecutionTrustPolicy",
    # 批量运行 / Batch run
    "BatchRun",
    # 智能体版本 / Agent versions
    "AgentVersion",
    # 智能体访问权限 / Agent access
    "AgentAccess",
    "TenantAgentPublication",
    "AgentMemoryOverride",
    # AI 操作审计日志 / AI action logs
    "AIActionLog",
    # AI 表策略 / AI table policies
    "AITablePolicy",
    "AITablePolicyOverride",
    "Capability",
    # 技能包 & 技能 / Skill packages & skills
    "SkillPackage",
    "Skill",
    "SkillResource",
    "SkillCapabilityBinding",
    "AgentSkillGrant",
    "AgentKnowledgeBaseBinding",
    "SkillCallLog",
    # 知识库 / Knowledge bases
    "KnowledgeBase",
    "KnowledgeDocument",
    "DocumentChunk",
    # AI 查询日志 / AI query logs
    "AIQueryLog",
    # 系统智能体绑定 / System agent assignments
    "SystemAgentAssignment",
    "CodegenConfig",
    "CodegenConfigVersion",
    # 邮件日志 / Email logs
    "EmailLog",
    # 插件 / Plugins
    "Plugin",
    "PluginVersion",
    "PluginLicense",
    "ResourceTenantAssignment",
    # 通知 / Notifications
    "NotificationTemplate",
    "Notification",
    "NotificationPreference",
    # 用户偏好 / User preferences
    "UserPreference",
]
