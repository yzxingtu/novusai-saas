"""
租户管理员管理 API

提供租户内管理员 CRUD 接口
"""

from fastapi import HTTPException, Query, Request, status
from pydantic import Field

from app.core.base_controller import TenantController
from app.core.base_schema import BaseSchema, PageParams, PageResponse
from app.core.deps import DbSession, QueryParams, ActiveTenantAdmin
from app.core.i18n import _
from app.core.response import success
from app.schemas.common.query import QuerySpec
from app.enums.rbac import PermissionScope
from app.models import TenantAdmin
from app.rbac.decorators import (
    permission_resource,
    action_read,
    action_create,
    action_update,
    action_delete,
)
from app.schemas.tenant import (
    TenantAdminResponse,
    TenantAdminCreateRequest,
    TenantAdminUpdateRequest,
)
from app.schemas.common.select import SelectResponse
from app.services.tenant import TenantAdminService


class TenantAdminResetPasswordRequest(BaseSchema):
    """重置密码请求"""
    new_password: str = Field(..., min_length=6, max_length=50, description="新密码")


@permission_resource(
    resource="tenant_user",
    name="menu.tenant.tenant_user",  # i18n key
    scope=PermissionScope.TENANT,
    parent_resource="organization",  # 操作权限挂载到组织架构菜单下
)
class TenantAdminController(TenantController):
    """
    租户管理员控制器
    
    提供租户内管理员 CRUD、状态切换、密码重置等接口
    """
    
    prefix = "/admins"
    tags = ["租户管理员管理"]
    service_class = TenantAdminService
    
    def _register_routes(self) -> None:
        """注册路由"""
        router = self.router
        
        @router.get("/select", summary="获取管理员下拉选项")
        @action_read("action.admin.select")
        async def select_admins(
            request: Request,
            db: DbSession,
            current_admin: ActiveTenantAdmin,
            search: str = Query("", description="搜索关键词"),
            is_active: str = Query("", description="筛选状态，默认仅启用"),
            page: int = Query(0, ge=0, description="页码（0=不分页，>=1=分页）"),
            page_size: int = Query(20, ge=1, le=100, description="每页数量"),
        ):
            """
            获取管理员下拉选项
            
            用于表单中的管理员选择组件
            
            分页模式：
            - page=0: 不分页，返回全部数据（受 limit 限制）
            - page>=1: 分页模式，返回分页信息（total, has_more）
            
            权限: tenant_user:select
            """
            # 解析 is_active 参数
            active_filter = True  # 默认仅启用
            if is_active.lower() == "false":
                active_filter = False
            elif is_active.lower() == "true":
                active_filter = True
            
            service = TenantAdminService(db, tenant_id=current_admin.tenant_id)
            response = await service.get_select_options(
                search=search,
                limit=50,
                is_active=active_filter,
                page=page,
                page_size=page_size,
            )
            return success(
                data=response,
                message=_("common.success"),
            )
        
        @router.get("", summary="获取管理员列表")
        @action_read("action.admin.list")
        async def list_admins(
            request: Request,
            db: DbSession,
            spec: QueryParams,
            current_admin: ActiveTenantAdmin,
        ):
            """
            获取当前租户的所有管理员列表
            
            支持 JSON:API 风格筛选参数:
            - filter[username][ilike]=xxx 用户名模糊搜索
            - filter[email][ilike]=xxx 邮箱模糊搜索
            - filter[is_active]=true 按激活状态筛选
            - filter[is_owner]=true 按所有者状态筛选
            - filter[role_id]=1 按角色筛选
            - sort=-created_at 排序
            - page[number]=1&page[size]=20 分页
            
            权限: tenant_user:list
            """
            service = TenantAdminService(db, tenant_id=current_admin.tenant_id)
            items, total = await service.query_list(spec, scope="tenant")
            
            return success(
                data=PageResponse.create(
                    items=[TenantAdminResponse.from_model(item) for item in items],
                    total=total,
                    page=spec.page,
                    page_size=spec.size,
                ),
                message=_("common.success"),
            )
        
        @router.get("/{admin_id}", summary="获取管理员详情")
        @action_read("action.admin.detail")
        async def get_admin(
            request: Request,
            db: DbSession,
            admin_id: int,
            current_admin: ActiveTenantAdmin,
        ):
            """
            获取管理员详情
            
            权限: tenant_user:detail
            """
            service = TenantAdminService(db, tenant_id=current_admin.tenant_id)
            admin = await service.get_by_id(admin_id)
            
            if admin is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=_("tenant_admin.not_found"),
                )
            
            return success(
                data=TenantAdminResponse.from_model(admin),
                message=_("common.success"),
            )
        
        @router.post("", summary="创建管理员")
        @action_create("action.admin.create")
        async def create_admin(
            request: Request,
            db: DbSession,
            data: TenantAdminCreateRequest,
            current_admin: ActiveTenantAdmin,
        ):
            """
            创建租户管理员
            
            权限: tenant_user:create
            """
            service = TenantAdminService(db, tenant_id=current_admin.tenant_id)
            admin = await service.create_admin(
                username=data.username,
                email=data.email,
                password=data.password,
                phone=data.phone,
                nickname=data.nickname,
                is_active=data.is_active,
                is_owner=data.is_owner,
                role_id=data.role_id,
            )
            await db.commit()
            
            return success(
                data=TenantAdminResponse.from_model(admin),
                message=_("tenant_admin.created"),
            )
        
        @router.put("/{admin_id}", summary="更新管理员")
        @action_update("action.admin.update")
        async def update_admin(
            request: Request,
            db: DbSession,
            admin_id: int,
            data: TenantAdminUpdateRequest,
            current_admin: ActiveTenantAdmin,
        ):
            """
            更新租户管理员信息
            
            - 不能修改用户名
            - 密码通过专门接口修改
            
            权限: tenant_user:update
            """
            service = TenantAdminService(db, tenant_id=current_admin.tenant_id)
            
            # 移除 None 值
            update_data = {k: v for k, v in data.model_dump().items() if v is not None}
            
            admin = await service.update_admin(admin_id, update_data)
            await db.commit()
            
            return success(
                data=TenantAdminResponse.from_model(admin),
                message=_("tenant_admin.updated"),
            )
        
        @router.delete("/{admin_id}", summary="删除管理员")
        @action_delete("action.admin.delete")
        async def delete_admin(
            request: Request,
            db: DbSession,
            admin_id: int,
            current_admin: ActiveTenantAdmin,
        ):
            """
            删除租户管理员（软删除）
            
            - 不能删除自己
            - 不能删除租户所有者（除非自己也是所有者）
            
            权限: tenant_user:delete
            """
            # 不能删除自己
            if admin_id == current_admin.id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=_("tenant_admin.cannot_delete_self"),
                )
            
            service = TenantAdminService(db, tenant_id=current_admin.tenant_id)
            
            # 检查目标管理员
            target_admin = await service.get_by_id(admin_id)
            if target_admin is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=_("tenant_admin.not_found"),
                )
            
            # 非所有者不能删除所有者
            if target_admin.is_owner and not current_admin.is_owner:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=_("tenant_admin.cannot_delete_owner"),
                )
            
            await service.delete(admin_id)
            await db.commit()
            
            return success(message=_("tenant_admin.deleted"))
        
        @router.put("/{admin_id}/reset-password", summary="重置密码")
        @action_update("action.admin.reset_password")
        async def reset_password(
            request: Request,
            db: DbSession,
            admin_id: int,
            data: TenantAdminResetPasswordRequest,
            current_admin: ActiveTenantAdmin,
        ):
            """
            重置管理员密码（租户所有者操作）
            
            - 只有租户所有者可以重置其他管理员的密码
            
            权限: tenant_user:reset_password + 租户所有者
            """
            # 验证当前用户是租户所有者
            if not current_admin.is_owner:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=_("tenant_admin.owner_required"),
                )
            
            service = TenantAdminService(db, tenant_id=current_admin.tenant_id)
            await service.reset_password(admin_id, data.new_password)
            await db.commit()
            
            return success(message=_("tenant_admin.password_reset"))
        
        @router.put("/{admin_id}/status", summary="切换管理员状态")
        @action_update("action.admin.toggle_status")
        async def toggle_admin_status(
            request: Request,
            db: DbSession,
            admin_id: int,
            current_admin: ActiveTenantAdmin,
            is_active: bool = Query(..., description="是否激活"),
        ):
            """
            启用或禁用管理员
            
            - 不能禁用自己
            - 非所有者不能操作所有者
            
            权限: tenant_user:update
            """
            # 不能禁用自己
            if admin_id == current_admin.id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=_("tenant_admin.cannot_disable_self"),
                )
            
            service = TenantAdminService(db, tenant_id=current_admin.tenant_id)
            
            # 检查目标管理员
            target_admin = await service.get_by_id(admin_id)
            if target_admin is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=_("tenant_admin.not_found"),
                )
            
            # 非所有者不能操作所有者
            if target_admin.is_owner and not current_admin.is_owner:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=_("tenant_admin.cannot_modify_owner"),
                )
            
            admin = await service.toggle_status(admin_id, is_active)
            await db.commit()
            
            return success(
                data=TenantAdminResponse.from_model(admin),
                message=_("tenant_admin.status_updated"),
            )


# 导出路由器
router = TenantAdminController.get_router()

__all__ = ["router", "TenantAdminController"]
