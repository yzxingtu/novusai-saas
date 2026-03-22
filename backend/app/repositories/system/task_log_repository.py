"""
任务日志仓储 / Task Log Repository

提供任务日志的数据访问操作
Provides task log data access operations.
"""

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import func, select

from app.core.base_repository import BaseRepository
from app.enums.task import TaskStatusEnum
from app.models.system.task_log import TaskLog
from app.schemas.common.query import FilterRule, QuerySpec


class TaskLogRepository(BaseRepository[TaskLog]):
    """
    任务日志仓储 / Task log repository.
    """

    model = TaskLog

    _scope_fields = {
        "admin": {
            "id",
            "task_id",
            "task_name",
            "queue",
            "status",
            "tenant_id",
            "created_at",
            "duration_ms",
        },
        "tenant": {
            "id",
            "task_id",
            "task_name",
            "queue",
            "status",
            "created_at",
            "duration_ms",
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
                "avg_duration_ms": float(row.avg_duration_ms)
                if row.avg_duration_ms
                else 0,
            }
            for row in rows
        }

    async def query_list(
        self,
        spec: QuerySpec,
        scope: str | None = None,
        forced_filters: list[FilterRule] | None = None,
        include_deleted: bool = False,
        include_task_names: Sequence[str] | None = None,
        exclude_task_names: Sequence[str] | None = None,
    ) -> tuple[list[TaskLog], int]:
        if include_task_names and exclude_task_names:
            raise ValueError(
                "include_task_names and exclude_task_names cannot be used together"
            )

        allowed_fields = self.get_allowed_fields(scope)
        all_fields = self.get_allowed_fields(None)
        query = select(self.model)

        if not include_deleted:
            query = query.where(self.model.is_deleted.is_(False))

        if forced_filters:
            query = self._apply_filters(query, forced_filters, all_fields)

        if spec.filters:
            query = self._apply_filters(query, spec.filters, allowed_fields)

        if include_task_names:
            query = query.where(self.model.task_name.in_(list(include_task_names)))

        if exclude_task_names:
            query = query.where(~self.model.task_name.in_(list(exclude_task_names)))

        query = self._apply_data_permission_if_needed(query)

        count_query = select(func.count()).select_from(query.subquery())
        count_result = await self.db.execute(count_query)
        total = count_result.scalar() or 0

        sortable_fields = self.get_sortable_fields()
        query = self._apply_sort(query, spec.sort, sortable_fields)
        query = query.offset(spec.offset).limit(spec.limit)

        result = await self.db.execute(query)
        return list(result.scalars().all()), total
