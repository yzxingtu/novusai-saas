"""
任务绑定服务 / Task Binding Service
"""

from __future__ import annotations

from sqlalchemy import and_, delete, select

from app.core.base_service import GlobalService
from app.models.system.tenant_task_binding import TenantTaskBinding
from app.models.tenant.tenant import Tenant
from app.repositories.system.tenant_task_binding_repository import (
    TenantTaskBindingRepository,
)


class TaskBindingService(
    GlobalService[TenantTaskBinding, TenantTaskBindingRepository]
):
    """
    任务绑定服务 / Task binding service.
    """

    model = TenantTaskBinding
    repository_class = TenantTaskBindingRepository

    async def list_by_definition(self, task_definition_id: int) -> list[dict]:
        stmt = (
            select(TenantTaskBinding, Tenant.name)
            .join(Tenant, Tenant.id == TenantTaskBinding.tenant_id)
            .where(
                TenantTaskBinding.task_definition_id == task_definition_id,
                TenantTaskBinding.is_deleted.is_(False),  # noqa: E712
            )
            .order_by(Tenant.name.asc())
        )
        result = await self.db.execute(stmt)
        rows = result.all()
        return [
            {
                "id": binding.id,
                "tenant_id": binding.tenant_id,
                "tenant_name": tenant_name,
                "is_enabled": binding.is_enabled,
                "schedule_type_override": binding.schedule_type_override,
                "cron_expression_override": binding.cron_expression_override,
                "interval_seconds_override": binding.interval_seconds_override,
                "last_run_at": binding.last_run_at,
                "next_run_at": binding.next_run_at,
            }
            for binding, tenant_name in rows
        ]

    async def sync_definition_bindings(
        self,
        task_definition_id: int,
        tenant_ids: list[int],
    ) -> dict[str, int]:
        result = await self.db.execute(
            select(TenantTaskBinding).where(
                TenantTaskBinding.task_definition_id == task_definition_id,
                TenantTaskBinding.is_deleted.is_(False),  # noqa: E712
            )
        )
        existing = list(result.scalars().all())
        existing_map = {item.tenant_id: item for item in existing}

        target = set(tenant_ids)
        current = set(existing_map.keys())

        added = 0
        removed = 0
        reenabled = 0

        for tenant_id in sorted(target - current):
            await self.repo.create(
                {
                    "task_definition_id": task_definition_id,
                    "tenant_id": tenant_id,
                    "is_enabled": True,
                }
            )
            added += 1

        for tenant_id in sorted(target & current):
            binding = existing_map[tenant_id]
            if not binding.is_enabled:
                await self.repo.update(binding.id, {"is_enabled": True})
                reenabled += 1

        stale_ids = [existing_map[tenant_id].id for tenant_id in sorted(current - target)]
        if stale_ids:
            stmt = delete(TenantTaskBinding).where(
                and_(
                    TenantTaskBinding.id.in_(stale_ids),
                    TenantTaskBinding.task_definition_id == task_definition_id,
                )
            )
            delete_result = await self.db.execute(stmt)
            removed = delete_result.rowcount or 0

        return {
            "added": added,
            "removed": removed,
            "reenabled": reenabled,
        }


__all__ = ["TaskBindingService"]
