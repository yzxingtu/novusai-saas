"""
企业端任务日志仓储 / Tenant Task Log Repository

提供任务日志数据访问能力（企业隔离）
Provides task log data access (tenant-isolated).
"""

from app.core.base_repository import TenantRepository
from app.models.system.task_log import TaskLog


class TenantTaskLogRepository(TenantRepository[TaskLog]):
    """
    企业端任务日志仓储（自动按 tenant_id 过滤）/ Tenant task log repository (auto tenant_id filter).
    """

    model = TaskLog

    _scope_fields = {
        "tenant": {
            "id", "task_id", "task_name", "queue",
            "status", "created_at", "duration_ms",
        },
    }


__all__ = ["TenantTaskLogRepository"]
