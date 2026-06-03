"""
任务运行仓储 / Task Run Repository
"""

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import func, select

from app.core.base_repository import BaseRepository
from app.models.system.task_run import TaskRun
from app.schemas.common.query import FilterRule, QuerySpec


class TaskRunRepository(BaseRepository[TaskRun]):
    """
    任务运行仓储 / Task run repository.
    """

    model = TaskRun

    _scope_fields = {
        "admin": {
            "id",
            "task_id",
            "run_key",
            "task_name",
            "handler_path",
            "queue",
            "priority",
            "status",
            "trigger_slot",
            "trigger_id",
            "retry_of_run_id",
            "retry_of_task_id",
            "effective_tenant_id",
            "created_at",
            "duration_ms",
        },
    }

    async def get_by_celery_task_id(self, celery_task_id: str) -> TaskRun | None:
        return await self.get_one_by(celery_task_id=celery_task_id)

    async def get_failed_tasks(
        self,
        limit: int = 50,
        offset: int = 0,
    ) -> list[TaskRun]:
        stmt = (
            select(TaskRun)
            .where(
                TaskRun.status == "failed",
                TaskRun.is_deleted.is_(False),  # noqa: E712
            )
            .order_by(TaskRun.created_at.desc())
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
                TaskRun.status,
                func.count(TaskRun.id).label("count"),
                func.avg(TaskRun.duration_ms).label("avg_duration_ms"),
            )
            .where(
                TaskRun.created_at >= start_date,
                TaskRun.created_at <= end_date,
                TaskRun.is_deleted.is_(False),  # noqa: E712
            )
            .group_by(TaskRun.status)
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
    ) -> tuple[list[TaskRun], int]:
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
            query = query.where(
                self.model.handler_path_snapshot.in_(list(include_task_names))
            )

        if exclude_task_names:
            query = query.where(
                ~self.model.handler_path_snapshot.in_(list(exclude_task_names))
            )

        query = self._apply_data_permission_if_needed(query)

        count_query = select(func.count()).select_from(query.subquery())
        count_result = await self.db.execute(count_query)
        total = count_result.scalar() or 0

        sortable_fields = self.get_sortable_fields()
        query = self._apply_sort(query, spec.sort, sortable_fields)
        query = query.offset(spec.offset).limit(spec.limit)

        result = await self.db.execute(query)
        return list(result.scalars().all()), total


__all__ = ["TaskRunRepository"]
