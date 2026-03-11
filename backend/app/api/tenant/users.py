"""
租户用户管理 API（租户端） / Tenant User Management API (Tenant Side)

提供租户业务用户的 CRUD、重置密码、状态切换、审批等接口
Provides tenant user CRUD, password reset, status toggle, approval endpoints
"""

from fastapi import Query, Request

from app.core.base_controller import TenantController
from app.core.deps import ActiveTenantAdmin, DbSession, QueryParams
from app.core.i18n import _
from app.core.response import created, deleted, paginated, success, updated
from app.core.security import get_password_hash
from app.enums.rbac import PermissionScope
from app.exceptions import NotFoundException
from app.rbac.decorators import (
    action_create,
    action_delete,
    action_read,
    action_update,
    permission_resource,
)
from app.schemas.tenant import (
    TenantUserCreateRequest,
    TenantUserResponse,
    TenantUserUpdateRequest,
)
from app.services.tenant.tenant_user_service import TenantUserService


def _serialize_user(user) -> dict:
    """序列化用户信息 / Serialize user info"""
    return {
        "id": user.id,
        "tenant_id": user.tenant_id,
        "username": user.username,
        "email": user.email,
        "phone": user.phone,
        "nickname": user.nickname,
        "avatar": user.avatar,
        "gender": user.gender,
        "is_active": user.is_active,
        "approval_status": user.approval_status,
        "role_id": user.role_id,
        "role_name": user.role.name if user.role else None,
        "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "updated_at": user.updated_at.isoformat() if user.updated_at else None,
    }


