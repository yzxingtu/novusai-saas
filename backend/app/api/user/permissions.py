"""
用户端权限 API

提供用户端菜单等接口
"""

from fastapi import Request

from app.core.base_controller import BaseController
from app.core.deps import ActiveTenantUser, DbSession
from app.core.i18n import _
from app.core.response import success
from app.enums.rbac import PermissionScope
from app.rbac.decorators import (
    auth_only,
    permission_resource,
)
from app.rbac.services import PermissionService


@permission_resource(
    resource="user_permission",
    name="menu.user.permission",
    scope=PermissionScope.TENANT_USER,
    parent_resource="menu",
)
class UserPermissionController(BaseController):
    """
    用户端权限控制器

    提供菜单树查询接口
    """

    prefix = "/permissions"
    tags = ["Permission Management (User)"]

    def _register_routes(self) -> None:
        """注册路由"""
        router = self.router

        @router.get("/menus", summary="获取当前用户菜单")
        @auth_only
        async def get_current_user_menus(
            request: Request,
            db: DbSession,
            current_user: ActiveTenantUser,
        ):
            """
            获取当前租户业务用户的菜单列表

            根据角色权限过滤，用于前端动态渲染菜单
            """
            perm_service = PermissionService(db)
            menus = await perm_service.get_tenant_user_menus(current_user)
            return success(data=menus, message=_("common.success"))


# 导出路由器
router = UserPermissionController.get_router()

__all__ = ["router", "UserPermissionController"]
