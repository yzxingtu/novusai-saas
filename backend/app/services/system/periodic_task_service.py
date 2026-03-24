"""
定时任务服务 / Periodic Task Service

提供定时任务的 CRUD 和管理业务逻辑
Provides periodic task CRUD and management business logic.
"""

from datetime import datetime, timedelta

from app.celery_app import celery_app
from app.core.base_model import utc_now
from app.core.base_service import GlobalService
from app.core.i18n import _
from app.core.logging import LogManager
from app.exceptions import BusinessException
from app.models.system.periodic_task import PeriodicTask
from app.repositories.system.periodic_task_repository import PeriodicTaskRepository

logger = LogManager.get_logger("queue")


class PeriodicTaskService(GlobalService[PeriodicTask, PeriodicTaskRepository]):
    """
    定时任务服务 / Periodic task service.
    """

    model = PeriodicTask
    repository_class = PeriodicTaskRepository

    async def toggle_active(self, task_id: int, is_active: bool) -> PeriodicTask:
        task = await self.get_by_id(task_id)
        updated = await self.update(task.id, {"is_active": is_active})
        logger.info(
            f"Periodic task '{task.name}' {'enabled' if is_active else 'disabled'}"
        )
        return updated

    async def trigger_now(self, task_id: int) -> str:
        task = await self.get_by_id(task_id)
        # 使用任务注册时定义的队列（从 task registry 查询），回退到 scheduled
        from app.tasks.base import get_task_registry
        registry = get_task_registry()
        task_info = registry.get(task.task_path, {})
        queue = task_info.get("queue", "scheduled")

        result = celery_app.send_task(
            task.task_path,
            args=list(task.args.values()) if task.args else [],
            kwargs=task.kwargs or {},
            queue=queue,
        )
        now = utc_now()
        update_data: dict = {"last_run_at": now}
        next_run = self._compute_next_run(task, now)
        if next_run:
            update_data["next_run_at"] = next_run
        await self.update(task.id, update_data)
        logger.info(
            f"Periodic task '{task.name}' triggered manually -> task_id={result.id}"
        )
        return result.id

    @staticmethod
    def _compute_next_run(
        task: PeriodicTask, base_time: datetime | None = None,
    ) -> datetime | None:
        """根据调度配置计算下次执行时间 / Compute next run from schedule config."""
        base = base_time or utc_now()
        if task.schedule_type == "cron" and task.cron_expression:
            try:
                from celery.schedules import crontab
                parts = task.cron_expression.strip().split()
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
                return base + remaining  # 剩余为 timedelta 类型 / remaining is timedelta
            except Exception:
                return None
        elif task.schedule_type == "interval" and task.interval_seconds:
            return base + timedelta(seconds=task.interval_seconds)
        return None

    async def _before_create(self, data: dict) -> dict:
        existing = await self.repo.get_by_name(data.get("name", ""))
        if existing:
            raise BusinessException(
                message=_("periodic_task.error.name_exists", name=data['name'])
            )
        from app.enums.common import ResourceScopeEnum

        if "tenant_id" in data:
            raise BusinessException(
                message=_("periodic_task.error.reject_tenant_id_field"),
            )

        scope_val = data.get("scope") or ResourceScopeEnum.ADMIN_ONLY.value
        if scope_val in (
            ResourceScopeEnum.ADMIN_ONLY.value,
            ResourceScopeEnum.GLOBAL_SHARED.value,
            ResourceScopeEnum.ALL_TENANTS.value,
        ):
            data["owner_tenant_id"] = None
        elif scope_val in (
            ResourceScopeEnum.SELECTED_TENANTS.value,
            ResourceScopeEnum.ADMIN_AND_SELECTED_TENANTS.value,
        ):
            if data.get("owner_tenant_id") is None:
                raise BusinessException(
                    message=_("periodic_task.error.scope_requires_tenant_id")
                )
        return data

    async def _before_update(self, id: int, data: dict) -> None:
        if "tenant_id" in data:
            raise BusinessException(
                message=_("periodic_task.error.reject_tenant_id_field"),
            )
        instance = await self.get_by_id(id)
        if instance and not instance.is_editable:
            allowed_fields = {"is_active", "last_run_at", "next_run_at"}
            non_allowed = set(data.keys()) - allowed_fields
            if non_allowed:
                raise BusinessException(
                    message=_("periodic_task.error.edit_locked")
                )

    async def _before_delete(self, id: int) -> None:
        instance = await self.get_by_id(id)
        if instance and instance.is_locked:
            raise BusinessException(
                message=_("periodic_task.error.delete_locked", name=instance.name)
            )

    async def _after_create(self, instance: PeriodicTask) -> None:
        next_run = self._compute_next_run(instance)
        if next_run:
            await self.repo.update(instance.id, {"next_run_at": next_run})
        from app.tasks.scheduler import refresh_schedule
        try:
            refresh_schedule()
        except Exception as e:
            logger.warning(f"Failed to refresh schedule after create: {e}")

    async def _after_update(self, instance: PeriodicTask) -> None:
        _ = instance
        from app.tasks.scheduler import refresh_schedule
        try:
            refresh_schedule()
        except Exception as e:
            logger.warning(f"Failed to refresh schedule after update: {e}")
