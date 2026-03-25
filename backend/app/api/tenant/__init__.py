"""
企业管理后台 API 路由模块 / Tenant admin API router module.

聚合所有企业管理后台的 API 路由 / Aggregates all tenant admin API routes.

控制器类使用 @permission_resource 装饰器定义资源权限，
导入控制器类时会自动注册权限到 PermissionRegistry。
Controllers use @permission_resource to define resource permissions; importing registers them to PermissionRegistry.
"""

from fastapi import APIRouter

from app.api.tenant.agent_chat import TenantAgentChatController
from app.api.tenant.agent_chat import router as agent_chat_router
from app.api.tenant.agents import TenantAgentController
from app.api.tenant.agents import router as agents_router
from app.api.tenant.ai_action_logs import TenantAIActionLogController
from app.api.tenant.ai_action_logs import router as ai_action_logs_router
from app.api.tenant.ai_writing import router as ai_writing_router
from app.api.tenant.ai_call_logs import TenantAICallLogController
from app.api.tenant.ai_call_logs import router as ai_call_logs_router
from app.api.tenant.ai_config import TenantAIConfigController
from app.api.tenant.ai_config import router as ai_config_router
from app.api.tenant.ai_gateway import TenantAIGatewayController
from app.api.tenant.ai_gateway import router as ai_gateway_router
from app.api.tenant.ai_quotas import TenantAIQuotaController
from app.api.tenant.ai_quotas import router as ai_quotas_router
from app.api.tenant.ai_usage import TenantAIUsageController
from app.api.tenant.ai_usage import router as ai_usage_router
from app.api.tenant.analytics import router as analytics_router
from app.api.tenant.attachments import TenantAttachmentController
from app.api.tenant.attachments import router as attachments_router
from app.api.tenant.auth import router as auth_router
from app.api.tenant.configs import TenantConfigController
from app.api.tenant.configs import router as configs_router
from app.api.tenant.conversations import TenantConversationController
from app.api.tenant.conversations import router as conversations_router
from app.api.tenant.dashboard import router as dashboard_router
from app.api.tenant.domains import TenantDomainController
from app.api.tenant.domains import router as domains_router
from app.api.tenant.knowledge_bases import TenantKnowledgeBaseController
from app.api.tenant.knowledge_bases import router as knowledge_bases_router
from app.api.tenant.notification_preferences import (
    router as notification_preferences_router,
)
from app.api.tenant.preferences import router as preferences_router
from app.api.tenant.notifications import router as notifications_router
from app.api.tenant.operation_logs import TenantOperationLogController
from app.api.tenant.operation_logs import router as operation_logs_router
from app.api.tenant.permissions import TenantPermissionController
from app.api.tenant.permissions import router as permissions_router
from app.api.tenant.permission_roles import TenantPermissionRoleController
from app.api.tenant.permission_roles import router as permission_roles_router
from app.api.tenant.plugins import router as plugins_router
from app.api.tenant.organization import TenantOrganizationController
from app.api.tenant.organization import router as organization_router
from app.api.tenant.user_roles import TenantUserRoleController
from app.api.tenant.user_roles import router as user_roles_router
from app.api.tenant.users import TenantUserController
from app.api.tenant.users import router as users_router
from app.api.tenant.ws import router as ws_router

# 创建企业管理后台路由器 / Create tenant admin router
tenant_router = APIRouter()

# 注册子路由 / Register sub-routers
tenant_router.include_router(auth_router)
tenant_router.include_router(dashboard_router)
tenant_router.include_router(configs_router)
tenant_router.include_router(attachments_router)
tenant_router.include_router(domains_router)
tenant_router.include_router(operation_logs_router)
tenant_router.include_router(permissions_router)
tenant_router.include_router(permission_roles_router)
tenant_router.include_router(organization_router)
tenant_router.include_router(users_router)
tenant_router.include_router(user_roles_router)
# AI 网关相关 / AI gateway
tenant_router.include_router(ai_config_router)
tenant_router.include_router(ai_gateway_router)
tenant_router.include_router(ai_quotas_router)
tenant_router.include_router(ai_usage_router)
tenant_router.include_router(ai_call_logs_router)
# 智能体 / Agents
tenant_router.include_router(agents_router)
# 对话管理 / Conversations
tenant_router.include_router(conversations_router)
# AI 对话 / AI chat
tenant_router.include_router(agent_chat_router)
# AI 操作审计 / AI action logs
tenant_router.include_router(ai_action_logs_router)
# 知识库 / Knowledge bases
tenant_router.include_router(knowledge_bases_router)
# WebSocket 在线状态 / WebSocket online status
tenant_router.include_router(ws_router)
# 通知 / Notifications
tenant_router.include_router(notifications_router)
# 通知偏好 / Notification preferences
tenant_router.include_router(notification_preferences_router)
# 偏好设置 / User preferences
tenant_router.include_router(preferences_router)
# 插件（企业端只读列表，按 scope + 分配过滤）/ Plugins (tenant read-only, scope+assignment)
tenant_router.include_router(plugins_router)
# 数据分析 / Analytics
tenant_router.include_router(analytics_router)
# AI 写作 / AI Writing
tenant_router.include_router(ai_writing_router)

__all__ = [
    "tenant_router",
    # 导出控制器类，确保权限装饰器被执行 / Export controllers for permission decorators
    "TenantConfigController",
    "TenantAttachmentController",
    "TenantDomainController",
    "TenantOperationLogController",
    "TenantPermissionController",
    "TenantPermissionRoleController",
    "TenantOrganizationController",
    "TenantUserController",
    "TenantUserRoleController",
    # AI 网关 / AI gateway
    "TenantAIConfigController",
    "TenantAIGatewayController",
    "TenantAIQuotaController",
    "TenantAIUsageController",
    "TenantAICallLogController",
    # 智能体 / Agents
    "TenantAgentController",
    # 对话管理 / Conversations
    "TenantConversationController",
    # AI 对话 / AI chat
    "TenantAgentChatController",
    # AI 操作审计 / AI action logs
    "TenantAIActionLogController",
    # 知识库 / Knowledge bases
    "TenantKnowledgeBaseController",
]
