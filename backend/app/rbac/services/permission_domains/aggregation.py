"""Permission aggregation and org authority domain helpers."""

import inspect

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.enums.rbac import PermissionScope
from app.models import Admin, Permission, Tenant, TenantAdmin, TenantUser
from app.models.auth.admin_role import AdminRole
from app.models.auth.tenant_admin_role import TenantAdminRole
from app.models.auth.tenant_user_role import TenantUserRole
from app.models.org.admin_org_node import AdminOrgNode
from app.models.org.tenant_org_node import TenantOrgNode
from app.models.tenant.tenant_plan import TenantPlan
from app.services.system.admin_org_authority_service import AdminOrgAuthorityService
from app.services.tenant.tenant_org_authority_service import TenantOrgAuthorityService


def _enabled_permission_codes(permissions) -> set[str]:
    return {
        permission.code
        for permission in permissions
        if permission.is_enabled and not permission.is_deleted
    }


def _enabled_permission_ids(permissions) -> set[int]:
    return {
        permission.id
        for permission in permissions
        if permission.is_enabled and not permission.is_deleted
    }


class _TenantPlanPermissionResolver:
    """Resolve tenant-plan permissions and expanded child operations."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    @staticmethod
    async def _maybe_await(value):
        if inspect.isawaitable(value):
            return await value
        return value

    async def _scalar_one_or_none(self, result):
        return await self._maybe_await(result.scalar_one_or_none())

    async def _scalars_all(self, result):
        return await self._maybe_await(result.scalars().all())

    async def resolve(self, tenant_id: int) -> tuple[set[str], set[int]] | None:
        result = await self._db.execute(
            select(Tenant)
            .where(Tenant.id == tenant_id)
            .options(
                selectinload(Tenant.tenant_plan).selectinload(TenantPlan.permissions)
            )
        )
        tenant = await self._scalar_one_or_none(result)
        if tenant is None or tenant.plan_id is None:
            return None

        plan = tenant.tenant_plan
        if plan is None or not plan.is_active:
            return None

        plan_codes: set[str] = set()
        plan_ids: set[int] = set()
        menu_ids: set[int] = set()

        for permission in plan.permissions:
            if permission.is_enabled and not permission.is_deleted:
                plan_codes.add(permission.code)
                plan_ids.add(permission.id)
                if permission.type == "menu":
                    menu_ids.add(permission.id)

        if menu_ids:
            child_result = await self._db.execute(
                select(Permission).where(
                    Permission.parent_id.in_(menu_ids),
                    Permission.type == "operation",
                    Permission.is_enabled.is_(True),
                    Permission.is_deleted.is_(False),
                )
            )
            for child in await self._scalars_all(child_result):
                plan_codes.add(child.code)
                plan_ids.add(child.id)

        return plan_codes, plan_ids


class PermissionAggregationDomain:
    """Permission aggregation domain split by stable identity concerns."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._tenant_plan_permission_resolver = _TenantPlanPermissionResolver(db)

    async def get_admin_org_node(self, admin: Admin) -> AdminOrgNode | None:
        if admin.org_node_id is None:
            return None

        result = await self._db.execute(
            select(AdminOrgNode)
            .where(AdminOrgNode.id == admin.org_node_id)
            .options(selectinload(AdminOrgNode.permissions))
        )
        org_node = result.scalar_one_or_none()
        if org_node is None or org_node.is_deleted or not org_node.is_active:
            return None
        return org_node

    async def get_tenant_org_node(
        self,
        tenant_admin: TenantAdmin,
    ) -> TenantOrgNode | None:
        if tenant_admin.org_node_id is None:
            return None

        result = await self._db.execute(
            select(TenantOrgNode)
            .where(TenantOrgNode.id == tenant_admin.org_node_id)
            .options(selectinload(TenantOrgNode.permissions))
        )
        org_node = result.scalar_one_or_none()
        if org_node is None or org_node.is_deleted or not org_node.is_active:
            return None
        return org_node

    async def get_tenant_admin_role(
        self,
        tenant_admin: TenantAdmin,
    ) -> TenantAdminRole | None:
        if tenant_admin.role_id is None:
            return None

        result = await self._db.execute(
            select(TenantAdminRole)
            .where(TenantAdminRole.id == tenant_admin.role_id)
            .options(selectinload(TenantAdminRole.permissions))
        )
        role = result.scalar_one_or_none()
        if role is None or not role.is_active:
            return None
        return role

    async def get_admin_permissions(self, admin: Admin) -> set[str]:
        if admin.is_super:
            return {"*"}

        org_node = await self.get_admin_org_node(admin)
        if org_node is not None:
            return {
                permission.code
                for permission in org_node.permissions
                if permission.is_enabled and not permission.is_deleted
            }

        if admin.role_id is None:
            return set()

        result = await self._db.execute(
            select(AdminRole)
            .where(AdminRole.id == admin.role_id)
            .options(selectinload(AdminRole.permissions))
        )
        role = result.scalar_one_or_none()

        if role is None or not role.is_active:
            return set()

        return {
            permission.code
            for permission in role.permissions
            if permission.is_enabled and not permission.is_deleted
        }

    async def get_admin_effective_permission_ids(self, admin: Admin) -> set[int]:
        if admin.is_super:
            result = await self._db.execute(
                select(Permission.id).where(
                    Permission.is_enabled.is_(True),
                    Permission.is_deleted.is_(False),
                    Permission.scope.in_(
                        [PermissionScope.ADMIN.value, PermissionScope.BOTH.value]
                    ),
                )
            )
            return set(result.scalars().all())

        org_node = await self.get_admin_org_node(admin)
        if org_node is not None:
            return {
                permission.id
                for permission in org_node.permissions
                if permission.is_enabled and not permission.is_deleted
            }

        if admin.role_id is None:
            return set()

        permission_ids: set[int] = set()
        result = await self._db.execute(
            select(AdminRole)
            .where(AdminRole.id == admin.role_id)
            .options(selectinload(AdminRole.permissions))
        )
        role = result.scalar_one_or_none()
        if role and role.is_active:
            for permission in role.permissions:
                if permission.is_enabled and not permission.is_deleted:
                    permission_ids.add(permission.id)
        return permission_ids

    async def get_admin_manageable_role_ids(self, admin: Admin) -> set[int]:
        return set(
            await AdminOrgAuthorityService(
                self._db, admin
            ).get_manageable_org_node_ids()
        )

    async def get_admin_visible_role_ids(self, admin: Admin) -> set[int]:
        return set(
            await AdminOrgAuthorityService(self._db, admin).get_visible_org_node_ids()
        )

    async def get_tenant_plan_permissions(
        self,
        tenant_id: int,
    ) -> tuple[set[str], set[int]] | None:
        return await self._tenant_plan_permission_resolver.resolve(tenant_id)

    async def get_tenant_admin_permissions(self, tenant_admin: TenantAdmin) -> set[str]:
        plan_perms = await self.get_tenant_plan_permissions(tenant_admin.tenant_id)
        if plan_perms is None:
            return set()

        if tenant_admin.is_owner:
            return plan_perms[0]

        permission_codes: set[str] = set()
        org_node = await self.get_tenant_org_node(tenant_admin)
        if org_node is not None:
            permission_codes.update(_enabled_permission_codes(org_node.permissions))

        role = await self.get_tenant_admin_role(tenant_admin)
        if role is not None:
            permission_codes.update(_enabled_permission_codes(role.permissions))

        return permission_codes & plan_perms[0]

    async def get_tenant_admin_effective_permission_ids(
        self,
        tenant_admin: TenantAdmin,
    ) -> set[int]:
        plan_perms = await self.get_tenant_plan_permissions(tenant_admin.tenant_id)
        if plan_perms is None:
            return set()

        if tenant_admin.is_owner:
            return plan_perms[1]

        permission_ids: set[int] = set()
        org_node = await self.get_tenant_org_node(tenant_admin)
        if org_node is not None:
            permission_ids.update(_enabled_permission_ids(org_node.permissions))

        role = await self.get_tenant_admin_role(tenant_admin)
        if role is not None:
            permission_ids.update(_enabled_permission_ids(role.permissions))

        return permission_ids & plan_perms[1]

    async def get_tenant_admin_manageable_role_ids(
        self,
        tenant_admin: TenantAdmin,
    ) -> set[int]:
        return set(
            await TenantOrgAuthorityService(
                self._db, tenant_admin
            ).get_manageable_org_node_ids()
        )

    async def get_tenant_admin_visible_role_ids(
        self,
        tenant_admin: TenantAdmin,
    ) -> set[int]:
        return set(
            await TenantOrgAuthorityService(
                self._db, tenant_admin
            ).get_visible_org_node_ids()
        )

    async def get_tenant_user_permissions(self, tenant_user: TenantUser) -> set[str]:
        if tenant_user.role_id is None:
            return set()

        result = await self._db.execute(
            select(TenantUserRole)
            .where(TenantUserRole.id == tenant_user.role_id)
            .options(selectinload(TenantUserRole.permissions))
        )
        role = result.scalar_one_or_none()

        if role is None or not role.is_active:
            return set()

        return {
            permission.code
            for permission in role.permissions
            if permission.is_enabled and not permission.is_deleted
        }

    async def get_tenant_user_effective_permission_ids(
        self,
        tenant_user: TenantUser,
    ) -> set[int]:
        if tenant_user.role_id is None:
            return set()

        result = await self._db.execute(
            select(TenantUserRole)
            .where(TenantUserRole.id == tenant_user.role_id)
            .options(selectinload(TenantUserRole.permissions))
        )
        role = result.scalar_one_or_none()

        if role is None or not role.is_active:
            return set()

        return {
            permission.id
            for permission in role.permissions
            if permission.is_enabled and not permission.is_deleted
        }

    async def get_enabled_permissions_by_scope(self, scope: str) -> list[Permission]:
        if scope == PermissionScope.USER.value:
            scopes = [PermissionScope.USER.value]
        elif scope == PermissionScope.ADMIN.value:
            scopes = [PermissionScope.ADMIN.value, PermissionScope.BOTH.value]
        elif scope == PermissionScope.TENANT.value:
            scopes = [PermissionScope.TENANT.value, PermissionScope.BOTH.value]
        else:
            scopes = [scope]

        result = await self._db.execute(
            select(Permission)
            .where(
                Permission.is_enabled.is_(True),
                Permission.is_deleted.is_(False),
                Permission.scope.in_(scopes),
            )
            .order_by(Permission.sort_order)
        )
        return list(result.scalars().all())
