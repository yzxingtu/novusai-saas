"""
平台管理后台 API 路由模块

聚合所有平台管理后台的 API 路由

控制器类使用 @permission_resource 装饰器定义资源权限，
导入控制器类时会自动注册权限到 PermissionRegistry。
"""

from fastapi import APIRouter

from app.api.admin.auth import router as auth_router
from app.api.admin.permissions import router as permissions_router, AdminPermissionController
from app.api.admin.roles import router as roles_router, AdminRoleController
from app.api.admin.tenants import router as tenants_router, AdminTenantController
from app.api.admin.tenant_domains import router as tenant_domains_router, AdminTenantDomainController
from app.api.admin.configs import router as configs_router, AdminConfigController
from app.api.admin.plans import router as plans_router, AdminPlanController
from app.api.admin.operation_logs import router as operation_logs_router, AdminOperationLogController
from app.api.admin.system_logs import router as system_logs_router, AdminSystemLogController
from app.api.admin.attachments import router as attachments_router, AdminAttachmentController
from app.api.admin.tasks import router as tasks_router, AdminTaskController
from app.api.admin.periodic_tasks import router as periodic_tasks_router, AdminPeriodicTaskController
from app.api.admin.ai_providers import router as ai_providers_router, AdminAIProviderController
from app.api.admin.ai_models import router as ai_models_router, AdminAIModelController
from app.api.admin.ai_api_keys import router as ai_api_keys_router, AdminAIApiKeyController
from app.api.admin.ai_call_logs import router as ai_call_logs_router, AdminAICallLogController
from app.api.admin.ai_gateway import router as ai_gateway_router, AdminAIGatewayController
from app.api.admin.ai_usage import router as ai_usage_router, AdminAIUsageController
from app.api.admin.ai_health import router as ai_health_router, AdminAIHealthController
from app.api.admin.ai_quotas import router as ai_quotas_router, AdminAIQuotaController

# 创建平台管理后台路由器
admin_router = APIRouter()

# 注册子路由
admin_router.include_router(auth_router)
admin_router.include_router(permissions_router)
admin_router.include_router(roles_router)
admin_router.include_router(tenants_router)
admin_router.include_router(tenant_domains_router)
admin_router.include_router(configs_router)
admin_router.include_router(plans_router)
admin_router.include_router(operation_logs_router)
admin_router.include_router(system_logs_router)
admin_router.include_router(attachments_router)
admin_router.include_router(tasks_router)
admin_router.include_router(periodic_tasks_router)
# AI 网关相关
admin_router.include_router(ai_providers_router)
admin_router.include_router(ai_models_router)
admin_router.include_router(ai_api_keys_router)
admin_router.include_router(ai_call_logs_router)
admin_router.include_router(ai_gateway_router)
admin_router.include_router(ai_usage_router)
admin_router.include_router(ai_health_router)
admin_router.include_router(ai_quotas_router)


__all__ = [
    "admin_router",
    # 导出控制器类，确保权限装饰器被执行
    "AdminPermissionController",
    "AdminRoleController",
    "AdminTenantController",
    "AdminTenantDomainController",
    "AdminConfigController",
    "AdminPlanController",
    "AdminOperationLogController",
    "AdminSystemLogController",
    "AdminAttachmentController",
    "AdminTaskController",
    "AdminPeriodicTaskController",
    # AI 网关
    "AdminAIProviderController",
    "AdminAIModelController",
    "AdminAIApiKeyController",
    "AdminAICallLogController",
    "AdminAIGatewayController",
    "AdminAIUsageController",
    "AdminAIHealthController",
    "AdminAIQuotaController",
]
