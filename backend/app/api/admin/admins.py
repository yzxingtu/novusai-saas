"""
平台管理员管理 API

提供平台管理员 CRUD 接口
"""

from fastapi import Query, Request
from pydantic import Field

from app.core.base_controller import GlobalController
from app.core.base_schema import BaseSchema, PageParams, PageResponse
from app.core.deps import DbSession, ActiveAdmin, QueryParams
from app.core.i18n import _
from app.core.response import success
from app.schemas.common.query import QuerySpec
from app.enums.rbac import PermissionScope
from app.models import Admin
from app.rbac.decorators import (
    permission_resource,
    action_read,
    action_create,
    action_update,
    action_delete,
)
from app.schemas.system import (
    AdminResponse,
    AdminCreateRequest,
    AdminUpdateRequest,
)
from app.schemas.common.select import SelectResponse
from app.services.system import AdminService


class AdminResetPasswordRequest(BaseSchema):
    """重置密码请求"""
    new_password: str = Field(..., min_length=6, max_length=50, description="新密码")


@permission_resource(
    resource="admin_user",
    name="menu.admin.admin_user",  # i18n key
    scope=PermissionScope.ADMIN,
    parent_resource="organization",  # 操作权限挂载到组织架构菜单下
)
class AdminAdminController(GlobalController):
    """
    平台管理员控制器
    
    提供管理员 CRUD、状态切换、密码重置等接口
    """
    
    prefix = "/admins"
    tags = ["平台管理员管理"]
    service_class = AdminService
    
    def _register_routes(self) -> None:
        """注册路由"""
        router = self.router
        
        @router.get("/select", summary="获取管理员下拉选项")
        @action_read("action.admin.select")
        async def select_admins(
            request: Request,
            db: DbSession,
            current_admin: ActiveAdmin,
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
            
            权限: admin_user:select
            """
            # 解析 is_active 参数
            active_filter = True  # 默认仅启用
            if is_active.lower() == "false":
                active_filter = False
            elif is_active.lower() == "true":
                active_filter = True
            
            service = AdminService(db)
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
            current_admin: ActiveAdmin,
        ):
            """
            获取所有平台管理员列表
            
            支持 JSON:API 风格筛选参数:
            - filter[username][ilike]=xxx 用户名模糊搜索
            - filter[email][ilike]=xxx 邮箱模糊搜索
            - filter[is_active]=true 按激活状态筛选
            - filter[is_super]=true 按超管状态筛选
            - filter[role_id]=1 按角色筛选
            - sort=-created_at 排序
            - page[number]=1&page[size]=20 分页
            
            权限: admin_user:list
            """
            service = AdminService(db)
            items, total = await service.query_list(spec, scope="admin")
            
            return success(
                data=PageResponse.create(
                    items=[AdminResponse.from_model(item) for item in items],
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
            current_admin: ActiveAdmin,
        ):
            """
            获取管理员详情
            
            权限: admin_user:detail
            """
            service = AdminService(db)
            admin = await service.get_by_id(admin_id)
            
            if admin is None:
                from fastapi import HTTPException, status
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=_("admin.not_found"),
                )
            
            return success(
                data=AdminResponse.from_model(admin),
                message=_("common.success"),
            )
        
        @router.post("", summary="创建管理员")
        @action_create("action.admin.create")
        async def create_admin(
            request: Request,
            db: DbSession,
            data: AdminCreateRequest,
            current_admin: ActiveAdmin,
        ):
            """
            创建平台管理员
            
            权限: admin_user:create
            """
            service = AdminService(db)
            admin = await service.create_admin(
                username=data.username,
                email=data.email,
                password=data.password,
                phone=data.phone,
                nickname=data.nickname,
                is_active=data.is_active,
                is_super=data.is_super,
                role_id=data.role_id,
            )
            await db.commit()
            
            return success(
                data=AdminResponse.from_model(admin),
                message=_("admin.created"),
            )
        
        @router.put("/{admin_id}", summary="更新管理员")
        @action_update("action.admin.update")
        async def update_admin(
            request: Request,
            db: DbSession,
            admin_id: int,
            data: AdminUpdateRequest,
            current_admin: ActiveAdmin,
        ):
            """
            更新平台管理员信息
            
            - 不能修改用户名
            - 密码通过专门接口修改
            
            权限: admin_user:update
            """
            service = AdminService(db)
            
            # 移除 None 值
            update_data = {k: v for k, v in data.model_dump().items() if v is not None}
            
            admin = await service.update_admin(admin_id, update_data)
            await db.commit()
            
            return success(
                data=AdminResponse.from_model(admin),
                message=_("admin.updated"),
            )
        
        @router.delete("/{admin_id}", summary="删除管理员")
        @action_delete("action.admin.delete")
        async def delete_admin(
            request: Request,
            db: DbSession,
            admin_id: int,
            current_admin: ActiveAdmin,
        ):
            """
            删除平台管理员（软删除）
            
            - 不能删除自己
            - 不能删除超级管理员（除非自己也是超管）
            
            权限: admin_user:delete
            """
            # 不能删除自己
            if admin_id == current_admin.id:
                from fastapi import HTTPException, status
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=_("admin.cannot_delete_self"),
                )
            
            service = AdminService(db)
            
            # 检查目标管理员
            target_admin = await service.get_by_id(admin_id)
            if target_admin is None:
                from fastapi import HTTPException, status
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=_("admin.not_found"),
                )
            
            # 非超管不能删除超管
            if target_admin.is_super and not current_admin.is_super:
                from fastapi import HTTPException, status
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=_("admin.cannot_delete_super"),
                )
            
            await service.delete(admin_id)
            await db.commit()
            
            return success(message=_("admin.deleted"))
        
        @router.put("/{admin_id}/reset-password", summary="重置密码")
        @action_update("action.admin.reset_password")
        async def reset_password(
            request: Request,
            db: DbSession,
            admin_id: int,
            data: AdminResetPasswordRequest,
            current_admin: ActiveAdmin,
        ):
            """
            重置管理员密码（超管操作）
            
            - 只有超级管理员可以重置其他管理员的密码
            
            权限: admin_user:reset_password + 超级管理员
            """
            # 验证当前用户是超级管理员
            if not current_admin.is_super:
                from fastapi import HTTPException, status
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=_("admin.super_admin_required"),
                )
            
            service = AdminService(db)
            await service.reset_password(admin_id, data.new_password)
            await db.commit()
            
            return success(message=_("admin.password_reset"))
        
        @router.put("/{admin_id}/status", summary="切换管理员状态")
        @action_update("action.admin.toggle_status")
        async def toggle_admin_status(
            request: Request,
            db: DbSession,
            admin_id: int,
            current_admin: ActiveAdmin,
            is_active: bool = Query(..., description="是否激活"),
        ):
            """
            启用或禁用管理员
            
            - 不能禁用自己
            - 非超管不能操作超管
            
            权限: admin_user:toggle_status
            """
            # 不能禁用自己
            if admin_id == current_admin.id:
                from fastapi import HTTPException, status
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=_("admin.cannot_disable_self"),
                )
            
            service = AdminService(db)
            
            # 检查目标管理员
            target_admin = await service.get_by_id(admin_id)
            if target_admin is None:
                from fastapi import HTTPException, status
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=_("admin.not_found"),
                )
            
            # 非超管不能操作超管
            if target_admin.is_super and not current_admin.is_super:
                from fastapi import HTTPException, status
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=_("admin.cannot_modify_super"),
                )
            
            admin = await service.toggle_status(admin_id, is_active)
            await db.commit()
            
            return success(
                data=AdminResponse.from_model(admin),
                message=_("admin.status_updated"),
            )


# 导出路由器
router = AdminAdminController.get_router()

__all__ = ["router", "AdminAdminController"]
