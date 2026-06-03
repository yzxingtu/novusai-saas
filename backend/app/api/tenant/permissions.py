"""
企业管理员权限 API / Tenant Admin Permission API

提供企业端权限树、菜单等接口
Provides tenant permission tree, menu endpoints
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
    name="menu.tenant.permission",  # i18n key / 菜单 i18n 键名
    scope=PermissionScope.TENANT,
    parent_resource="system",
    # 不传 menu 参数 = 不注册菜单权限，仅提供 API 端点 / No menu param = no menu permission, API endpoints only
)
class TenantPermissionController(TenantController):
    """
    企业权限控制器 / Tenant Permission Controller

    提供权限树、菜单树等查询接口
    Provides permission tree, menu tree query endpoints
    """

    prefix = "/permissions"
    tags = ["Permission Management (Tenant)"]

    def _register_routes(self) -> None:
        """注册路由 / Register routes"""
        router = self.router

        @router.get("", summary="获取权限树")
        @auth_only
        async def get_permission_tree(
            request: Request,
            db: DbSession,
            current_admin: ActiveTenantAdmin,
        ):
            """
            获取企业端权限（树形结构） / Get tenant permissions (tree structure)

            用于角色权限配置页面。 / Used for role permission configuration page.

            层级权限控制： / Hierarchical permission control:
            - 企业所有者：返回所有权限 / Tenant owner: returns all permissions
            - 普通管理员：返回自己拥有的权限（含继承） / Regular admin: returns owned permissions (including inherited)
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
            获取当前企业管理员的菜单列表 / Get current tenant admin menu list

            根据角色权限过滤，用于前端动态渲染菜单
            Filtered by role permissions, used for frontend dynamic menu rendering

            菜单可见性规则： / Menu visibility rules:
            - 用户明确拥有的菜单权限（menu:xxx） / User explicitly has menu permission (menu:xxx)
            - 用户拥有任意操作权限时，自动显示操作权限的父级菜单及其所有祖先菜单 / When user has any action permission, auto-show parent menus and all ancestor menus

            响应中每个菜单节点包含 permissions 字段，列出该菜单下用户拥有的操作权限码
            Each menu node includes permissions field listing user's action permission codes under that menu
            """
            perm_service = PermissionService(db)
            menus = await perm_service.get_tenant_admin_menus(current_admin)
            return success(data=menus, message=_("common.success"))


# 导出路由器 / Export router
router = TenantPermissionController.get_router()

__all__ = ["router", "TenantPermissionController"]
