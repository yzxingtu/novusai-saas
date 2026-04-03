"""
Tenant admin permission role APIs / 企业管理员权限角色 API
"""

from __future__ import annotations

from fastapi import Query, Request

from app.core.base_controller import TenantController
from app.core.base_schema import PageResponse
from app.core.deps import ActiveTenantAdmin, DbSession
from app.core.i18n import _
from app.core.response import created, deleted, success, updated
from app.enums.rbac import PermissionScope
from app.exceptions import NotFoundException
from app.rbac.decorators import (
    action_create,
    action_delete,
    action_read,
    action_update,
    permission_resource,
)
from app.schemas.tenant.tenant_permission_role import (
    TenantPermissionRoleCreateRequest,
    TenantPermissionRolePermissionsRequest,
    TenantPermissionRoleUpdateRequest,
)
from app.services.tenant.tenant_permission_role_service import (
    TenantPermissionRoleService,
)


def _serialize_role(role) -> dict:
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
    data = _serialize_role(role)
    data["permission_ids"] = [permission.id for permission in role.permissions]
    data["permission_codes"] = [permission.code for permission in role.permissions]
    return data


@permission_resource(
    resource="permission_role",
    name="menu.tenant.permission_role",
    scope=PermissionScope.TENANT,
    parent_resource="system",
)
class TenantPermissionRoleController(TenantController):
    """Tenant admin permission role controller / 企业管理员权限角色控制器"""

    prefix = "/permission-roles"
    tags = ["Tenant Permission Role Management"]

    def _register_routes(self) -> None:
        router = self.router

        @router.get("", summary="获取企业管理员权限角色列表")
        @action_read("action.permission_role.list")
        async def list_roles(
            request: Request,
            db: DbSession,
            current_admin: ActiveTenantAdmin,
            search: str = Query("", description=_("api.param.search")),
            page: int = Query(
                1, alias="page[number]", ge=1, description=_("api.param.page_number")
            ),
            page_size: int = Query(
                20,
                alias="page[size]",
                ge=1,
                le=100,
                description=_("api.param.page_size"),
            ),
        ):
            service = TenantPermissionRoleService(db, current_admin.tenant_id)
            roles, total = await service.get_permission_roles(
                search=search or None,
                page=page,
                page_size=page_size,
            )
            return success(
                data=PageResponse.create(
                    items=[_serialize_role(role) for role in roles],
                    total=total,
                    page=page,
                    page_size=page_size,
                ),
                message=_("common.success"),
            )

        @router.get("/{role_id}", summary="获取企业管理员权限角色详情")
        @action_read("action.permission_role.detail")
        async def get_role(
            request: Request,
            db: DbSession,
            current_admin: ActiveTenantAdmin,
            role_id: int,
        ):
            service = TenantPermissionRoleService(db, current_admin.tenant_id)
            role = await service.get_by_id(role_id)
            if not role:
                raise NotFoundException(message=_("role.not_found"))
            return success(data=_serialize_role_detail(role))

        @router.post("", summary="创建企业管理员权限角色")
        @action_create("action.permission_role.create")
        async def create_role(
            request: Request,
            db: DbSession,
            current_admin: ActiveTenantAdmin,
            data: TenantPermissionRoleCreateRequest,
        ):
            service = TenantPermissionRoleService(db, current_admin.tenant_id)
            role = await service.create_permission_role(
                name=data.name,
                code=data.code,
                description=data.description,
                is_active=data.is_active,
                sort_order=data.sort_order,
                permission_ids=data.permission_ids,
            )
            return created(data=_serialize_role_detail(role))

        @router.put("/{role_id}", summary="更新企业管理员权限角色")
        @action_update("action.permission_role.update")
        async def update_role(
            request: Request,
            db: DbSession,
            current_admin: ActiveTenantAdmin,
            role_id: int,
            data: TenantPermissionRoleUpdateRequest,
        ):
            service = TenantPermissionRoleService(db, current_admin.tenant_id)
            role = await service.update_permission_role(
                role_id,
                data.model_dump(exclude_unset=True),
            )
            return updated(data=_serialize_role_detail(role))

        @router.put("/{role_id}/permissions", summary="分配企业管理员权限角色权限")
        @action_update("action.permission_role.assign_permissions")
        async def assign_permissions(
            request: Request,
            db: DbSession,
            current_admin: ActiveTenantAdmin,
            role_id: int,
            data: TenantPermissionRolePermissionsRequest,
        ):
            service = TenantPermissionRoleService(db, current_admin.tenant_id)
            role = await service.assign_permissions(role_id, data.permission_ids)
            return success(data=_serialize_role_detail(role))

        @router.delete("/{role_id}", summary="删除企业管理员权限角色")
        @action_delete("action.permission_role.delete")
        async def delete_role(
            request: Request,
            db: DbSession,
            current_admin: ActiveTenantAdmin,
            role_id: int,
        ):
            service = TenantPermissionRoleService(db, current_admin.tenant_id)
            await service.delete_permission_role(role_id)
            return deleted()


_controller = TenantPermissionRoleController()
router = _controller.router

__all__ = ["TenantPermissionRoleController", "router"]
