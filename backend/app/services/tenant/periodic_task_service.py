"""
租户端定时任务服务

提供租户端定时任务 CRUD（自动按 tenant_id 过滤）
"""

from app.celery_app import celery_app
from app.core.base_service import TenantService
from app.exceptions import BusinessException, NotFoundException
from app.core.logging import LogManager
from app.models.system.periodic_task import PeriodicTask
from app.repositories.tenant.periodic_task_repository import TenantPeriodicTaskRepository

logger = LogManager.get_logger("queue")


class TenantPeriodicTaskService(TenantService[PeriodicTask, TenantPeriodicTaskRepository]):
    """
    租户端定时任务服务
    """

    model = PeriodicTask
    repository_class = TenantPeriodicTaskRepository

    async def toggle_active(self, task_id: int, is_active: bool) -> PeriodicTask:
        task = await self.get_by_id(task_id)
        if task is None:
            raise NotFoundException("periodic_task.not_found")
        return await self.update(task_id, {"is_active": is_active})

    async def trigger_now(self, task_id: int) -> str:
        task = await self.get_by_id(task_id)
        if task is None:
            raise NotFoundException("periodic_task.not_found")
        if not task.is_active:
            raise BusinessException("periodic_task.disabled")

        result = celery_app.send_task(
            task.task_path,
            args=task.args or [],
            kwargs={**(task.kwargs or {}), "tenant_id": self.tenant_id},
        )
        logger.info(f"Tenant {self.tenant_id} triggered periodic task: {task.name} -> {result.id}")
        return result.id


__all__ = ["TenantPeriodicTaskService"]
