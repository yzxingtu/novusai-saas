"""
任务日志仓储 / Task Log Repository

提供任务日志的数据访问操作
Provides task log data access operations.
"""

from datetime import datetime

from sqlalchemy import func, select

from app.core.base_repository import BaseRepository
from app.enums.task import TaskStatusEnum
from app.models.system.task_log import TaskLog


class TaskLogRepository(BaseRepository[TaskLog]):
    """
    任务日志仓储
    """

    model = TaskLog

    _scope_fields = {
        "admin": {
            "id", "task_id", "task_name", "queue",
            "status", "tenant_id", "created_at", "duration_ms",
        },
        "tenant": {
            "id", "task_id", "task_name", "queue",
            "status", "created_at", "duration_ms",
        },
    }

    async def get_by_task_id(self, task_id: str) -> TaskLog | None:
        return await self.get_one_by(task_id=task_id)

    async def get_failed_tasks(
        self,
        limit: int = 50,
        offset: int = 0,
    ) -> list[TaskLog]:
        stmt = (
            select(TaskLog)
            .where(
                TaskLog.status == TaskStatusEnum.FAILED.value,
                TaskLog.is_deleted.is_(False),  # noqa: E712
            )
            .order_by(TaskLog.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_stats_by_date_range(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> dict:
        stmt = (
            select(
                TaskLog.status,
                func.count(TaskLog.id).label("count"),
                func.avg(TaskLog.duration_ms).label("avg_duration_ms"),
            )
            .where(
                TaskLog.created_at >= start_date,
                TaskLog.created_at <= end_date,
                TaskLog.is_deleted.is_(False),  # noqa: E712
            )
            .group_by(TaskLog.status)
        )
        result = await self.db.execute(stmt)
        rows = result.all()
        return {
            row.status: {
                "count": row.count,
                "avg_duration_ms": float(row.avg_duration_ms) if row.avg_duration_ms else 0,
            }
            for row in rows
        }
