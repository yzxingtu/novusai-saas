"""
任务绑定服务 / Task Binding Service
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from sqlalchemy import and_, delete, select

from app.core.base_service import GlobalService
from app.core.i18n import _
from app.enums.common import ResourceScopeEnum
from app.exceptions import BusinessException
from app.models.system.task_definition import TaskDefinition
from app.models.system.tenant_task_binding import TenantTaskBinding
from app.models.tenant.tenant import Tenant
from app.models.tenant.tenant_plan import TenantPlan
from app.repositories.system.tenant_task_binding_repository import (
    TenantTaskBindingRepository,
)
from app.services.system.task_tenant_eligibility_service import (
    TaskTenantEligibilityService,
)
from app.tasks.task_scheduling import handler_supports_tenant_dispatch


class TaskBindingService(GlobalService[TenantTaskBinding, TenantTaskBindingRepository]):
    """
    任务绑定服务 / Task binding service.
    """

    model = TenantTaskBinding
    repository_class = TenantTaskBindingRepository

    EXPLICIT_BINDING_SCOPES = {
        ResourceScopeEnum.SELECTED_TENANTS.value,
        ResourceScopeEnum.ADMIN_AND_SELECTED_TENANTS.value,
    }
    TENANT_DISPATCH_SCOPES = EXPLICIT_BINDING_SCOPES | {
        ResourceScopeEnum.ALL_TENANTS.value
    }
    OVERRIDE_FIELDS = {
        "schedule_type_override",
        "cron_expression_override",
        "interval_seconds_override",
        "config_override",
        "args_override",
        "kwargs_override",
    }

    @classmethod
    def validate_tenant_dispatch_scope(
        cls,
        *,
        handler_path: str | None,
        scope: str | None,
    ) -> None:
        if scope not in cls.TENANT_DISPATCH_SCOPES:
            return
        if handler_path and handler_supports_tenant_dispatch(handler_path):
            return
        raise BusinessException(
            message=_(
                "periodic_task.error.tenant_dispatch_requires_tenant_handler",
                handler=handler_path or _("common.unknown"),
            )
        )

    @classmethod
    def _scope_accepts_binding_targets(cls, target_scope: str | None) -> bool:
        return target_scope in cls.EXPLICIT_BINDING_SCOPES or (
            target_scope == ResourceScopeEnum.ALL_TENANTS.value
        )

    async def resolve_target_tenant_ids(
        self,
        target_scope: str,
        tenant_ids: list[int] | None,
    ) -> list[int]:
        if self._scope_accepts_binding_targets(target_scope):
            unique_ids: list[int] = []
            seen: set[int] = set()
            for tenant_id in tenant_ids or []:
                if tenant_id in seen:
                    continue
                seen.add(tenant_id)
                unique_ids.append(tenant_id)
            return unique_ids

        return []

    async def get_active_bindings_for_dispatch(
        self,
        task_definition_id: int,
    ) -> list[TenantTaskBinding]:
        result = await self.db.execute(
            select(TenantTaskBinding)
            .join(Tenant, Tenant.id == TenantTaskBinding.tenant_id)
            .join(
                TenantPlan,
                TaskTenantEligibilityService.eligible_tenant_join_condition(),
            )
            .where(
                TenantTaskBinding.task_definition_id == task_definition_id,
                TenantTaskBinding.is_deleted.is_(False),  # noqa: E712
                TenantTaskBinding.is_enabled.is_(True),  # noqa: E712
                *TaskTenantEligibilityService.eligible_tenant_filters(),
            )
            .order_by(TenantTaskBinding.tenant_id.asc())
        )
        return list(result.scalars().all())

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
                TenantTaskBinding.is_enabled.is_(True),  # noqa: E712
                Tenant.is_deleted.is_(False),  # noqa: E712
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

    @classmethod
    def serialize_binding(
        cls,
        binding: TenantTaskBinding,
        *,
        definition: TaskDefinition | None = None,
        tenant_name: str | None = None,
    ) -> dict:
        schedule_type = binding.schedule_type_override
        cron_expression = binding.cron_expression_override
        interval_seconds = binding.interval_seconds_override
        if definition is not None:
            schedule_type = schedule_type or definition.default_schedule_type
            cron_expression = cron_expression or definition.default_cron_expression
            if interval_seconds is None:
                interval_seconds = definition.default_interval_seconds
        return {
            "id": binding.id,
            "tenant_id": binding.tenant_id,
            "tenant_name": tenant_name,
            "is_enabled": binding.is_enabled,
            "disabled_reason": binding.disabled_reason,
            "schedule_type_override": binding.schedule_type_override,
            "cron_expression_override": binding.cron_expression_override,
            "interval_seconds_override": binding.interval_seconds_override,
            "config_override": binding.config_override,
            "args_override": binding.args_override,
            "kwargs_override": binding.kwargs_override,
            "effective_schedule_type": schedule_type,
            "effective_cron_expression": cron_expression,
            "effective_interval_seconds": interval_seconds,
            "last_run_at": binding.last_run_at,
            "next_run_at": binding.next_run_at,
        }

    async def list_by_definition(self, task_definition_id: int) -> list[dict]:
        definition = await self.db.get(TaskDefinition, task_definition_id)
        stmt = (
            select(TenantTaskBinding, Tenant.name)
            .join(Tenant, Tenant.id == TenantTaskBinding.tenant_id)
            .where(
                TenantTaskBinding.task_definition_id == task_definition_id,
                TenantTaskBinding.is_deleted.is_(False),  # noqa: E712
                Tenant.is_deleted.is_(False),  # noqa: E712
            )
            .order_by(Tenant.name.asc())
        )
        result = await self.db.execute(stmt)
        rows = result.all()
        return [
            self.serialize_binding(
                binding,
                definition=definition,
                tenant_name=tenant_name,
            )
            for binding, tenant_name in rows
        ]

    async def _require_eligible_tenant(self, tenant_id: int) -> None:
        eligibility = await TaskTenantEligibilityService(
            self.db
        ).resolve_tenant_eligibility(tenant_id)
        if eligibility.is_eligible:
            return
        raise BusinessException(
            message=_(
                "periodic_task.error.tenant_not_eligible",
                reason=eligibility.reason or _("common.unknown"),
            )
        )

    def _normalize_binding_payload_for_scope(
        self,
        *,
        definition: TaskDefinition,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        payload = dict(data)
        payload.pop("tenant_id", None)
        if definition.scope != ResourceScopeEnum.ALL_TENANTS.value:
            return payload

        has_override = any(
            payload.get(field) not in (None, {}, [])
            for field in self.OVERRIDE_FIELDS
        )
        if payload.get("is_enabled") is not False or has_override:
            raise BusinessException(
                message=_("periodic_task.error.all_tenants_binding_deny_only")
            )
        return {
            "is_enabled": False,
            "disabled_reason": payload.get("disabled_reason"),
        }

    async def upsert_tenant_binding(
        self,
        task_definition_id: int,
        tenant_id: int,
        data: dict[str, Any],
    ) -> TenantTaskBinding:
        definition = await self.db.get(TaskDefinition, task_definition_id)
        if definition is None or bool(getattr(definition, "is_deleted", False)):
            raise BusinessException(message=_("periodic_task.error.not_found"))
        if definition.scope not in self.TENANT_DISPATCH_SCOPES:
            raise BusinessException(
                message=_(
                    "periodic_task.error.tenant_dispatch_scope_required",
                    scope=definition.scope or _("common.unknown"),
                )
            )
        self.validate_tenant_dispatch_scope(
            handler_path=getattr(definition, "handler_path", None),
            scope=getattr(definition, "scope", None),
        )
        await self._require_eligible_tenant(tenant_id)
        payload = self._normalize_binding_payload_for_scope(
            definition=definition,
            data=data,
        )
        result = await self.db.execute(
            select(TenantTaskBinding).where(
                TenantTaskBinding.task_definition_id == task_definition_id,
                TenantTaskBinding.tenant_id == tenant_id,
                TenantTaskBinding.is_deleted.is_(False),  # noqa: E712
            )
        )
        binding = result.scalars().first()
        if binding is None:
            payload.setdefault("is_enabled", True)
            return await self.repo.create(
                {
                    **payload,
                    "task_definition_id": task_definition_id,
                    "tenant_id": tenant_id,
                }
            )
        return await self.repo.update(binding.id, payload)

    async def sync_definition_bindings(
        self,
        task_definition_id: int,
        tenant_ids: list[int],
        target_scope: str | None = None,
        binding_payloads: list[dict[str, Any]] | None = None,
        replace_all_tenant_bindings: bool = False,
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

        effective_scope = target_scope
        if effective_scope is None:
            if tenant_ids:
                effective_scope = ResourceScopeEnum.ADMIN_AND_SELECTED_TENANTS.value
            elif definition is not None:
                effective_scope = definition.scope
        self.validate_tenant_dispatch_scope(
            handler_path=getattr(definition, "handler_path", None)
            if definition
            else None,
            scope=effective_scope,
        )

        payloads_by_tenant: dict[int, dict[str, Any]] = {}
        for item in binding_payloads or []:
            raw_tenant_id = item.get("tenant_id")
            if raw_tenant_id is None:
                continue
            payloads_by_tenant[int(raw_tenant_id)] = item

        requested_target = set(
            tenant_ids if self._scope_accepts_binding_targets(effective_scope) else []
        )
        if effective_scope in self.EXPLICIT_BINDING_SCOPES:
            invalid_payload_tenants = set(payloads_by_tenant) - requested_target
            if invalid_payload_tenants:
                raise BusinessException(
                    message=_("periodic_task.error.binding_tenant_not_selected")
                )
            target = requested_target
        else:
            target = requested_target | set(payloads_by_tenant)
        current = set(existing_map.keys())
        is_all_tenants = effective_scope == ResourceScopeEnum.ALL_TENANTS.value

        added = 0
        removed = 0
        reenabled = 0
        updated = 0

        if definition is not None and target_scope:
            definition.scope = target_scope

        for tenant_id in sorted(target - current):
            await self._require_eligible_tenant(tenant_id)
            payload = dict(payloads_by_tenant.get(tenant_id, {}))
            payload.pop("tenant_id", None)
            payload.setdefault("is_enabled", not is_all_tenants)
            if definition is not None:
                payload = self._normalize_binding_payload_for_scope(
                    definition=definition,
                    data=payload,
                )
            await self.repo.create(
                {
                    **payload,
                    "task_definition_id": task_definition_id,
                    "tenant_id": tenant_id,
                }
            )
            added += 1

        for tenant_id in sorted(target & current):
            await self._require_eligible_tenant(tenant_id)
            binding = existing_map[tenant_id]
            payload = dict(payloads_by_tenant.get(tenant_id, {}))
            payload.pop("tenant_id", None)
            payload.setdefault("is_enabled", not is_all_tenants)
            if definition is not None:
                payload = self._normalize_binding_payload_for_scope(
                    definition=definition,
                    data=payload,
                )
            if not binding.is_enabled and payload.get("is_enabled") is True:
                reenabled += 1
            await self.repo.update(binding.id, payload)
            updated += 1

        if is_all_tenants:
            if replace_all_tenant_bindings:
                stale_ids = [
                    existing_map[tenant_id].id
                    for tenant_id in sorted(current - target)
                ]
            else:
                stale_ids = [
                    binding.id
                    for binding in existing
                    if bool(binding.is_enabled) and binding.tenant_id not in target
                ]
        elif effective_scope in self.EXPLICIT_BINDING_SCOPES:
            stale_ids = [
                existing_map[tenant_id].id for tenant_id in sorted(current - target)
            ]
        else:
            stale_ids = [binding.id for binding in existing]
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
            elif target:
                definition.scope = ResourceScopeEnum.ADMIN_AND_SELECTED_TENANTS.value
            elif definition.scope in self.EXPLICIT_BINDING_SCOPES:
                definition.scope = ResourceScopeEnum.ADMIN_ONLY.value

        return {
            "added": added,
            "removed": removed,
            "reenabled": reenabled,
            "updated": updated,
        }


__all__ = ["TaskBindingService"]
