"""
企业管理员管理 API（平台端） / Tenant Admin Management API (Platform)

平台管理员查看/创建/管理指定企业的管理员。
Platform admins view/create/manage admins for specified tenants.
使用独立资源码 tenant_admin，权限与企业资源分离。
Uses independent resource code tenant_admin, permissions separated from tenant resource.
"""

from fastapi import HTTPException, Query, Request, status
from pydantic import BaseModel, Field

from app.core.base_controller import GlobalController
from app.core.deps import ActiveAdmin, DbSession
from app.core.i18n import _
from app.core.response import created, serialize_datetime_for_api, success
from app.enums.rbac import PermissionScope
from app.exceptions import BusinessException, NotFoundException
from app.rbac.decorators import (
    action_create,
    action_read,
    action_update,
    permission_resource,
)
from app.services.common import AuthService
from app.services.system import TenantService
from app.services.tenant import TenantAdminService

# ==========================================
# 请求/响应 Schema / Request/Response Schema
# ==========================================


class TenantAdminCreateRequest(BaseModel):
    """创建企业管理员请求 / Create tenant admin request"""

    username: str = Field(..., min_length=2, max_length=50)
    email: str = Field(..., max_length=255)
    password: str = Field(..., min_length=6, max_length=100)
    nickname: str | None = Field(None, max_length=100)
    role_id: int | None = Field(None)
    org_node_id: int | None = Field(None)


class TenantAdminUpdateRequest(BaseModel):
    """更新企业管理员请求（平台端重置密码等） / Update tenant admin request (platform-side password reset etc.)"""

    password: str | None = Field(None, min_length=6, max_length=100)
    nickname: str | None = Field(None, max_length=100)
    role_id: int | None = Field(None)
    org_node_id: int | None = Field(None)
    is_active: bool | None = Field(None)


class TenantAdminStatusRequest(BaseModel):
    """切换管理员状态请求 / Toggle admin status request"""

    is_active: bool


def _raise_http(exc: Exception):
    if isinstance(exc, NotFoundException):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc.message),
        )
    if isinstance(exc, BusinessException):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc.message),
        )
    raise exc


def _serialize_tenant_admin(tenant_admin) -> dict:
    permission_role = getattr(tenant_admin, "role", None)
    org_node = getattr(tenant_admin, "org_node", None)
    return {
        "id": tenant_admin.id,
        "username": tenant_admin.username,
        "email": tenant_admin.email,
        "nickname": tenant_admin.nickname,
        "avatar": tenant_admin.avatar,
        "is_owner": tenant_admin.is_owner,
        "is_active": tenant_admin.is_active,
        "role_name": permission_role.name if permission_role else None,
        "role_id": tenant_admin.role_id,
        "permission_role_name": permission_role.name if permission_role else None,
        "permission_role_id": tenant_admin.role_id,
        "org_node_name": org_node.name if org_node else None,
        "org_node_id": tenant_admin.org_node_id,
        "last_login_at": serialize_datetime_for_api(tenant_admin.last_login_at),
        "last_login_ip": tenant_admin.last_login_ip,
        "created_at": serialize_datetime_for_api(tenant_admin.created_at),
    }


# ==========================================
# Controller / 控制器
# ==========================================


