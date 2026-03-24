"""
任务日志服务 / Task Log Service

提供任务日志的业务逻辑
Provides task log business logic.
"""

from datetime import datetime
from typing import Literal

from app.core.base_service import GlobalService
from app.models.system.task_run import TaskRun
from app.repositories.system.task_run_repository import TaskRunRepository
from app.schemas.common.query import FilterRule, QuerySpec

TaskLogListView = Literal["all", "execution", "internal"]

HIGH_FREQUENCY_INTERNAL_TASK_NAMES: tuple[str, ...] = (
    "tasks.ai.log_ai_call",
    "app.tasks.scheduled.system_health_check",
    "app.tasks.ai_health_check.ai_provider_health_check",
)


class TaskLogService(GlobalService[TaskRun, TaskRunRepository]):
    """
    任务日志服务 / Task log service.
    """

    model = TaskRun
    repository_class = TaskRunRepository

    async def query_list_by_view(
        self,
        spec: QuerySpec,
        view: TaskLogListView = "all",
        scope: str | None = None,
        forced_filters: list[FilterRule] | None = None,
    ) -> tuple[list[TaskRun], int]:
        if view == "all":
            return await self.query_list(
                spec=spec,
                scope=scope,
                forced_filters=forced_filters,
            )

        include_task_names = (
            list(HIGH_FREQUENCY_INTERNAL_TASK_NAMES) if view == "internal" else None
        )
        exclude_task_names = (
            list(HIGH_FREQUENCY_INTERNAL_TASK_NAMES) if view == "execution" else None
        )

        return await self.repo.query_list(
            spec=spec,
            scope=scope,
            forced_filters=forced_filters,
            include_task_names=include_task_names,
            exclude_task_names=exclude_task_names,
        )

    async def get_dashboard_stats(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> dict:
        return await self.repo.get_stats_by_date_range(start_date, end_date)
