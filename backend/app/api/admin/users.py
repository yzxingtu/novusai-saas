"""
平台管理员用户 API / Platform Admin User API

提供平台管理员相关操作（如强制下线）
Provides platform admin related operations (e.g. force logout).
"""

from sqlalchemy import select

from app.core.base_controller import GlobalController
from app.core.deps import ActiveAdmin, DbSession
from app.core.i18n import _
from app.core.response import success
from app.enums.rbac import PermissionScope
from app.exceptions import NotFoundException
from app.models.system.admin import Admin
from app.rbac.decorators import action_create, auth_only, permission_resource
from app.services.common import AuthService


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
