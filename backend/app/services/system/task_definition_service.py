"""
任务定义服务 / Task Definition Service
"""

from __future__ import annotations

from hashlib import md5
from typing import Any

from sqlalchemy import select

from app.celery_app import celery_app
from app.core.base_model import utc_now
from app.core.base_service import GlobalService
from app.core.i18n import _
from app.core.logging import LogManager
from app.enums.common import ResourceScopeEnum
from app.enums.plugin import PluginStatusEnum
from app.exceptions import BusinessException
from app.models.system.plugin import Plugin
from app.models.system.task_definition import TaskDefinition
from app.repositories.system.task_definition_repository import (
    TaskDefinitionRepository,
)
from app.repositories.system.tenant_task_binding_repository import (
    TenantTaskBindingRepository,
)
from app.tasks.task_scheduling import (
    TASK_DEFINITION_WRAPPER,
    TENANT_BINDING_WRAPPER,
)

logger = LogManager.get_logger("queue")

PLATFORM_EXECUTION_SCOPES = {
    ResourceScopeEnum.ADMIN_ONLY.value,
    ResourceScopeEnum.GLOBAL_SHARED.value,
    ResourceScopeEnum.ADMIN_AND_SELECTED_TENANTS.value,
}

TENANT_EXECUTION_SCOPES = {
    ResourceScopeEnum.ALL_TENANTS.value,
    ResourceScopeEnum.SELECTED_TENANTS.value,
    ResourceScopeEnum.ADMIN_AND_SELECTED_TENANTS.value,
}


