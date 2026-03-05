"""
租户管理后台 API 路由模块

聚合所有租户管理后台的 API 路由

控制器类使用 @permission_resource 装饰器定义资源权限，
导入控制器类时会自动注册权限到 PermissionRegistry。
"""

from fastapi import APIRouter

from app.api.tenant.agent_chat import TenantAgentChatController
from app.api.tenant.agent_chat import router as agent_chat_router
from app.api.tenant.agents import TenantAgentController
from app.api.tenant.agents import router as agents_router
from app.api.tenant.ai_action_logs import TenantAIActionLogController
from app.api.tenant.ai_action_logs import router as ai_action_logs_router
from app.api.tenant.ai_call_logs import TenantAICallLogController
from app.api.tenant.ai_call_logs import router as ai_call_logs_router
from app.api.tenant.ai_config import TenantAIConfigController
from app.api.tenant.ai_config import router as ai_config_router
from app.api.tenant.ai_gateway import TenantAIGatewayController
from app.api.tenant.ai_gateway import router as ai_gateway_router
from app.api.tenant.ai_quotas import TenantAIQuotaController
from app.api.tenant.ai_quotas import router as ai_quotas_router
from app.api.tenant.ai_table_policies import TenantAITablePolicyController
from app.api.tenant.ai_table_policies import router as ai_table_policies_router
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
from app.api.tenant.notifications import router as notifications_router
from app.api.tenant.operation_logs import TenantOperationLogController
from app.api.tenant.operation_logs import router as operation_logs_router
from app.api.tenant.periodic_tasks import TenantPeriodicTaskController
from app.api.tenant.periodic_tasks import router as periodic_tasks_router
from app.api.tenant.permissions import TenantPermissionController
from app.api.tenant.permissions import router as permissions_router
from app.api.tenant.plugins import router as plugins_router
from app.api.tenant.roles import TenantRoleController
from app.api.tenant.roles import router as roles_router
from app.api.tenant.skill_packages import TenantSkillPackageController
from app.api.tenant.skill_packages import router as skill_packages_router
from app.api.tenant.skills import TenantSkillController
from app.api.tenant.skills import router as skills_router
from app.api.tenant.tasks import TenantTaskLogController
from app.api.tenant.tasks import router as tasks_router
from app.api.tenant.ws import router as ws_router

# 创建租户管理后台路由器
tenant_router = APIRouter()

# 注册子路由
tenant_router.include_router(auth_router)
tenant_router.include_router(dashboard_router)
tenant_router.include_router(configs_router)
tenant_router.include_router(attachments_router)
tenant_router.include_router(domains_router)
tenant_router.include_router(operation_logs_router)
tenant_router.include_router(permissions_router)
tenant_router.include_router(roles_router)
tenant_router.include_router(tasks_router)
tenant_router.include_router(periodic_tasks_router)
# AI 网关相关
tenant_router.include_router(ai_config_router)
tenant_router.include_router(ai_gateway_router)
tenant_router.include_router(ai_quotas_router)
tenant_router.include_router(ai_usage_router)
tenant_router.include_router(ai_call_logs_router)
# 智能体
tenant_router.include_router(agents_router)
# 对话管理
tenant_router.include_router(conversations_router)
# AI 对话
tenant_router.include_router(agent_chat_router)
# AI 操作审计
tenant_router.include_router(ai_action_logs_router)
# 知识库
tenant_router.include_router(knowledge_bases_router)
# AI 表策略覆盖
tenant_router.include_router(ai_table_policies_router)
# 技能包 & 技能管理
tenant_router.include_router(skill_packages_router)
tenant_router.include_router(skills_router)
# WebSocket 在线状态
tenant_router.include_router(ws_router)
# 通知
tenant_router.include_router(notifications_router)
# 通知偏好
tenant_router.include_router(notification_preferences_router)
# 插件（租户端只读列表，按 scope + 分配过滤）
tenant_router.include_router(plugins_router)
# 数据分析
tenant_router.include_router(analytics_router)


__all__ = [
    "tenant_router",
    # 导出控制器类，确保权限装饰器被执行
    "TenantConfigController",
    "TenantAttachmentController",
    "TenantDomainController",
    "TenantOperationLogController",
    "TenantPeriodicTaskController",
    "TenantPermissionController",
    "TenantRoleController",
    "TenantTaskLogController",
    # AI 网关
    "TenantAIConfigController",
    "TenantAIGatewayController",
    "TenantAIQuotaController",
    "TenantAIUsageController",
    "TenantAICallLogController",
    # 智能体
    "TenantAgentController",
    # 对话管理
    "TenantConversationController",
    # AI 对话
    "TenantAgentChatController",
    # AI 操作审计
    "TenantAIActionLogController",
    # 知识库
    "TenantKnowledgeBaseController",
    # AI 表策略覆盖
    "TenantAITablePolicyController",
    # 技能包 & 技能管理
    "TenantSkillPackageController",
    "TenantSkillController",
]
