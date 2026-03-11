"""
租户管理员管理 API（平台端） / Tenant Admin Management API (Platform)

平台管理员查看/创建/管理指定租户的管理员。
Platform admins view/create/manage admins for specified tenants.
使用独立资源码 tenant_admin，权限与租户资源分离。
Uses independent resource code tenant_admin, permissions separated from tenant resource.
"""

from fastapi import HTTPException, Request, status
from pydantic import BaseModel, Field

from app.core.base_controller import GlobalController
from app.core.deps import ActiveAdmin, DbSession
from app.core.i18n import _
from app.core.response import created, success
from app.core.security import get_password_hash
from app.enums import ErrorCode
from app.enums.rbac import PermissionScope
from app.exceptions import BusinessException
from app.rbac.decorators import (
    action_create,
    action_read,
    action_update,
    permission_resource,
)
from app.services.system import TenantService

# ==========================================
# 请求/响应 Schema / Request/Response Schema
# ==========================================

class TenantAdminCreateRequest(BaseModel):
    """创建租户管理员请求 / Create tenant admin request"""
    username: str = Field(..., min_length=2, max_length=50)
    email: str = Field(..., max_length=255)
    password: str = Field(..., min_length=6, max_length=100)
    nickname: str | None = Field(None, max_length=100)
    role_id: int | None = Field(None)


class TenantAdminUpdateRequest(BaseModel):
    """更新租户管理员请求（平台端重置密码等） / Update tenant admin request (platform-side password reset etc.)"""
    password: str | None = Field(None, min_length=6, max_length=100)
    nickname: str | None = Field(None, max_length=100)
    role_id: int | None = Field(None)
    is_active: bool | None = Field(None)


class TenantAdminStatusRequest(BaseModel):
    """切换管理员状态请求 / Toggle admin status request"""
    is_active: bool


# ==========================================
# Controller
# ==========================================

@permission_resource(
    resource="tenant_admin",
    name="menu.admin.tenant_admin",
    scope=PermissionScope.ADMIN_ONLY,
    parent_resource="tenant",
    menu=None,
)
class AdminTenantAdminController(GlobalController):
    """
    租户管理员管理控制器 / Tenant Admin Management Controller

    平台管理员可查看/创建/禁用指定租户的管理员。
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
            """验证租户存在 / Verify tenant exists"""
            tenant_service = TenantService(db)
            tenant = await tenant_service.get_by_id(tenant_id)
            if tenant is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=_("tenant.not_found"),
                )
            return tenant

        @router.get("", summary="获取租户管理员列表")
        @action_read("action.tenant_admin.list")
        async def list_tenant_admins(
            request: Request,
            db: DbSession,
            admin: ActiveAdmin,
            tenant_id: int,
        ):
            """
            获取指定租户下所有管理员列表 / Get all admin list for specified tenant

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
                .options(selectinload(TenantAdmin.role))
                .order_by(TenantAdmin.is_owner.desc(), TenantAdmin.created_at.asc())
            )
            admins = list(result.scalars().all())

            items = []
            for ta in admins:
                items.append({
                    "id": ta.id,
                    "username": ta.username,
                    "email": ta.email,
                    "nickname": ta.nickname,
                    "avatar": ta.avatar,
                    "is_owner": ta.is_owner,
                    "is_active": ta.is_active,
                    "role_name": ta.role.name if ta.role else None,
                    "role_id": ta.role_id,
                    "last_login_at": ta.last_login_at.isoformat() if ta.last_login_at else None,
                    "last_login_ip": ta.last_login_ip,
                    "created_at": ta.created_at.isoformat() if ta.created_at else None,
                })

            return success(data=items)

        @router.post("", summary="为租户创建管理员")
        @action_create("action.tenant_admin.create")
        async def create_tenant_admin(
            request: Request,
            db: DbSession,
            admin: ActiveAdmin,
            tenant_id: int,
            data: TenantAdminCreateRequest,
        ):
            """
            为指定租户创建新管理员 / Create new admin for specified tenant

            - 自动设置 tenant_id 和 is_owner=False / Auto-set tenant_id and is_owner=False
            - 验证用户名/邮箱在该租户内唯一 / Validate username/email uniqueness within the tenant
            """
            await _verify_tenant(db, tenant_id)

            from sqlalchemy import or_, select

            from app.models import TenantAdmin

            # 验证用户名/邮箱唯一性 / Validate username/email uniqueness
            existing = await db.execute(
                select(TenantAdmin).where(
                    TenantAdmin.tenant_id == tenant_id,
                    TenantAdmin.is_deleted.is_(False),
                    or_(
                        TenantAdmin.username == data.username,
                        TenantAdmin.email == data.email,
                    ),
                )
            )
            if existing.scalar_one_or_none():
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=_("tenant_admin.username_or_email_exists"),
                )

            # 检查管理员数配额 / Check admin count quota
            from sqlalchemy.orm import selectinload as _sil

            from app.models.tenant.tenant import Tenant
            from app.services.tenant.quota_service import QuotaService
            tenant_obj = (await db.execute(
                select(Tenant)
                .options(_sil(Tenant.tenant_plan))
                .where(Tenant.id == tenant_id)
            )).scalar_one_or_none()
            if tenant_obj:
                quota_svc = QuotaService(db, tenant_obj)
                quota_check = await quota_svc.check_admin_quota()
                if not quota_check.allowed:
                    raise BusinessException(
                        message=quota_check.message or _("quota.admins_exceeded"),
                        code=ErrorCode.CONFLICT,
                    )

            # 创建管理员 / Create admin
            new_admin = TenantAdmin(
                tenant_id=tenant_id,
                username=data.username,
                email=data.email,
                password_hash=get_password_hash(data.password),
                nickname=data.nickname,
                role_id=data.role_id,
                is_owner=False,
                is_active=True,
            )
            db.add(new_admin)
            await db.flush()

            return created(data={
                "id": new_admin.id,
                "username": new_admin.username,
                "email": new_admin.email,
                "nickname": new_admin.nickname,
                "is_owner": new_admin.is_owner,
                "is_active": new_admin.is_active,
            })

        @router.put("/{admin_id}", summary="更新租户管理员")
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
            更新租户管理员信息（含重置密码） / Update tenant admin info (including password reset)

            平台管理员可修改租户管理员的密码、昵称、角色、状态。
            Platform admin can modify tenant admin's password, nickname, role, and status.
            至少需要一个字段有值。
            At least one field must have a value.
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

            if data.password is not None:
                tenant_admin.password_hash = get_password_hash(data.password)
            if data.nickname is not None:
                tenant_admin.nickname = data.nickname
            if data.role_id is not None:
                tenant_admin.role_id = data.role_id
            if data.is_active is not None:
                if tenant_admin.is_owner and not data.is_active:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=_("tenant_admin.cannot_disable_owner"),
                    )
                tenant_admin.is_active = data.is_active

            await db.flush()

            return success(data={
                "id": tenant_admin.id,
                "username": tenant_admin.username,
                "nickname": tenant_admin.nickname,
                "role_id": tenant_admin.role_id,
                "is_active": tenant_admin.is_active,
            })

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
            切换租户管理员的启用/禁用状态 / Toggle tenant admin enable/disable status

            不可禁用租户所有者（is_owner=True）。
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

            return success(data={
                "id": tenant_admin.id,
                "is_active": tenant_admin.is_active,
            })


# 创建 router（GlobalController 自动注册路由） / Create router (GlobalController auto-registers routes)
_controller = AdminTenantAdminController()
router = _controller.router
