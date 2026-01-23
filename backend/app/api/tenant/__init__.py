"""
租户管理后台 API 路由模块

聚合所有租户管理后台的 API 路由

控制器类使用 @permission_resource 装饰器定义资源权限，
导入控制器类时会自动注册权限到 PermissionRegistry。
"""

from fastapi import APIRouter

from app.api.tenant.auth import router as auth_router
from app.api.tenant.configs import router as configs_router, TenantConfigController
from app.api.tenant.domains import router as domains_router, TenantDomainController
from app.api.tenant.operation_logs import router as operation_logs_router, TenantOperationLogController
from app.api.tenant.permissions import router as permissions_router, TenantPermissionController
from app.api.tenant.roles import router as roles_router, TenantRoleController

# 创建租户管理后台路由器
tenant_router = APIRouter()

# 注册子路由
tenant_router.include_router(auth_router)
tenant_router.include_router(configs_router)
tenant_router.include_router(domains_router)
tenant_router.include_router(operation_logs_router)
tenant_router.include_router(permissions_router)
tenant_router.include_router(roles_router)


__all__ = [
    "tenant_router",
    # 导出控制器类，确保权限装饰器被执行
    "TenantConfigController",
    "TenantDomainController",
    "TenantOperationLogController",
    "TenantPermissionController",
    "TenantRoleController",
]
