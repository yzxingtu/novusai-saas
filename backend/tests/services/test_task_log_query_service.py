"""中文: 任务日志读模型合同测试。

EN: Contract tests for task-log read models.

Test type: behavioral
"""

from datetime import UTC, datetime
from types import SimpleNamespace

from app.services.system.task_log_query_service import TaskLogRelationService


def _task_run() -> SimpleNamespace:
    return SimpleNamespace(
        id=1,
        celery_task_id="celery-1",
        run_key="task:1:slot",
        task_name_snapshot="Example task",
        handler_path_snapshot="app.tasks.example",
        task_definition_id=2,
        binding_id=3,
        owner_tenant_id=None,
        effective_tenant_id=42,
        queue="scheduled",
        status="success",
        args_summary={"args": [1], "kwargs": {"tenant_id": 42}},
        result_summary={"cleaned": 1},
        error_message_public=None,
        error_message_internal=None,
        trigger_source="scheduler",
        run_kind="tenant_binding",
        trace_id="trace-1",
        started_at=datetime(2026, 5, 10, tzinfo=UTC),
        finished_at=datetime(2026, 5, 10, tzinfo=UTC),
        duration_ms=12,
        retry_count=0,
        created_at=datetime(2026, 5, 10, tzinfo=UTC),
        traceback_internal="stack",
    )


def test_task_log_response_uses_effective_tenant_id_without_tenant_alias() -> None:
    service = TaskLogRelationService(db=None)

    payload = service.serialize_task_run(_task_run())
    detail = service.serialize_task_run_detail(_task_run())

    assert payload["effective_tenant_id"] == 42
    assert "tenant_id" not in payload
    assert detail["effective_tenant_id"] == 42
    assert "tenant_id" not in detail
