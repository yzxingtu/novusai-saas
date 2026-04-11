"""Permission list/tree query and projection helpers."""

from __future__ import annotations

from sqlalchemy import select

from app.enums.rbac import PermissionScope
from app.models import Admin, Permission, TenantAdmin
from app.schemas.common import PermissionResponse, PermissionTreeResponse


class PermissionQueryDomain:
    """Permission tree/list query and projection helpers."""

    def __init__(self, service) -> None:
        self._service = service

    async def _load_permissions_by_ids(
        self,
        permission_ids: set[int],
        *,
        perm_type: str | None = None,
    ) -> list[Permission]:
        query = select(Permission).where(
            Permission.id.in_(permission_ids),
            Permission.is_enabled.is_(True),
            Permission.is_deleted.is_(False),
        )
        if perm_type:
            query = query.where(Permission.type == perm_type)
        query = query.order_by(Permission.sort_order)
        result = await self._service.db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    def _serialize_permission(permission: Permission) -> PermissionResponse:
        return PermissionResponse(
            id=permission.id,
            code=permission.code,
            name=PermissionResponse.__fields__["name"] and permission.name
            if False
            else PermissionResponse(
                id=permission.id,
                code=permission.code,
                name="",
                description=permission.description,
                type=permission.type,
                scope=permission.scope,
                resource=permission.resource,
                action=permission.action,
                parent_id=permission.parent_id,
                sort_order=permission.sort_order,
                icon=permission.icon,
                path=permission.path,
                component=permission.component,
                hidden=permission.hidden,
            ).name,
            description=permission.description,
            type=permission.type,
            scope=permission.scope,
            resource=permission.resource,
            action=permission.action,
            parent_id=permission.parent_id,
            sort_order=permission.sort_order,
            icon=permission.icon,
            path=permission.path,
            component=permission.component,
            hidden=permission.hidden,
        )

    async def get_admin_tree(self, admin: Admin) -> list[PermissionTreeResponse]:
        if admin.is_super:
            permissions = await self._service.get_enabled_permissions_by_scope(
                PermissionScope.ADMIN.value
            )
            return self._service._build_permission_tree(permissions)

        effective_ids = await self._service.get_admin_effective_permission_ids(admin)
        if not effective_ids:
            return []

        permissions = await self._load_permissions_by_ids(effective_ids)
        permissions = await self.fill_parent_permissions(permissions)
        return self._service._build_permission_tree(permissions)

    async def get_tenant_tree(
        self,
        tenant_admin: TenantAdmin,
    ) -> list[PermissionTreeResponse]:
        effective_ids = await self._service.get_tenant_admin_effective_permission_ids(
            tenant_admin
        )
        if not effective_ids:
            return []

        permissions = await self._load_permissions_by_ids(effective_ids)
        permissions = await self.fill_parent_permissions(permissions)
        return self._service._build_permission_tree(permissions)

    async def get_admin_list(
        self,
        admin: Admin,
        perm_type: str | None = None,
    ) -> list[PermissionResponse]:
        if admin.is_super:
            permissions = await self._service.get_enabled_permissions_by_scope(
                PermissionScope.ADMIN.value
            )
            if perm_type:
                permissions = [
                    permission
                    for permission in permissions
                    if permission.type == perm_type
                ]
        else:
            effective_ids = await self._service.get_admin_effective_permission_ids(admin)
            if not effective_ids:
                return []
            permissions = await self._load_permissions_by_ids(
                effective_ids,
                perm_type=perm_type,
            )

        return [
            self._service._presentation_domain.serialize_permission(permission)
            for permission in permissions
        ]

    async def get_tenant_list(
        self,
        tenant_admin: TenantAdmin,
        perm_type: str | None = None,
    ) -> list[PermissionResponse]:
        effective_ids = await self._service.get_tenant_admin_effective_permission_ids(
            tenant_admin
        )
        if not effective_ids:
            return []

        permissions = await self._load_permissions_by_ids(
            effective_ids,
            perm_type=perm_type,
        )
        return [
            self._service._presentation_domain.serialize_permission(permission)
            for permission in permissions
        ]

    async def fill_parent_permissions(
        self,
        permissions: list[Permission],
    ) -> list[Permission]:
        perm_ids = {permission.id for permission in permissions}
        parent_ids_to_fetch = {
            permission.parent_id
            for permission in permissions
            if permission.parent_id and permission.parent_id not in perm_ids
        }

        while parent_ids_to_fetch:
            result = await self._service.db.execute(
                select(Permission).where(
                    Permission.id.in_(parent_ids_to_fetch),
                    Permission.is_enabled.is_(True),
                    Permission.is_deleted.is_(False),
                )
            )
            parents = list(result.scalars().all())
            permissions.extend(parents)
            perm_ids.update(permission.id for permission in parents)
            parent_ids_to_fetch = {
                permission.parent_id
                for permission in parents
                if permission.parent_id and permission.parent_id not in perm_ids
            }

        return permissions

    async def fill_parent_permissions_for_tree(
        self,
        permissions: list[Permission],
    ) -> list[Permission]:
        return await self.fill_parent_permissions(list(permissions))
