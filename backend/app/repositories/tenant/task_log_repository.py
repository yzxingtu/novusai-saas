"""
租户端任务日志仓储

提供任务日志数据访问能力（租户隔离）
"""

from app.core.base_repository import TenantRepository
from app.models.system.task_log import TaskLog


class TenantTaskLogRepository(TenantRepository[TaskLog]):
    """
    租户端任务日志仓储（自动按 tenant_id 过滤）
    """

    model = TaskLog

    _scope_fields = {
        "tenant": {
            "id", "task_id", "task_name", "queue",
            "status", "created_at", "duration_ms",
        },
    }


__all__ = ["TenantTaskLogRepository"]
