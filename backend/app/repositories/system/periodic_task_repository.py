"""
定时任务仓储 / Periodic Task Repository

提供定时任务的数据访问操作
Provides periodic task data access operations.
"""

from app.core.base_repository import BaseRepository
from app.models.system.periodic_task import PeriodicTask


class PeriodicTaskRepository(BaseRepository[PeriodicTask]):
    """
    定时任务仓储
    """

    model = PeriodicTask

    _scope_fields = {
        "admin": {
            "id", "name", "task_path", "schedule_type",
            "cron_expression", "interval_seconds", "is_active",
            "last_run_at", "next_run_at", "description",
            "tenant_id", "created_at",
        },
        "tenant": {
            "id", "name", "task_path", "schedule_type",
            "cron_expression", "interval_seconds", "is_active",
            "last_run_at", "next_run_at", "description", "created_at",
        },
    }

    async def get_by_name(self, name: str) -> PeriodicTask | None:
        return await self.get_one_by(name=name)

    async def get_active_tasks(self) -> list[PeriodicTask]:
        return await self.get_multi_by(is_active=True)
