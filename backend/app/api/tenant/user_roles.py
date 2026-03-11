"""
租户用户角色管理 API（租户端） / Tenant User Role Management API (Tenant Side)

提供租户业务用户角色的 CRUD、权限分配、状态切换等接口
Provides tenant user role CRUD, permission assignment, status toggle endpoints
"""

from __future__ import annotations

from fastapi import Query, Request

from app.core.base_controller import TenantController
from app.core.deps import ActiveTenantAdmin, DbSession, QueryParams
from app.core.i18n import _
from app.core.response import created, deleted, paginated, success, updated
from app.enums.rbac import PermissionScope
from app.exceptions import NotFoundException
from app.rbac.decorators import (
    MenuConfig,
    action_create,
    action_delete,
    action_read,
    action_update,
    permission_resource,
)
from app.schemas.tenant.user_role import (
    TenantUserRoleCreateRequest,
    TenantUserRolePermissionsRequest,
    TenantUserRoleUpdateRequest,
)
from app.services.tenant.tenant_user_role_service import TenantUserRoleService


def _serialize_role(role) -> dict:
    """序列化角色信息 / Serialize role info"""
    return {
        "id": role.id,
        "tenant_id": role.tenant_id,
        "name": role.name,
        "code": role.code,
        "description": role.description,
        "is_system": role.is_system,
        "is_active": role.is_active,
        "sort_order": role.sort_order,
        "permissions_count": role.permissions_count,
        "member_count": role.member_count,
        "created_at": role.created_at.isoformat() if role.created_at else None,
        "updated_at": role.updated_at.isoformat() if role.updated_at else None,
    }


def _serialize_role_detail(role) -> dict:
    """序列化角色详情（含权限） / Serialize role details (with permissions)"""
    data = _serialize_role(role)
    data["permission_ids"] = [p.id for p in role.permissions]
    data["permission_codes"] = [p.code for p in role.permissions]
    return data


@permission_resource(
    resource="tenant_user_role",
    name="menu.tenant.user_architecture",
    scope=PermissionScope.ALL_TENANTS,
    parent_resource="system",
    menu=MenuConfig(
        icon="lucide:network",
        path="/system/user-architecture",
        component="tenant/system/user-architecture/index",
        parent="system",
        sort_order=25,
    ),
)
class TenantUserRoleController(TenantController):
    """租户用户角色管理控制器 / Tenant User Role Management Controller"""

    prefix = "/user-roles"
    tags = ["Tenant User Role Management"]

    def _register_routes(self) -> None:
        router = self.router

        @router.get("", summary="获取用户角色列表")
        @action_read("action.tenant_user_role.list")
        async def list_roles(
            request: Request, db: DbSession,
            current_admin: ActiveTenantAdmin, query: QueryParams,
        ):
            service = TenantUserRoleService(db, current_admin.tenant_id)
            items, total = await service.query_list(spec=query)
            return paginated(
                items=[_serialize_role(item) for item in items],
                total=total, page=query.page, page_size=query.size,
            )

        @router.get("/{role_id}", summary="获取用户角色详情")
        @action_read("action.tenant_user_role.detail")
        async def get_role(
            request: Request, db: DbSession,
            current_admin: ActiveTenantAdmin, role_id: int,
        ):
            service = TenantUserRoleService(db, current_admin.tenant_id)
            role = await service.get_by_id(role_id)
            if not role:
                raise NotFoundException(message=_("tenant_user_role.not_found"))
            return success(data=_serialize_role_detail(role))

        @router.post("", summary="创建用户角色")
        @action_create("action.tenant_user_role.create")
        async def create_role(
            request: Request, db: DbSession,
            current_admin: ActiveTenantAdmin,
            data: TenantUserRoleCreateRequest,
        ):
            service = TenantUserRoleService(db, current_admin.tenant_id)
            role = await service.create_role(
                name=data.name, code=data.code,
                description=data.description, is_active=data.is_active,
                sort_order=data.sort_order, permission_ids=data.permission_ids,
            )
            return created(data=_serialize_role(role))

        @router.put("/{role_id}", summary="更新用户角色")
        @action_update("action.tenant_user_role.update")
        async def update_role(
            request: Request, db: DbSession,
            current_admin: ActiveTenantAdmin, role_id: int,
            data: TenantUserRoleUpdateRequest,
        ):
            service = TenantUserRoleService(db, current_admin.tenant_id)
            update_data = data.model_dump(exclude_unset=True)
            role = await service.update_role(role_id, update_data)
            return updated(data=_serialize_role(role))

        @router.delete("/{role_id}", summary="删除用户角色")
        @action_delete("action.tenant_user_role.delete")
        async def delete_role(
            request: Request, db: DbSession,
            current_admin: ActiveTenantAdmin, role_id: int,
        ):
            service = TenantUserRoleService(db, current_admin.tenant_id)
            await service.delete_role(role_id)
            return deleted()

        @router.put("/{role_id}/status", summary="切换角色状态")
        @action_update("action.tenant_user_role.toggle")
        async def toggle_role_status(
            request: Request, db: DbSession,
            current_admin: ActiveTenantAdmin, role_id: int,
            is_active: bool = Query(...),
        ):
            service = TenantUserRoleService(db, current_admin.tenant_id)
            role = await service.toggle_status(role_id, is_active)
            return success(data=_serialize_role(role))

        @router.put("/{role_id}/permissions", summary="分配角色权限")
        @action_update("action.tenant_user_role.assign_permissions")
        async def assign_permissions(
            request: Request, db: DbSession,
            current_admin: ActiveTenantAdmin, role_id: int,
            data: TenantUserRolePermissionsRequest,
        ):
            service = TenantUserRoleService(db, current_admin.tenant_id)
            role = await service.assign_permissions(role_id, data.permission_ids)
            return success(data=_serialize_role_detail(role))


_controller = TenantUserRoleController()
router = _controller.router
