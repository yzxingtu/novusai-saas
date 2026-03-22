"""TaskLogService tests / 任务日志服务测试。"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from sqlalchemy.dialects import postgresql

from app.schemas.common.query import QuerySpec
from tests.services.conftest import make_scalar_result, make_scalars_result


def _compile_sql(statement) -> str:
    return str(
        statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )


class TestTaskLogViewRouting:
    @pytest.mark.asyncio
    async def test_query_list_by_view_all_uses_raw_feed(self, mock_db):
        from app.services.system.task_log_service import TaskLogService

        service = TaskLogService.__new__(TaskLogService)
        service.db = mock_db
        service.repo = AsyncMock()
        service.repo.query_list = AsyncMock(return_value=([], 0))
        spec = QuerySpec()

        await service.query_list_by_view(spec, view="all")

        service.repo.query_list.assert_awaited_once_with(
            spec=spec,
            scope=None,
            forced_filters=None,
        )

    @pytest.mark.asyncio
    async def test_query_list_by_view_execution_excludes_internal_tasks(self, mock_db):
        from app.services.system.task_log_service import (
            HIGH_FREQUENCY_INTERNAL_TASK_NAMES,
            TaskLogService,
        )

        service = TaskLogService.__new__(TaskLogService)
        service.db = mock_db
        service.repo = AsyncMock()
        service.repo.query_list = AsyncMock(return_value=([], 0))
        spec = QuerySpec()

        await service.query_list_by_view(spec, view="execution")

        service.repo.query_list.assert_awaited_once_with(
            spec=spec,
            scope=None,
            forced_filters=None,
            include_task_names=None,
            exclude_task_names=list(HIGH_FREQUENCY_INTERNAL_TASK_NAMES),
        )

    @pytest.mark.asyncio
    async def test_query_list_by_view_internal_only_includes_internal_tasks(
        self, mock_db
    ):
        from app.services.system.task_log_service import (
            HIGH_FREQUENCY_INTERNAL_TASK_NAMES,
            TaskLogService,
        )

        service = TaskLogService.__new__(TaskLogService)
        service.db = mock_db
        service.repo = AsyncMock()
        service.repo.query_list = AsyncMock(return_value=([], 0))
        spec = QuerySpec()

        await service.query_list_by_view(spec, view="internal")

        service.repo.query_list.assert_awaited_once_with(
            spec=spec,
            scope=None,
            forced_filters=None,
            include_task_names=list(HIGH_FREQUENCY_INTERNAL_TASK_NAMES),
            exclude_task_names=None,
        )


class TestTaskLogRepositoryFilters:
    @pytest.mark.asyncio
    async def test_query_list_excludes_selected_task_names(self, mock_db):
        from app.repositories.system.task_log_repository import TaskLogRepository

        repo = TaskLogRepository(mock_db)
        mock_db.execute.side_effect = [
            make_scalar_result(0),
            make_scalars_result([]),
        ]

        await repo.query_list(
            QuerySpec(sort=["-created_at"]),
            exclude_task_names=[
                "tasks.ai.log_ai_call",
                "app.tasks.scheduled.system_health_check",
            ],
        )

        data_stmt = mock_db.execute.await_args_list[1].args[0]
        sql = _compile_sql(data_stmt)
        assert "NOT IN" in sql
        assert "'tasks.ai.log_ai_call'" in sql
        assert "'app.tasks.scheduled.system_health_check'" in sql

    @pytest.mark.asyncio
    async def test_query_list_includes_selected_task_names(self, mock_db):
        from app.repositories.system.task_log_repository import TaskLogRepository

        repo = TaskLogRepository(mock_db)
        mock_db.execute.side_effect = [
            make_scalar_result(0),
            make_scalars_result([]),
        ]

        await repo.query_list(
            QuerySpec(sort=["-created_at"]),
            include_task_names=["tasks.ai.log_ai_call"],
        )

        data_stmt = mock_db.execute.await_args_list[1].args[0]
        sql = _compile_sql(data_stmt)
        assert " IN " in sql
        assert "'tasks.ai.log_ai_call'" in sql
