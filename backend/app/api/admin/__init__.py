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
]
