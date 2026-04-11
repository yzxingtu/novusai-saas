"""Permission-scoped operation log queries."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.system.operation_log import OperationLog
from app.repositories.system.operation_log_repository import OperationLogRepository
from app.schemas.common.query import QuerySpec

if TYPE_CHECKING:
    from app.models.system.admin import Admin
    from app.models.tenant.tenant_admin import TenantAdmin


class _OperationLogPermissionFacade:
    """Permission-scoped log query helpers."""

    def __init__(self, db: AsyncSession, repo: OperationLogRepository):
        self.db = db
        self.repo = repo

    async def query_admin_logs_by_permission(
        self,
        admin: Admin,
        spec: QuerySpec,
    ) -> tuple[list[OperationLog], int]:
        if admin.is_super:
            return await self.repo.query_admin_logs_with_hierarchy(
                spec=spec,
                is_super=True,
            )

        subordinate_ids = await self.get_subordinate_admin_ids(admin)
        return await self.repo.query_admin_logs_with_hierarchy(
            spec=spec,
            is_super=False,
            subordinate_user_ids=subordinate_ids,
        )

    async def query_tenant_logs_by_permission(
        self,
        tenant_admin: TenantAdmin,
        spec: QuerySpec,
    ) -> tuple[list[OperationLog], int]:
        if tenant_admin.is_owner:
            return await self.repo.query_tenant_logs_with_hierarchy(
                tenant_id=tenant_admin.tenant_id,
                spec=spec,
                is_owner=True,
            )

        subordinate_ids = await self.get_subordinate_tenant_admin_ids(tenant_admin)
        return await self.repo.query_tenant_logs_with_hierarchy(
            tenant_id=tenant_admin.tenant_id,
            spec=spec,
            is_owner=False,
            subordinate_user_ids=subordinate_ids,
        )

    async def get_subordinate_admin_ids(self, admin: Admin) -> list[int]:
        from app.models.system.admin import Admin as AdminModel
        from app.services.system.admin_org_authority_service import (
            AdminOrgAuthorityService,
        )

        user_ids = [admin.id]
        visible_org_ids = await AdminOrgAuthorityService(
            self.db, admin
        ).get_visible_org_node_ids()
        if not visible_org_ids:
            return user_ids

        result = await self.db.execute(
            select(AdminModel.id).where(
                AdminModel.is_deleted.is_(False),
                AdminModel.org_node_id.in_(visible_org_ids),
            )
        )
        for row in result.all():
            if row[0] not in user_ids:
                user_ids.append(row[0])
        return user_ids

    async def get_subordinate_tenant_admin_ids(
        self,
        tenant_admin: TenantAdmin,
    ) -> list[int]:
        from app.models.tenant.tenant_admin import TenantAdmin as TenantAdminModel
        from app.services.tenant.tenant_org_authority_service import (
            TenantOrgAuthorityService,
        )

        user_ids = [tenant_admin.id]
        visible_org_ids = await TenantOrgAuthorityService(
            self.db, tenant_admin
        ).get_visible_org_node_ids()
        if not visible_org_ids:
            return user_ids

        result = await self.db.execute(
            select(TenantAdminModel.id).where(
                TenantAdminModel.is_deleted.is_(False),
                TenantAdminModel.tenant_id == tenant_admin.tenant_id,
                TenantAdminModel.org_node_id.in_(visible_org_ids),
            )
        )
        for row in result.all():
            if row[0] not in user_ids:
                user_ids.append(row[0])
        return user_ids


__all__ = ["_OperationLogPermissionFacade"]
