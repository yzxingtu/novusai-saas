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

        org_node = await self._service._get_tenant_org_node(tenant_admin)
        if org_node is not None:
            org_node_perms = {
                permission.code
                for permission in org_node.permissions
                if permission.is_enabled and not permission.is_deleted
            }
            return org_node_perms & plan_perms[0]

        role = await self._get_role(tenant_admin.role_id)
        if role is None:
            return set()

        role_perms = {
            permission.code
            for permission in role.permissions
            if permission.is_enabled and not permission.is_deleted
        }
        return role_perms & plan_perms[0]

    async def get_effective_permission_ids(self, tenant_admin: TenantAdmin) -> set[int]:
        plan_perms = await self._service._get_tenant_plan_permissions(
            tenant_admin.tenant_id
        )
        if plan_perms is None:
            return set()

        if tenant_admin.is_owner:
            return plan_perms[1]

        org_node = await self._service._get_tenant_org_node(tenant_admin)
        if org_node is not None:
            org_node_permission_ids = {
                permission.id
                for permission in org_node.permissions
                if permission.is_enabled and not permission.is_deleted
            }
            return org_node_permission_ids & plan_perms[1]

        role = await self._get_role(tenant_admin.role_id)
        if role is None:
            return set()

        permission_ids = {
            permission.id
            for permission in role.permissions
            if permission.is_enabled and not permission.is_deleted
        }
        return permission_ids & plan_perms[1]
