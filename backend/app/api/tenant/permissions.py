"""
租户管理员权限 API

提供租户端权限树、菜单等接口
"""

from fastapi import Request

from app.core.base_controller import TenantController
from app.core.deps import ActiveTenantAdmin, DbSession
from app.core.i18n import _
from app.core.response import success
from app.enums.rbac import PermissionScope
from app.rbac.decorators import (
    auth_only,
    permission_resource,
)
from app.rbac.services import PermissionService


@permission_resource(
    resource="permission",
    name="menu.tenant.permission",  # i18n key
    scope=PermissionScope.ALL_TENANTS,
    # 不传 menu 参数 = 不注册菜单权限，仅提供 API 端点
)
class TenantPermissionController(TenantController):
    """
    租户权限控制器

    提供权限树、菜单树等查询接口
    """

    prefix = "/permissions"
    tags = ["Permission Management (Tenant)"]

    def _register_routes(self) -> None:
        """注册路由"""
        router = self.router

        @router.get("", summary="获取权限树")
        @auth_only
        async def get_permission_tree(
            request: Request,
            db: DbSession,
            current_admin: ActiveTenantAdmin,
        ):
            """
            获取租户端权限（树形结构）

            用于角色权限配置页面。

            层级权限控制：
            - 租户所有者：返回所有权限
            - 普通管理员：返回自己拥有的权限（含继承）
            """
            perm_service = PermissionService(db)
            tree = await perm_service.get_tenant_permission_tree(current_admin)
            return success(data=tree, message=_("common.success"))

        @router.get("/menus", summary="获取当前用户菜单")
        @auth_only
        async def get_current_user_menus(
            request: Request,
            db: DbSession,
            current_admin: ActiveTenantAdmin,
        ):
            """
            获取当前租户管理员的菜单列表

            根据角色权限过滤，用于前端动态渲染菜单

            菜单可见性规则：
            - 用户明确拥有的菜单权限（menu:xxx）
            - 用户拥有任意操作权限时，自动显示操作权限的父级菜单及其所有祖先菜单

            响应中每个菜单节点包含 permissions 字段，列出该菜单下用户拥有的操作权限码
            """
            perm_service = PermissionService(db)
            menus = await perm_service.get_tenant_admin_menus(current_admin)
            return success(data=menus, message=_("common.success"))


# 导出路由器
router = TenantPermissionController.get_router()

__all__ = ["router", "TenantPermissionController"]
