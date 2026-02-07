"""
租户端任务日志服务

提供租户端任务日志查询（只读，自动按 tenant_id 过滤）
"""

from datetime import datetime

from app.core.base_service import TenantService
from app.models.system.task_log import TaskLog
from app.repositories.tenant.task_log_repository import TenantTaskLogRepository


class TenantTaskLogService(TenantService[TaskLog, TenantTaskLogRepository]):
    """
    租户端任务日志服务（只读）
    """

    model = TaskLog
    repository_class = TenantTaskLogRepository

    async def get_dashboard_stats(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> dict:
        return await self.repo.get_stats_by_date_range(start_date, end_date)


__all__ = ["TenantTaskLogService"]
