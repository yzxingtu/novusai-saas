"""
任务管理服务

提供任务重试、取消、活跃任务查询等管理功能
"""

from app.celery_app import celery_app
from app.core.logging import LogManager

logger = LogManager.get_logger("queue")


class TaskManagerService:
    """
    任务管理服务

    封装 Celery 控制操作，提供任务重试、取消和监控功能
    """

    @staticmethod
    def retry_task(
        task_name: str,
        args: list | None = None,
        kwargs: dict | None = None,
        queue: str | None = None,
    ) -> str:
        result = celery_app.send_task(
            task_name,
            args=args or [],
            kwargs=kwargs or {},
            queue=queue or "default",
        )
        logger.info(
            f"Task retried: {task_name} -> new task_id={result.id}"
        )
        return result.id

    @staticmethod
    def cancel_task(task_id: str, terminate: bool = False) -> None:
        celery_app.control.revoke(task_id, terminate=terminate)
        logger.info(
            f"Task cancelled: {task_id} terminate={terminate}"
        )

    @staticmethod
    def get_active_tasks() -> list[dict]:
        inspect = celery_app.control.inspect()
        active = inspect.active()
        if not active:
            return []

        tasks = []
        for worker_name, worker_tasks in active.items():
            for task in worker_tasks:
                tasks.append({
                    "task_id": task.get("id", ""),
                    "task_name": task.get("name", ""),
                    "worker": worker_name,
                    "started_at": task.get("time_start"),
                })
        return tasks

    @staticmethod
    def get_scheduled_tasks() -> list[dict]:
        inspect = celery_app.control.inspect()
        scheduled = inspect.scheduled()
        if not scheduled:
            return []

        tasks = []
        for worker_name, worker_tasks in scheduled.items():
            for task in worker_tasks:
                req = task.get("request", {})
                tasks.append({
                    "task_id": req.get("id", ""),
                    "task_name": req.get("name", ""),
                    "worker": worker_name,
                    "eta": task.get("eta"),
                })
        return tasks