@permission_resource(
    resource="tenant_admin",
    name="menu.admin.tenant_admin",
    scope=PermissionScope.ADMIN,
    parent_resource="tenant",
    menu=None,
)
class AdminTenantAdminController(GlobalController):
    """
    企业管理员管理控制器 / Tenant Admin Management Controller

    平台管理员可查看/创建/禁用指定企业的管理员。
    Platform admins can view/create/disable admins for specified tenants.
    路由嵌套在 /admin/tenants/{tenant_id}/admins 下。
    Routes nested under /admin/tenants/{tenant_id}/admins.
    """

    prefix = "/tenants/{tenant_id}/admins"
    tags = ["Tenant Admin Management"]

    def _register_routes(self) -> None:
        """注册路由 / Register routes"""
        router = self.router

        async def _verify_tenant(db: DbSession, tenant_id: int):
            """验证企业存在 / Verify tenant exists"""
            tenant_service = TenantService(db)
            tenant = await tenant_service.get_by_id(tenant_id)
            if tenant is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=_("tenant.not_found"),
                )
            return tenant

        @router.get("", summary="获取企业管理员列表")
        @action_read("action.tenant_admin.list")
        async def list_tenant_admins(
            request: Request,
            db: DbSession,
            admin: ActiveAdmin,
            tenant_id: int,
        ):
            """
            获取指定企业下所有管理员列表 / Get all admin list for specified tenant

            返回管理员基本信息、角色名、在线状态相关字段。
            Returns admin basic info, role name, and online status related fields.
            """
            await _verify_tenant(db, tenant_id)

            from sqlalchemy import select
            from sqlalchemy.orm import selectinload

            from app.models import TenantAdmin

            result = await db.execute(
                select(TenantAdmin)
                .where(
                    TenantAdmin.tenant_id == tenant_id,
                    TenantAdmin.is_deleted.is_(False),
                )
                .options(
                    selectinload(TenantAdmin.role),
                    selectinload(TenantAdmin.org_node),
                )
                .order_by(TenantAdmin.is_owner.desc(), TenantAdmin.created_at.asc())
            )
            admins = list(result.scalars().all())
            return success(data=[_serialize_tenant_admin(ta) for ta in admins])

        @router.get("/select", summary="获取企业管理员下拉选项")
        @action_read("action.tenant_admin.list")
        async def select_tenant_admins(
            request: Request,
            db: DbSession,
            admin: ActiveAdmin,
            tenant_id: int,
            search: str = Query("", description=_("api.param.search")),
            page: int = Query(1, ge=1, description=_("api.param.page")),
            page_size: int = Query(
                20, ge=1, le=100, description=_("api.param.page_size")
            ),
        ):
            """
            获取企业管理员分页下拉选项 / Get paginated tenant admin select options.
            """
            await _verify_tenant(db, tenant_id)
            response = await TenantAdminService(
                db, tenant_id
            ).get_identity_select_options(
                search=search,
                page=page,
                page_size=page_size,
            )
            return success(data=response, message=_("common.success"))

        @router.post("", summary="为企业创建管理员")
        @action_create("action.tenant_admin.create")
        async def create_tenant_admin(
            request: Request,
            db: DbSession,
            admin: ActiveAdmin,
            tenant_id: int,
            data: TenantAdminCreateRequest,
        ):
            """
            为指定企业创建新管理员 / Create new admin for specified tenant

            - 自动设置 tenant_id 和 is_owner=False / Auto-set tenant_id and is_owner=False
            - 验证用户名/邮箱在该企业内唯一 / Validate username/email uniqueness within the tenant
            """
            await _verify_tenant(db, tenant_id)
            service = TenantAdminService(db, tenant_id)
            try:
                new_admin = await service.create_admin(
                    username=data.username,
                    email=data.email,
                    password=data.password,
                    nickname=data.nickname,
                    is_active=True,
                    is_owner=False,
                    role_id=data.role_id,
                    org_node_id=data.org_node_id,
                )
                await db.flush()
                return created(data=_serialize_tenant_admin(new_admin))
            except Exception as exc:
                _raise_http(exc)

        @router.put("/{admin_id}", summary="更新企业管理员")
        @action_update("action.tenant_admin.update")
        async def update_tenant_admin(
            request: Request,
            db: DbSession,
            admin: ActiveAdmin,
            tenant_id: int,
            admin_id: int,
            data: TenantAdminUpdateRequest,
        ):
            """
            更新企业管理员信息（含重置密码） / Update tenant admin info (including password reset)

            平台管理员可修改企业管理员的密码、昵称、角色、状态。
            Platform admin can modify tenant admin's password, nickname, role, and status.
            至少需要一个字段有值。
            At least one field must have a value.
            """
            await _verify_tenant(db, tenant_id)

            from sqlalchemy import select
            from sqlalchemy.orm import selectinload

            from app.models import TenantAdmin

            result = await db.execute(
                select(TenantAdmin).where(
                    TenantAdmin.id == admin_id,
                    TenantAdmin.tenant_id == tenant_id,
                    TenantAdmin.is_deleted.is_(False),
                )
            )
            tenant_admin = result.scalar_one_or_none()
            if not tenant_admin:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=_("tenant_admin.not_found"),
                )

            if (
                data.is_active is not None
                and tenant_admin.is_owner
                and not data.is_active
            ):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=_("tenant_admin.cannot_disable_owner"),
                )

            service = TenantAdminService(db, tenant_id)
            update_data = data.model_dump(
                exclude_unset=True,
                exclude={"password"},
            )

            try:
                if data.password is not None:
                    await service.reset_password(admin_id, data.password)
                if update_data:
                    await service.update_admin(admin_id, update_data)

                refreshed = await db.execute(
                    select(TenantAdmin)
                    .where(
                        TenantAdmin.id == admin_id,
                        TenantAdmin.tenant_id == tenant_id,
                        TenantAdmin.is_deleted.is_(False),
                    )
                    .options(
                        selectinload(TenantAdmin.role),
                        selectinload(TenantAdmin.org_node),
                    )
                )
                updated_admin = refreshed.scalar_one_or_none()
                if updated_admin is None:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=_("tenant_admin.not_found"),
                    )

                await db.flush()
                return success(data=_serialize_tenant_admin(updated_admin))
            except Exception as exc:
                _raise_http(exc)

        @router.put("/{admin_id}/status", summary="切换管理员状态")
        @action_update("action.tenant_admin.update")
        async def toggle_admin_status(
            request: Request,
            db: DbSession,
            admin: ActiveAdmin,
            tenant_id: int,
            admin_id: int,
            data: TenantAdminStatusRequest,
        ):
            """
            切换企业管理员的启用/禁用状态 / Toggle tenant admin enable/disable status

            不可禁用企业所有者（is_owner=True）。
            Cannot disable tenant owner (is_owner=True).
            """
            await _verify_tenant(db, tenant_id)

            from sqlalchemy import select

            from app.models import TenantAdmin

            result = await db.execute(
                select(TenantAdmin).where(
                    TenantAdmin.id == admin_id,
                    TenantAdmin.tenant_id == tenant_id,
                    TenantAdmin.is_deleted.is_(False),
                )
            )
            tenant_admin = result.scalar_one_or_none()
            if not tenant_admin:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=_("tenant_admin.not_found"),
                )

            if tenant_admin.is_owner and not data.is_active:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=_("tenant_admin.cannot_disable_owner"),
                )

            tenant_admin.is_active = data.is_active
            await db.flush()

            return success(
                data={
                    "id": tenant_admin.id,
                    "is_active": tenant_admin.is_active,
                }
            )

        @router.post("/{admin_id}/force-logout", summary="强制下线企业管理员")
        @action_create("action.tenant_admin.force_logout")
        async def force_logout_tenant_admin(
            request: Request,
            db: DbSession,
            admin: ActiveAdmin,
            tenant_id: int,
            admin_id: int,
        ):
            """
            强制下线指定企业管理员 / Force logout tenant admin
            吊销其所有 Token 并通知前端跳转登录页。
            """
            await _verify_tenant(db, tenant_id)

            from sqlalchemy import select

            from app.models import TenantAdmin

            result = await db.execute(
                select(TenantAdmin).where(
                    TenantAdmin.id == admin_id,
                    TenantAdmin.tenant_id == tenant_id,
                    TenantAdmin.is_deleted.is_(False),
                )
            )
            tenant_admin = result.scalar_one_or_none()
            if not tenant_admin:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=_("tenant_admin.not_found"),
                )

            auth_service = AuthService(db)
            await auth_service.force_logout(
                user_type="tenant_admin",
                user_id=admin_id,
                tenant_id=tenant_id,
            )
            return success(
                message=_("auth.force_logout_success", name=tenant_admin.username),
            )


# 创建 router（GlobalController 自动注册路由） / Create router (GlobalController auto-registers routes)
_controller = AdminTenantAdminController()
router = _controller.router