class TaskDefinitionService(GlobalService[TaskDefinition, TaskDefinitionRepository]):
    """
    任务定义服务 / Task definition service.
    """

    model = TaskDefinition
    repository_class = TaskDefinitionRepository

    @staticmethod
    def build_definition_code(handler_path: str) -> str:
        leaf = handler_path.split(".")[-1][:48]
        digest = md5(handler_path.encode("utf-8")).hexdigest()[:8]
        return f"task.{leaf}.{digest}"

    @staticmethod
    def _extract_plugin_name(definition: TaskDefinition) -> str | None:
        for raw in (
            getattr(definition, "code", None),
            getattr(definition, "handler_path", None),
            getattr(definition, "name", None),
        ):
            value = str(raw or "").strip()
            if not value.startswith("plugin."):
                continue
            parts = value.split(".")
            if len(parts) >= 3:
                return parts[1]
        return None

    async def _ensure_plugin_task_available(
        self,
        definition: TaskDefinition,
    ) -> None:
        plugin_name = self._extract_plugin_name(definition)
        if not plugin_name:
            return

        result = await self.db.execute(
            select(Plugin.status).where(
                Plugin.name == plugin_name,
                Plugin.is_deleted.is_(False),
            )
        )
        plugin_status = result.scalar_one_or_none()
        if plugin_status != PluginStatusEnum.ENABLED.value:
            raise BusinessException(message=_("common.operation_failed"))

    async def toggle_active(self, definition_id: int, is_enabled: bool) -> TaskDefinition:
        definition = await self.get_by_id(definition_id)
        if is_enabled:
            await self._ensure_plugin_task_available(definition)
        updated = await self.update(definition.id, {"is_enabled": is_enabled})
        logger.info(
            "Task definition '{}' {}",
            definition.code,
            "enabled" if is_enabled else "disabled",
        )
        return updated

    async def trigger_now(self, definition_id: int) -> str:
        definition = await self.get_by_id(definition_id)
        await self._ensure_plugin_task_available(definition)
        binding_repo = TenantTaskBindingRepository(self.db)
        active_bindings = await binding_repo.get_list(
            task_definition_id=definition.id,
            is_enabled=True,
        )
        scope = getattr(definition, "scope", None)

        dispatched_task_ids: list[str] = []
        should_dispatch_bindings = (
            scope in TENANT_EXECUTION_SCOPES if scope else bool(active_bindings)
        )
        should_dispatch_platform = (
            scope in PLATFORM_EXECUTION_SCOPES if scope else not active_bindings
        )

        if should_dispatch_bindings and active_bindings:
            for binding in active_bindings:
                result = celery_app.send_task(
                    TENANT_BINDING_WRAPPER,
                    args=[binding.id],
                    queue="scheduled",
                )
                dispatched_task_ids.append(str(result.id))
        if should_dispatch_platform:
            result = celery_app.send_task(
                TASK_DEFINITION_WRAPPER,
                args=[definition.id],
                queue="scheduled",
            )
            dispatched_task_ids.append(str(result.id))
        if not dispatched_task_ids:
            if scope:
                raise BusinessException(message=_("common.operation_failed"))
            result = celery_app.send_task(
                TASK_DEFINITION_WRAPPER,
                args=[definition.id],
                queue="scheduled",
            )
            dispatched_task_ids.append(str(result.id))

        now = utc_now()
        update_data: dict = {"last_run_at": now}
        next_run = self._compute_next_run(
            definition.default_schedule_type,
            definition.default_cron_expression,
            definition.default_interval_seconds,
            now,
        )
        if next_run is not None:
            update_data["next_run_at"] = next_run
        await self.update(definition.id, update_data)
        if should_dispatch_bindings and active_bindings:
            for binding in active_bindings:
                binding_next_run = self._compute_next_run(
                    binding.schedule_type_override
                    or definition.default_schedule_type,
                    binding.cron_expression_override
                    or definition.default_cron_expression,
                    binding.interval_seconds_override
                    if binding.interval_seconds_override is not None
                    else definition.default_interval_seconds,
                    now,
                )
                binding_update: dict[str, Any] = {"last_run_at": now}
                if binding_next_run is not None:
                    binding_update["next_run_at"] = binding_next_run
                await binding_repo.update(
                    binding.id,
                    binding_update,
                )
        logger.info(
            "Task definition '{}' triggered manually -> task_ids={}",
            definition.code,
            dispatched_task_ids,
        )
        return dispatched_task_ids[0]

    async def _before_create(self, data: dict) -> dict:
        handler_path = data.get("handler_path", "")
        code = data.get("code") or self.build_definition_code(handler_path)
        existing = await self.repo.get_by_code(code)
        if existing:
            raise BusinessException(
                message=_("periodic_task.error.name_exists", name=data.get("name", code))
            )
        data["code"] = code
        return data

    async def _before_update(self, id: int, data: dict) -> None:
        instance = await self.get_by_id(id)
        if instance and not instance.is_editable:
            allowed_fields = {"is_enabled", "last_run_at", "next_run_at"}
            non_allowed = set(data.keys()) - allowed_fields
            if non_allowed:
                raise BusinessException(
                    message=_("periodic_task.error.edit_locked")
                )

    async def _before_delete(self, id: int) -> None:
        instance = await self.get_by_id(id)
        if instance and not instance.is_deletable:
            raise BusinessException(
                message=_("periodic_task.error.delete_locked", name=instance.name)
            )

    async def _after_create(self, instance: TaskDefinition) -> None:
        _ = instance
        from app.tasks.scheduler import refresh_schedule

        try:
            refresh_schedule()
        except Exception as e:
            logger.warning(f"Failed to refresh schedule after create: {e}")

    async def _after_update(self, instance: TaskDefinition) -> None:
        _ = instance
        from app.tasks.scheduler import refresh_schedule

        try:
            refresh_schedule()
        except Exception as e:
            logger.warning(f"Failed to refresh schedule after update: {e}")

    async def _after_delete(self, id: int) -> None:
        _ = id
        from app.tasks.scheduler import refresh_schedule

        try:
            refresh_schedule()
        except Exception as e:
            logger.warning(f"Failed to refresh schedule after delete: {e}")

    @staticmethod
    def _compute_next_run(
        schedule_type: str | None,
        cron_expression: str | None,
        interval_seconds: int | None,
        base_time=None,
    ):
        base = base_time or utc_now()
        if schedule_type == "cron" and cron_expression:
            try:
                from celery.schedules import crontab

                parts = cron_expression.strip().split()
                if len(parts) != 5:
                    return None
                schedule = crontab(
                    minute=parts[0],
                    hour=parts[1],
                    day_of_month=parts[2],
                    month_of_year=parts[3],
                    day_of_week=parts[4],
                )
                remaining = schedule.remaining_estimate(base)
                return base + remaining
            except Exception:
                return None
        if schedule_type == "interval" and interval_seconds:
            from datetime import timedelta

            return base + timedelta(seconds=interval_seconds)
        return None


__all__ = ["TaskDefinitionService"]
