"""
定时任务服务

提供定时任务的 CRUD 和管理业务逻辑
"""

from datetime import datetime

from app.celery_app import celery_app
from app.core.base_service import GlobalService
from app.exceptions import BusinessException
from app.core.logging import LogManager
from app.models.system.periodic_task import PeriodicTask
from app.repositories.system.periodic_task_repository import PeriodicTaskRepository

logger = LogManager.get_logger("queue")


class PeriodicTaskService(GlobalService[PeriodicTask, PeriodicTaskRepository]):
    """
    定时任务服务
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
        result = celery_app.send_task(
            task.task_path,
            args=list(task.args.values()) if task.args else [],
            kwargs=task.kwargs or {},
            queue="scheduled",
        )
        await self.update(task.id, {"last_run_at": datetime.utcnow()})
        logger.info(
            f"Periodic task '{task.name}' triggered manually -> task_id={result.id}"
        )
        return result.id

    async def _before_create(self, data: dict) -> dict:
        existing = await self.repo.get_by_name(data.get("name", ""))
        if existing:
            raise BusinessException(
                message=f"Periodic task with name '{data['name']}' already exists"
            )
        if data.get("scope") == "tenant" and not data.get("tenant_id"):
            raise BusinessException(
                message="scope 为 tenant 时必须指定 tenant_id"
            )
        if data.get("scope") != "tenant":
            data["tenant_id"] = None
        return data

    async def _before_update(self, instance: PeriodicTask, data: dict) -> dict:
        if not instance.is_editable:
            allowed_fields = {"is_active"}
            non_allowed = set(data.keys()) - allowed_fields
            if non_allowed:
                raise BusinessException(
                    message=f"该任务不允许编辑，仅允许切换启用状态"
                )
        return data

    async def _before_delete(self, instance: PeriodicTask) -> None:
        if instance.is_locked:
            raise BusinessException(
                message=f"任务 '{instance.name}' 已被保护，禁止删除"
            )

    async def _after_create(self, instance: PeriodicTask) -> None:
        from app.tasks.scheduler import refresh_schedule
        try:
            refresh_schedule()
        except Exception as e:
            logger.warning(f"Failed to refresh schedule after create: {e}")

    async def _after_update(self, instance: PeriodicTask, data: dict) -> None:
        from app.tasks.scheduler import refresh_schedule
        try:
            refresh_schedule()
        except Exception as e:
            logger.warning(f"Failed to refresh schedule after update: {e}")
