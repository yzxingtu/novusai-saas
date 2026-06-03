"""Tenant-admin permission aggregation helpers."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models import TenantAdmin
from app.models.auth.tenant_admin_role import TenantAdminRole


class TenantAdminPermissionDomain:
    """Tenant-admin aggregation kept behind the service facade."""

    def __init__(self, service) -> None:
        self._service = service

    @staticmethod
    def _enabled_permission_codes(permissions) -> set[str]:
        return {
            permission.code
            for permission in permissions
            if permission.is_enabled and not permission.is_deleted
        }

    @staticmethod
    def _enabled_permission_ids(permissions) -> set[int]:
        return {
            permission.id
            for permission in permissions
            if permission.is_enabled and not permission.is_deleted
        }

    async def _get_role(self, role_id: int | None) -> TenantAdminRole | None:
        if role_id is None:
            return None

        result = await self._service.db.execute(
            select(TenantAdminRole)
            .where(TenantAdminRole.id == role_id)
            .options(selectinload(TenantAdminRole.permissions))
        )
        role = result.scalar_one_or_none()
        if role is None or not role.is_active:
            return None
        return role

    async def get_permissions(self, tenant_admin: TenantAdmin) -> set[str]:
        plan_perms = await self._service._get_tenant_plan_permissions(
            tenant_admin.tenant_id
        )
        if plan_perms is None:
            return set()

        if tenant_admin.is_owner:
            return plan_perms[0]

        permission_codes: set[str] = set()
        org_node = await self._service._get_tenant_org_node(tenant_admin)
        if org_node is not None:
            permission_codes.update(
                self._enabled_permission_codes(org_node.permissions)
            )

        role = await self._get_role(tenant_admin.role_id)
        if role is not None:
            permission_codes.update(self._enabled_permission_codes(role.permissions))

        return permission_codes & plan_perms[0]

    async def get_effective_permission_ids(self, tenant_admin: TenantAdmin) -> set[int]:
        plan_perms = await self._service._get_tenant_plan_permissions(
            tenant_admin.tenant_id
        )
        if plan_perms is None:
            return set()

        if tenant_admin.is_owner:
            return plan_perms[1]

        permission_ids: set[int] = set()
        org_node = await self._service._get_tenant_org_node(tenant_admin)
        if org_node is not None:
            permission_ids.update(self._enabled_permission_ids(org_node.permissions))

        role = await self._get_role(tenant_admin.role_id)
        if role is not None:
            permission_ids.update(self._enabled_permission_ids(role.permissions))

        return permission_ids & plan_perms[1]
