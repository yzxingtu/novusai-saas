"""
平台管理后台 API 路由模块 / Platform Admin API Router Module

聚合所有平台管理后台的 API 路由
Aggregates all platform admin API routes.

控制器类使用 @permission_resource 装饰器定义资源权限，导入控制器类时会自动注册权限到 PermissionRegistry。
Controller classes use @permission_resource decorator to define resource permissions, auto-registering to PermissionRegistry on import.
"""

from fastapi import APIRouter

from app.api.admin.agent_assignments import AdminAgentAssignmentController
from app.api.admin.agent_assignments import router as agent_assignments_router
from app.api.admin.agents import AdminAgentController
from app.api.admin.agents import router as ai_agents_router
from app.api.admin.ai_action_logs import AdminAIActionLogController
from app.api.admin.ai_action_logs import router as ai_action_logs_router
from app.api.admin.ai_writing import router as ai_writing_router
from app.api.admin.ai_agent_chat import AdminAgentChatController
from app.api.admin.ai_agent_chat import router as ai_agent_chat_router
from app.api.admin.ai_api_keys import AdminAIApiKeyController
from app.api.admin.ai_api_keys import router as ai_api_keys_router
from app.api.admin.ai_call_logs import AdminAICallLogController
from app.api.admin.ai_call_logs import router as ai_call_logs_router
from app.api.admin.ai_conversations import AdminAIConversationController
from app.api.admin.ai_conversations import router as ai_conversations_router
from app.api.admin.ai_gateway import AdminAIGatewayController
from app.api.admin.ai_gateway import router as ai_gateway_router
from app.api.admin.ai_health import AdminAIHealthController
from app.api.admin.ai_health import router as ai_health_router
from app.api.admin.ai_models import AdminAIModelController
from app.api.admin.ai_models import router as ai_models_router
from app.api.admin.ai_providers import AdminAIProviderController
from app.api.admin.ai_providers import router as ai_providers_router
from app.api.admin.ai_quotas import AdminAIQuotaController
from app.api.admin.ai_quotas import router as ai_quotas_router
from app.api.admin.ai_table_policies import AdminAITablePolicyController
from app.api.admin.ai_table_policies import router as ai_table_policies_router
from app.api.admin.ai_usage import AdminAIUsageController
from app.api.admin.ai_usage import router as ai_usage_router
from app.api.admin.analytics import router as analytics_router
from app.api.admin.attachments import AdminAttachmentController
from app.api.admin.attachments import router as attachments_router
from app.api.admin.auth import router as auth_router
from app.api.admin.cache import AdminCacheController
from app.api.admin.cache import router as cache_router
from app.api.admin.codegen import AdminCodegenController
from app.api.admin.codegen import router as codegen_router
from app.api.admin.configs import AdminConfigController
from app.api.admin.configs import router as configs_router
from app.api.admin.dashboard import router as dashboard_router
from app.api.admin.email_logs import AdminEmailLogController
from app.api.admin.email_logs import router as email_logs_router
from app.api.admin.knowledge_bases import AdminKnowledgeBaseController
from app.api.admin.knowledge_bases import router as ai_knowledge_bases_router
from app.api.admin.notification_preferences import (
    router as notification_preferences_router,
)
from app.api.admin.preferences import router as preferences_router
from app.api.admin.notification_templates import AdminNotificationTemplateController
from app.api.admin.notification_templates import router as notification_templates_router
from app.api.admin.notifications import router as notifications_router
from app.api.admin.operation_logs import AdminOperationLogController
from app.api.admin.operation_logs import router as operation_logs_router
from app.api.admin.periodic_tasks import AdminPeriodicTaskController
from app.api.admin.periodic_tasks import router as periodic_tasks_router
from app.api.admin.permissions import AdminPermissionController
from app.api.admin.permissions import router as permissions_router
from app.api.admin.plans import AdminPlanController
from app.api.admin.plans import router as plans_router
from app.api.admin.plugins import AdminPluginController
from app.api.admin.plugins import router as plugins_router
from app.api.admin.recycle_bin import AdminRecycleBinController
from app.api.admin.recycle_bin import router as recycle_bin_router
from app.api.admin.organization import AdminOrganizationController
from app.api.admin.organization import router as organization_router
from app.api.admin.skill_packages import AdminSkillPackageController
from app.api.admin.skill_packages import router as ai_skill_packages_router
from app.api.admin.skills import AdminSkillController
from app.api.admin.skills import router as ai_skills_router
from app.api.admin.system_logs import AdminSystemLogController
from app.api.admin.system_logs import router as system_logs_router
from app.api.admin.tasks import AdminTaskController
from app.api.admin.tasks import router as tasks_router

# Must import tenants before tenant_admins/tenant_domains so menu:admin.tenant is registered first
# 必须先导入 tenants，注册 menu:admin.tenant，否则 tenant_admins/tenant_domains 的操作权限找不到父菜单
from app.api.admin.tenants import AdminTenantController
from app.api.admin.tenants import router as tenants_router
from app.api.admin.tenant_admins import AdminTenantAdminController
from app.api.admin.tenant_admins import router as tenant_admins_router
from app.api.admin.tenant_domains import AdminTenantDomainController
from app.api.admin.tenant_domains import router as tenant_domains_router
from app.api.admin.users import AdminUserController
from app.api.admin.users import router as users_router
from app.api.admin.ws import router as ws_router

