"""
企业端定时任务仓储 / Tenant Periodic Task Repository

提供定时任务数据访问能力（企业隔离）
Provides periodic task data access (tenant-isolated).
"""

from app.core.base_repository import TenantRepository
from app.models.system.periodic_task import PeriodicTask


class TenantPeriodicTaskRepository(TenantRepository[PeriodicTask]):
    """
    企业端定时任务仓储（自动按 tenant_id 过滤）/ Tenant periodic task repository (auto tenant_id filter).
    """

    model = PeriodicTask

    _scope_fields = {
        "tenant": {
            "id", "name", "task_path", "schedule_type",
            "cron_expression", "interval_seconds", "is_active",
            "last_run_at", "next_run_at", "description", "created_at",
        },
    }

    async def get_by_name(self, name: str) -> PeriodicTask | None:
        return await self.get_one_by(name=name)


__all__ = ["TenantPeriodicTaskRepository"]