@permission_resource(
    resource="tenant_user",
    name="menu.tenant.tenant_user",
    scope=PermissionScope.ALL_TENANTS,
    parent_resource="system",
)
class TenantUserController(TenantController):
    """
    租户用户管理控制器 / Tenant User Management Controller

    提供租户业务用户 CRUD、密码重置、状态切换、审批等接口
    Provides tenant user CRUD, password reset, status toggle, approval endpoints
    """

    prefix = "/users"
    tags = ["Tenant User Management"]

    def _register_routes(self) -> None:
        """注册路由 / Register routes"""
        router = self.router

        @router.get("", summary="获取用户列表")
        @action_read("action.tenant_user.list")
        async def list_users(
            request: Request,
            db: DbSession,
            current_admin: ActiveTenantAdmin,
            query: QueryParams,
        ):
            """获取租户用户分页列表 / Get tenant user paginated list"""
            service = TenantUserService(db, current_admin.tenant_id)
            items, total = await service.query_list(spec=query)

            return paginated(
                items=[_serialize_user(item) for item in items],
                total=total,
                page=query.page,
                page_size=query.size,
            )

        @router.get("/{user_id}", summary="获取用户详情")
        @action_read("action.tenant_user.detail")
        async def get_user(
            request: Request,
            db: DbSession,
            current_admin: ActiveTenantAdmin,
            user_id: int,
        ):
            """获取单个租户用户详情 / Get single tenant user details"""
            service = TenantUserService(db, current_admin.tenant_id)
            user = await service.get_by_id(user_id)
            if not user:
                raise NotFoundException(message=_("tenant_user.not_found"))

            return success(data=_serialize_user(user))

        @router.post("", summary="创建用户")
        @action_create("action.tenant_user.create")
        async def create_user(
            request: Request,
            db: DbSession,
            current_admin: ActiveTenantAdmin,
            data: TenantUserCreateRequest,
        ):
            """创建租户用户 / Create tenant user"""
            service = TenantUserService(db, current_admin.tenant_id)
            user = await service.create_user(
                username=data.username,
                email=data.email,
                password=data.password,
                phone=data.phone,
                nickname=data.nickname,
                is_active=data.is_active,
                role_id=data.role_id if hasattr(data, "role_id") else None,
            )

            return created(data=_serialize_user(user))

        @router.put("/{user_id}", summary="更新用户")
        @action_update("action.tenant_user.update")
        async def update_user(
            request: Request,
            db: DbSession,
            current_admin: ActiveTenantAdmin,
            user_id: int,
            data: TenantUserUpdateRequest,
        ):
            """更新租户用户信息 / Update tenant user info"""
            service = TenantUserService(db, current_admin.tenant_id)
            update_data = data.model_dump(exclude_unset=True)
            user = await service.update_user(user_id, update_data)

            return updated(data=_serialize_user(user))

        @router.delete("/{user_id}", summary="删除用户")
        @action_delete("action.tenant_user.delete")
        async def delete_user(
            request: Request,
            db: DbSession,
            current_admin: ActiveTenantAdmin,
            user_id: int,
        ):
            """删除租户用户 / Delete tenant user"""
            service = TenantUserService(db, current_admin.tenant_id)
            await service.delete(user_id)

            return deleted()

        @router.put("/{user_id}/status", summary="切换用户状态")
        @action_update("action.tenant_user.toggle")
        async def toggle_user_status(
            request: Request,
            db: DbSession,
            current_admin: ActiveTenantAdmin,
            user_id: int,
            is_active: bool = Query(...),
        ):
            """切换用户启用/禁用状态 / Toggle user enabled/disabled status"""
            service = TenantUserService(db, current_admin.tenant_id)
            user = await service.toggle_status(user_id, is_active)

            return success(data=_serialize_user(user))

        @router.put("/{user_id}/reset-password", summary="重置用户密码")
        @action_update("action.tenant_user.reset_password")
        async def reset_user_password(
            request: Request,
            db: DbSession,
            current_admin: ActiveTenantAdmin,
            user_id: int,
            data: dict,
        ):
            """重置用户密码（管理员操作） / Reset user password (admin operation)"""
            new_password = data.get("new_password", "")
            if not new_password or len(new_password) < 6:
                from app.exceptions import ValidationException
                raise ValidationException(
                    message=_("auth.password_too_short"),
                )

            service = TenantUserService(db, current_admin.tenant_id)
            await service.reset_password(user_id, new_password)

            return success(message=_("auth.password_reset_success"))

        @router.put("/{user_id}/approve", summary="审批通过用户")
        @action_update("action.tenant_user.approve")
        async def approve_user(
            request: Request,
            db: DbSession,
            current_admin: ActiveTenantAdmin,
            user_id: int,
        ):
            """审批通过用户注册 / Approve user registration"""
            service = TenantUserService(db, current_admin.tenant_id)
            user = await service.approve_user(user_id)

            return success(data=_serialize_user(user))

        @router.put("/{user_id}/reject", summary="审批拒绝用户")
        @action_update("action.tenant_user.reject")
        async def reject_user(
            request: Request,
            db: DbSession,
            current_admin: ActiveTenantAdmin,
            user_id: int,
        ):
            """审批拒绝用户注册 / Reject user registration"""
            service = TenantUserService(db, current_admin.tenant_id)
            user = await service.reject_user(user_id)

            return success(data=_serialize_user(user))

        @router.put("/batch/approve", summary="批量审批通过")
        @action_update("action.tenant_user.approve")
        async def batch_approve(
            request: Request,
            db: DbSession,
            current_admin: ActiveTenantAdmin,
            data: dict,
        ):
            """批量审批通过用户 / Batch approve users"""
            user_ids = data.get("ids", [])
            service = TenantUserService(db, current_admin.tenant_id)
            users = await service.batch_approve(user_ids)

            return success(data=[_serialize_user(u) for u in users])

        @router.put("/batch/reject", summary="批量审批拒绝")
        @action_update("action.tenant_user.reject")
        async def batch_reject(
            request: Request,
            db: DbSession,
            current_admin: ActiveTenantAdmin,
            data: dict,
        ):
            """批量审批拒绝用户 / Batch reject users"""
            user_ids = data.get("ids", [])
            service = TenantUserService(db, current_admin.tenant_id)
            users = await service.batch_reject(user_ids)

            return success(data=[_serialize_user(u) for u in users])


_controller = TenantUserController()
router = _controller.router
