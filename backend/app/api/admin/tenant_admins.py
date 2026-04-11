"""
企业管理员管理 API（平台端） / Tenant Admin Management API (Platform)

平台管理员查看/创建/管理指定企业的管理员。
Platform admins view/create/manage admins for specified tenants.
使用独立资源码 tenant_admin，权限与企业资源分离。
Uses independent resource code tenant_admin, permissions separated from tenant resource.
"""

from fastapi import Query, Request
from pydantic import BaseModel, Field

from app.core.base_controller import GlobalController
from app.core.deps import ActiveAdmin, DbSession
from app.core.i18n import _
from app.core.response import created, success
from app.enums.rbac import PermissionScope
from app.rbac.decorators import (
    action_create,
    action_read,
    action_update,
    permission_resource,
)
from app.services.system.tenant_admin_workflow_service import (
    TenantAdminWorkflowService,
)

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
            workflow = TenantAdminWorkflowService(db)
            return success(data=await workflow.list_tenant_admins(tenant_id=tenant_id))

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
            workflow = TenantAdminWorkflowService(db)
            response = await workflow.select_tenant_admins(
                tenant_id=tenant_id,
                search=search,
                page=page,
                page_size=page_size,
            )
            return success(data=response, message=_("common.success"))

        @router.get("/{admin_id}", summary="获取企业管理员详情")
        @action_read("action.tenant_admin.detail")
        async def get_tenant_admin_detail(
            request: Request,
            db: DbSession,
            admin: ActiveAdmin,
            tenant_id: int,
            admin_id: int,
        ):
            workflow = TenantAdminWorkflowService(db)
            tenant_admin = await workflow.get_tenant_admin_detail(
                tenant_id=tenant_id,
                admin_id=admin_id,
            )
            return success(
                data=tenant_admin,
                message=_("common.success"),
            )

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
            workflow = TenantAdminWorkflowService(db)
            new_admin = await workflow.create_tenant_admin(
                tenant_id=tenant_id,
                data=data,
            )
            return created(data=new_admin)

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
            workflow = TenantAdminWorkflowService(db)
            updated_admin = await workflow.update_tenant_admin(
                tenant_id=tenant_id,
                admin_id=admin_id,
                data=data,
            )
            return success(data=updated_admin)

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
            workflow = TenantAdminWorkflowService(db)
            response = await workflow.toggle_admin_status(
                tenant_id=tenant_id,
                admin_id=admin_id,
                is_active=data.is_active,
            )
            return success(data=response)

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
            workflow = TenantAdminWorkflowService(db)
            message = await workflow.force_logout_tenant_admin(
                tenant_id=tenant_id,
                admin_id=admin_id,
            )
            return success(message=message)


# 创建 router（GlobalController 自动注册路由） / Create router (GlobalController auto-registers routes)
_controller = AdminTenantAdminController()
router = _controller.router
