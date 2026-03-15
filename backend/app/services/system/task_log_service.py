"""
任务日志服务 / Task Log Service

提供任务日志的业务逻辑
Provides task log business logic.
"""

from datetime import datetime

from app.core.base_model import utc_now
from app.core.base_service import GlobalService
from app.enums.task import TaskStatusEnum
from app.models.system.task_log import TaskLog
from app.repositories.system.task_log_repository import TaskLogRepository


class TaskLogService(GlobalService[TaskLog, TaskLogRepository]):
    """
    任务日志服务 / Task log service.
    """

    model = TaskLog
    repository_class = TaskLogRepository

    async def record_start(
        self,
        task_id: str,
        task_name: str,
        queue: str = "default",
        args: dict | None = None,
        kwargs: dict | None = None,
        tenant_id: int | None = None,
    ) -> TaskLog:
        return await self.create({
            "task_id": task_id,
            "task_name": task_name,
            "queue": queue,
            "status": TaskStatusEnum.RUNNING.value,
            "args": args,
            "kwargs": kwargs,
            "started_at": utc_now(),
            "tenant_id": tenant_id,
        })

    async def record_success(
        self,
        task_id: str,
        result: dict | None = None,
        duration_ms: int | None = None,
    ) -> TaskLog | None:
        log = await self.repo.get_by_task_id(task_id)
        if log is None:
            return None
        now = utc_now()
        update_data = {
            "status": TaskStatusEnum.SUCCESS.value,
            "result": result,
            "finished_at": now,
        }
        if duration_ms is not None:
            update_data["duration_ms"] = duration_ms
        elif log.started_at:
            update_data["duration_ms"] = int(
                (now - log.started_at).total_seconds() * 1000
            )
        return await self.update(log.id, update_data)

    async def record_failure(
        self,
        task_id: str,
        error_message: str,
        traceback_str: str | None = None,
        duration_ms: int | None = None,
    ) -> TaskLog | None:
        log = await self.repo.get_by_task_id(task_id)
        if log is None:
            return None
        now = utc_now()
        update_data: dict = {
            "status": TaskStatusEnum.FAILED.value,
            "error_message": error_message,
            "traceback": traceback_str,
            "finished_at": now,
        }
        if duration_ms is not None:
            update_data["duration_ms"] = duration_ms
        elif log.started_at:
            update_data["duration_ms"] = int(
                (now - log.started_at).total_seconds() * 1000
            )
        return await self.update(log.id, update_data)

    async def record_retry(
        self,
        task_id: str,
        retry_count: int,
        error_message: str,
    ) -> TaskLog | None:
        log = await self.repo.get_by_task_id(task_id)
        if log is None:
            return None
        return await self.update(log.id, {
            "status": TaskStatusEnum.RETRYING.value,
            "retry_count": retry_count,
            "error_message": error_message,
        })

    async def get_dashboard_stats(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> dict:
        return await self.repo.get_stats_by_date_range(start_date, end_date)
