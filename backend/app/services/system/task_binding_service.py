"""
任务绑定服务 / Task Binding Service
"""

from __future__ import annotations

from collections import defaultdict

from sqlalchemy import and_, delete, select

from app.core.base_service import GlobalService
from app.enums.common import ResourceScopeEnum
from app.models.system.task_definition import TaskDefinition
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

    async def resolve_target_tenant_ids(
        self,
        target_scope: str,
        tenant_ids: list[int] | None,
    ) -> list[int]:
        if target_scope == ResourceScopeEnum.ALL_TENANTS.value:
            result = await self.db.execute(
                select(Tenant.id)
                .where(
                    Tenant.is_deleted.is_(False),  # noqa: E712
                    Tenant.is_active.is_(True),  # noqa: E712
                )
                .order_by(Tenant.id.asc())
            )
            return list(result.scalars().all())

        if target_scope in (
            ResourceScopeEnum.SELECTED_TENANTS.value,
            ResourceScopeEnum.ADMIN_AND_SELECTED_TENANTS.value,
        ):
            unique_ids: list[int] = []
            seen: set[int] = set()
            for tenant_id in tenant_ids or []:
                if tenant_id in seen:
                    continue
                seen.add(tenant_id)
                unique_ids.append(tenant_id)
            return unique_ids

        return []

    async def get_definition_binding_summary(
        self,
        task_definition_ids: list[int],
    ) -> dict[int, dict[str, list[int] | int | str]]:
        if not task_definition_ids:
            return {}

        result = await self.db.execute(
            select(TenantTaskBinding, Tenant.name)
            .join(Tenant, Tenant.id == TenantTaskBinding.tenant_id)
            .where(
                TenantTaskBinding.task_definition_id.in_(task_definition_ids),
                TenantTaskBinding.is_deleted.is_(False),  # noqa: E712
            )
            .order_by(TenantTaskBinding.task_definition_id.asc(), Tenant.name.asc())
        )
        rows = result.all()
        summary: dict[int, dict[str, list[int] | int | str]] = defaultdict(
            lambda: {
                "active_binding_count": 0,
                "assigned_tenant_ids": [],
                "assigned_tenant_names": [],
                "binding_count": 0,
                "binding_summary": None,
            }
        )
        for binding, tenant_name in rows:
            item = summary[binding.task_definition_id]
            tenant_ids = item["assigned_tenant_ids"]
            tenant_names = item["assigned_tenant_names"]
            if isinstance(tenant_ids, list):
                tenant_ids.append(binding.tenant_id)
            if isinstance(tenant_names, list):
                tenant_names.append(tenant_name)
            item["binding_count"] = int(item["binding_count"]) + 1
            if binding.is_enabled:
                item["active_binding_count"] = int(item["active_binding_count"]) + 1
        for item in summary.values():
            tenant_names = item["assigned_tenant_names"]
            if not isinstance(tenant_names, list) or not tenant_names:
                item["binding_summary"] = None
                continue
            preview_names = tenant_names[:3]
            remaining = len(tenant_names) - len(preview_names)
            suffix = f" +{remaining}" if remaining > 0 else ""
            item["binding_summary"] = ", ".join(preview_names) + suffix
        return dict(summary)

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
        target_scope: str | None = None,
    ) -> dict[str, int]:
        definition = await self.db.get(TaskDefinition, task_definition_id)
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

        if definition is not None:
            if target_scope:
                definition.scope = target_scope
            elif tenant_ids:
                definition.scope = ResourceScopeEnum.ADMIN_AND_SELECTED_TENANTS.value
            elif definition.scope in (
                ResourceScopeEnum.SELECTED_TENANTS.value,
                ResourceScopeEnum.ADMIN_AND_SELECTED_TENANTS.value,
            ):
                definition.scope = ResourceScopeEnum.ADMIN_ONLY.value

        return {
            "added": added,
            "removed": removed,
            "reenabled": reenabled,
        }


__all__ = ["TaskBindingService"]
