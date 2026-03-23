"""
Platform admin permission role APIs / 平台管理后台权限角色 API
"""

from __future__ import annotations

from fastapi import HTTPException, Query, Request, status

from app.core.base_controller import GlobalController
from app.core.base_schema import PageResponse
from app.core.deps import ActiveAdmin, DbSession
from app.core.i18n import _
from app.core.response import success
from app.enums.rbac import PermissionScope
from app.exceptions import BusinessException, NotFoundException
from app.rbac.decorators import (
    MenuConfig,
    action_create,
    action_delete,
    action_read,
    action_update,
    permission_resource,
)
from app.schemas.common import PermissionResponse
from app.schemas.system.admin_permission_role import (
    AdminPermissionRoleAssignPermissionsRequest,
    AdminPermissionRoleCreateRequest,
    AdminPermissionRoleDetailResponse,
    AdminPermissionRoleResponse,
    AdminPermissionRoleUpdateRequest,
)
from app.services.system.admin_permission_role_service import AdminPermissionRoleService


def _serialize_permission_role(role) -> AdminPermissionRoleResponse:
    return AdminPermissionRoleResponse(
        id=role.id,
        code=role.code,
        name=role.name,
        description=role.description,
        is_system=role.is_system,
        is_active=role.is_active,
        sort_order=role.sort_order,
        permissions_count=getattr(role, "permissions_count", len(getattr(role, "permissions", []))),
        created_at=role.created_at,
    )


def _serialize_permission_role_detail(role) -> AdminPermissionRoleDetailResponse:
    permissions = list(getattr(role, "permissions", []))
    return AdminPermissionRoleDetailResponse(
        **_serialize_permission_role(role).model_dump(),
        permission_ids=[permission.id for permission in permissions],
        permission_codes=[permission.code for permission in permissions],
    )


def _raise_http(exc: Exception):
    if isinstance(exc, NotFoundException):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc.message))
    if isinstance(exc, BusinessException):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc.message))
    raise exc


@permission_resource(
    resource="permission_role",
    name="menu.admin.permission_role",
    scope=PermissionScope.ADMIN,
    parent_resource="platform_mgmt",
    menu=MenuConfig(
        icon="lucide:key-round",
        path="/system/permission-roles",
        component="admin/system/permission-roles/index",
        parent="system",
        sort_order=16,
    ),
)
class AdminPermissionRoleController(GlobalController):
    prefix = "/permission-roles"
    tags = ["Permission Role Management (Platform)"]

    def _register_routes(self) -> None:
        router = self.router

        @router.get("", summary="获取权限角色列表")
        @action_read("action.permission_role.list")
        async def list_permission_roles(
            request: Request,
            db: DbSession,
            current_admin: ActiveAdmin,
            search: str = Query("", description=_("api.param.search")),
            page: int = Query(1, alias="page[number]", ge=1, description=_("api.param.page_number")),
            page_size: int = Query(20, alias="page[size]", ge=1, le=100, description=_("api.param.page_size")),
        ):
            roles, total = await AdminPermissionRoleService(db).get_permission_roles(
                search=search or None,
                page=page,
                page_size=page_size,
            )
            return success(
                data=PageResponse.create(
                    items=[_serialize_permission_role(role) for role in roles],
                    total=total,
                    page=page,
                    page_size=page_size,
                ),
                message=_("common.success"),
            )

        @router.get("/{role_id}", summary="获取权限角色详情")
        @action_read("action.permission_role.detail")
        async def get_permission_role(request: Request, db: DbSession, role_id: int, current_admin: ActiveAdmin):
            role = await AdminPermissionRoleService(db).get_by_id(role_id)
            if not role:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_("role.not_found"))
            return success(data=_serialize_permission_role_detail(role), message=_("common.success"))

        @router.post("", summary="创建权限角色")
        @action_create("action.permission_role.create")
        async def create_permission_role(
            request: Request,
            db: DbSession,
            data: AdminPermissionRoleCreateRequest,
            current_admin: ActiveAdmin,
        ):
            if not current_admin.is_super:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=_("common.error.permission_denied"))
            service = AdminPermissionRoleService(db)
            try:
                role = await service.create_permission_role(
                    name=data.name,
                    code=data.code,
                    description=data.description,
                    is_active=data.is_active,
                    sort_order=data.sort_order,
                )
                if data.permission_ids:
                    role = await service.assign_permissions(role.id, data.permission_ids)
                await db.commit()
                return success(data=_serialize_permission_role_detail(role), message=_("role.created"))
            except Exception as exc:
                _raise_http(exc)

        @router.put("/{role_id}", summary="更新权限角色")
        @action_update("action.permission_role.update")
        async def update_permission_role(
            request: Request,
            db: DbSession,
            role_id: int,
            data: AdminPermissionRoleUpdateRequest,
            current_admin: ActiveAdmin,
        ):
            if not current_admin.is_super:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=_("common.error.permission_denied"))
            service = AdminPermissionRoleService(db)
            try:
                role = await service.update_permission_role(
                    role_id,
                    data.model_dump(exclude_unset=True, exclude={"permission_ids"}),
                )
                if data.permission_ids is not None:
                    role = await service.assign_permissions(role_id, data.permission_ids)
                await db.commit()
                return success(data=_serialize_permission_role_detail(role), message=_("role.updated"))
            except Exception as exc:
                _raise_http(exc)

        @router.put("/{role_id}/permissions", summary="更新权限角色权限")
        @action_update("action.permission_role.assign_permissions")
        async def assign_permissions(
            request: Request,
            db: DbSession,
            role_id: int,
            data: AdminPermissionRoleAssignPermissionsRequest,
            current_admin: ActiveAdmin,
        ):
            if not current_admin.is_super:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=_("common.error.permission_denied"))
            try:
                role = await AdminPermissionRoleService(db).assign_permissions(role_id, data.permission_ids)
                await db.commit()
                return success(data=_serialize_permission_role_detail(role), message=_("role.permissions_updated"))
            except Exception as exc:
                _raise_http(exc)

        @router.get("/{role_id}/permissions/effective", summary="获取权限角色有效权限")
        @action_read("action.permission_role.effective_permissions")
        async def get_effective_permissions(request: Request, db: DbSession, role_id: int, current_admin: ActiveAdmin):
            try:
                permissions = await AdminPermissionRoleService(db).get_effective_permissions(role_id)
                return success(
                    data=[PermissionResponse.model_validate(permission, from_attributes=True) for permission in permissions],
                    message=_("common.success"),
                )
            except Exception as exc:
                _raise_http(exc)

        @router.delete("/{role_id}", summary="删除权限角色")
        @action_delete("action.permission_role.delete")
        async def delete_permission_role(request: Request, db: DbSession, role_id: int, current_admin: ActiveAdmin):
            if not current_admin.is_super:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=_("common.error.permission_denied"))
            try:
                await AdminPermissionRoleService(db).delete_permission_role(role_id)
                await db.commit()
                return success(data={"id": role_id}, message=_("role.deleted"))
            except Exception as exc:
                _raise_http(exc)


router = AdminPermissionRoleController.get_router()

__all__ = ["router", "AdminPermissionRoleController"]
