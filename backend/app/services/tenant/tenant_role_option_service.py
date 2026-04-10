"""Tenant config read models."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_schema import PageResponse
from app.models.auth.tenant_user_role import TenantUserRole
from app.schemas.system import TenantResponse, TenantStorageStats
from app.services.common import StorageQuotaService


class TenantRoleOptionService:
    """Load active tenant-user role options for tenant config pages."""

    def __init__(self, db: AsyncSession):
        self._db = db

    async def list_active_roles(
        self,
        tenant_id: int,
    ) -> list[tuple[int, str, str | None]]:
        result = await self._db.execute(
            select(TenantUserRole.id, TenantUserRole.name, TenantUserRole.code)
            .where(
                TenantUserRole.tenant_id == tenant_id,
                TenantUserRole.is_active.is_(True),
                TenantUserRole.is_deleted.is_(False),
            )
            .order_by(TenantUserRole.sort_order, TenantUserRole.id)
        )
        return [(row[0], row[1], row[2]) for row in result.all()]

    async def inject_role_options_for_user_default_role(
        self,
        tenant_id: int,
        configs: list[dict],
    ) -> None:
        """
        Append tenant active roles to the `user_default_role_id` config item.
        """
        target: dict | None = None
        for cfg in configs:
            if cfg.get("key") == "user_default_role_id":
                target = cfg
                break

        if target is None:
            return

        from app.services.tenant.tenant_user_role_display import (
            localized_tenant_user_role_name_and_description,
        )

        for role_id, role_name, role_code in await self.list_active_roles(tenant_id):
            label, _ = localized_tenant_user_role_name_and_description(
                role_code,
                role_name,
                None,
            )
            target.setdefault("options", []).append({"value": role_id, "label": label})


class TenantAdminReadModelService:
    """Compose admin tenant API response models outside controller endpoints."""

    def __init__(self, db: AsyncSession):
        self._db = db
        self._storage_quota_service = StorageQuotaService(db)

    async def build_tenant_list_page(
        self,
        items: list[object],
        total: int,
        page: int,
        page_size: int,
    ) -> PageResponse:
        tenant_ids = [item.id for item in items]
        storage_stats_map = {}
        if tenant_ids:
            storage_stats_map = (
                await self._storage_quota_service.get_tenant_storage_stats_batch(
                    tenant_ids
                )
            )

        response_items = [
            self._build_tenant_response(
                tenant=item,
                storage_stats=storage_stats_map.get(item.id),
                force_attach_stats=False,
            )
            for item in items
        ]
        return PageResponse.create(
            items=response_items,
            total=total,
            page=page,
            page_size=page_size,
        )

    async def build_tenant_detail(self, tenant: object) -> TenantResponse:
        storage_stats = await self._storage_quota_service.get_tenant_storage_stats(
            tenant.id
        )
        return self._build_tenant_response(
            tenant=tenant,
            storage_stats=storage_stats,
            force_attach_stats=True,
        )

    @staticmethod
    def _build_tenant_response(
        tenant: object,
        storage_stats: dict | None,
        *,
        force_attach_stats: bool,
    ) -> TenantResponse:
        data = TenantResponse.model_validate(tenant, from_attributes=True)
        if storage_stats is not None and (force_attach_stats or storage_stats):
            data.storage_stats = TenantStorageStats(**storage_stats)
        return data


__all__ = ["TenantRoleOptionService", "TenantAdminReadModelService"]