# 创建平台管理后台路由器 / Create platform admin router
admin_router = APIRouter()

# 注册子路由 / Register sub-routers
admin_router.include_router(auth_router)
admin_router.include_router(dashboard_router)
admin_router.include_router(analytics_router)
admin_router.include_router(permissions_router)
admin_router.include_router(organization_router)
admin_router.include_router(users_router)
admin_router.include_router(tenants_router)
admin_router.include_router(tenant_domains_router)
admin_router.include_router(configs_router)
admin_router.include_router(plans_router)
admin_router.include_router(operation_logs_router)
admin_router.include_router(system_logs_router)
admin_router.include_router(attachments_router)
admin_router.include_router(tasks_router)
admin_router.include_router(periodic_tasks_router)
# AI 网关相关 / AI Gateway related
admin_router.include_router(ai_providers_router)
admin_router.include_router(ai_models_router)
admin_router.include_router(ai_api_keys_router)
admin_router.include_router(ai_call_logs_router)
admin_router.include_router(ai_gateway_router)
admin_router.include_router(ai_usage_router)
admin_router.include_router(ai_health_router)
admin_router.include_router(ai_quotas_router)
# 对话管理 / Conversation management
admin_router.include_router(ai_conversations_router)
# 智能体引擎 / Agent engine
admin_router.include_router(ai_agents_router)
# AI 操作审计 / AI action audit
admin_router.include_router(ai_action_logs_router)
# AI 对话 / AI chat
admin_router.include_router(ai_agent_chat_router)
# 知识库监控 / Knowledge base monitoring
admin_router.include_router(ai_knowledge_bases_router)
# AI 表策略 / AI table policies
admin_router.include_router(ai_table_policies_router)
# 技能包 & 技能管理 / Skill package & skill management
admin_router.include_router(ai_skill_packages_router)
admin_router.include_router(ai_skills_router)
# 系统智能体绑定 / System agent assignments
admin_router.include_router(agent_assignments_router)
admin_router.include_router(email_logs_router)
# 总回收站 / Global recycle bin
admin_router.include_router(recycle_bin_router)
# WebSocket 在线状态 / WebSocket online status
admin_router.include_router(ws_router)
# 企业管理员管理 / Tenant admin management
admin_router.include_router(tenant_admins_router)
# 通知 / Notifications
admin_router.include_router(notifications_router)
# 通知偏好 / Notification preferences
admin_router.include_router(notification_preferences_router)
# 偏好设置 / User preferences
admin_router.include_router(preferences_router)
# 通知模板管理 / Notification template management
admin_router.include_router(notification_templates_router)
# 插件管理 / Plugin management
admin_router.include_router(plugins_router)
# AI 写作 / AI Writing
admin_router.include_router(ai_writing_router)
# 缓存管理 / Cache management
admin_router.include_router(cache_router)
# 代码生成器 / Codegen (DEBUG only)
admin_router.include_router(codegen_router)

__all__ = [
    "admin_router",
    # 导出控制器类，确保权限装饰器被执行 / Export controller classes to ensure permission decorators are executed
    "AdminPermissionController",
    "AdminOrganizationController",
    "AdminTenantController",
    "AdminTenantDomainController",
    "AdminUserController",
    "AdminConfigController",
    "AdminPlanController",
    "AdminOperationLogController",
    "AdminSystemLogController",
    "AdminAttachmentController",
    "AdminTaskController",
    "AdminPeriodicTaskController",
    # AI 网关 / AI Gateway
    "AdminAIProviderController",
    "AdminAIModelController",
    "AdminAIApiKeyController",
    "AdminAICallLogController",
    "AdminAIGatewayController",
    "AdminAIUsageController",
    "AdminAIHealthController",
    "AdminAIQuotaController",
    # 对话管理 / Conversation management
    "AdminAIConversationController",
    # 智能体引擎 / Agent engine
    "AdminAgentController",
    # AI 操作审计 / AI action audit
    "AdminAIActionLogController",
    # AI 对话 / AI chat
    "AdminAgentChatController",
    # 知识库监控 / Knowledge base monitoring
    "AdminKnowledgeBaseController",
    # AI 表策略 / AI table policies
    "AdminAITablePolicyController",
    # 技能包 & 技能管理 / Skill package & skill management
    "AdminSkillPackageController",
    "AdminSkillController",
    # 系统智能体绑定 / System agent assignments
    "AdminAgentAssignmentController",
    "AdminEmailLogController",
    "AdminTenantAdminController",
    # 总回收站 / Global recycle bin
    "AdminRecycleBinController",
    # 通知模板 / Notification templates
    "AdminNotificationTemplateController",
    # 插件 / Plugins
    "AdminPluginController",
    # 缓存管理 / Cache management
    "AdminCacheController",
    # 代码生成器 / Codegen
    "AdminCodegenController",
]
