"""
任务运行服务 / Task Run Service
"""

from app.core.base_service import GlobalService
from app.models.system.task_run import TaskRun
from app.repositories.system.task_run_repository import TaskRunRepository


class TaskRunService(GlobalService[TaskRun, TaskRunRepository]):
    """
    任务运行服务 / Task run service.
    """

    model = TaskRun
    repository_class = TaskRunRepository


__all__ = ["TaskRunService"]
