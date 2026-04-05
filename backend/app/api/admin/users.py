"""
平台管理员用户 API / Platform Admin User API

提供平台管理员相关操作（如强制下线）
Provides platform admin related operations (e.g. force logout).
"""

from fastapi import Query
from sqlalchemy import select

from app.core.base_controller import GlobalController
from app.core.deps import ActiveAdmin, DbSession
from app.core.i18n import _
from app.core.response import success
from app.enums.rbac import PermissionScope
from app.exceptions import NotFoundException
from app.models.system.admin import Admin
from app.rbac.decorators import (
    action_create,
    action_read,
    auth_only,
    permission_resource,
)
from app.services.common import AuthService
from app.services.system.admin_service import AdminService
from app.api.common.identity import serialize_admin_identity_detail


@permission_resource(
    resource="admin_user",
    name="menu.admin.admin_user",
    scope=PermissionScope.ADMIN,
    parent_resource="system",
    menu=None,
)
class AdminUserController(GlobalController):
    """平台管理员用户控制器 / Platform admin user controller"""

    prefix = "/users"
    tags = ["Platform Admin Users"]

    def _register_routes(self) -> None:
        router = self.router

        @router.get("/select", summary="获取平台管理员下拉选项")
        @action_read("action.admin_user.list")
        async def select_admin_users(
            db: DbSession,
            current_admin: ActiveAdmin,
            search: str = Query("", description=_("api.param.search")),
            page: int = Query(1, ge=1, description=_("api.param.page")),
            page_size: int = Query(
                20, ge=1, le=100, description=_("api.param.page_size")
            ),
        ):
            """
            获取平台管理员分页下拉选项 / Get paginated platform admin select options.
            """
            response = await AdminService(db).get_identity_select_options(
                search=search,
                page=page,
                page_size=page_size,
            )
            return success(data=response, message=_("common.success"))

        @router.get("/{user_id}", summary="获取平台管理员详情")
        @action_read("action.admin_user.detail")
        async def get_admin_detail(
            db: DbSession,
            current_admin: ActiveAdmin,
            user_id: int,
        ):
            """
            获取平台管理员详情 / Get platform admin detail.
            """
            admin = await AdminService(db).get_identity_detail(user_id)
            return success(
                data=serialize_admin_identity_detail(admin),
                message=_("common.success"),
            )

        @router.post("/{user_id}/force-logout", summary="强制下线平台管理员")
        @auth_only
        @action_create("action.admin_user.force_logout")
        async def force_logout_admin(
            db: DbSession,
            current_admin: ActiveAdmin,
            user_id: int,
        ):
            """
            强制下线指定平台管理员 / Force logout platform admin
            吊销其所有 Token 并通知前端跳转登录页。
            """
            result = await db.execute(
                select(Admin).where(
                    Admin.id == user_id,
                    Admin.is_deleted.is_(False),
                )
            )
            admin = result.scalar_one_or_none()
            if not admin:
                raise NotFoundException(message=_("admin.not_found"))

            auth_service = AuthService(db)
            await auth_service.force_logout(
                user_type="admin",
                user_id=user_id,
                tenant_id=None,
            )
            return success(
                message=_("auth.force_logout_success", name=admin.username),
            )


_controller = AdminUserController()
router = _controller.router
