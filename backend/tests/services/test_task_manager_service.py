"""TaskManagerService tests / 任务管理服务测试。"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from app.services.system.task_manager_service import TaskManagerService


def test_retry_task_preserves_task_run_headers(monkeypatch) -> None:
    original_run = SimpleNamespace(
        id=41,
        celery_task_id="celery-original",
        task_definition_id=12,
        binding_id=34,
        task_code_snapshot="tenant.cleanup",
        task_name_snapshot="Tenant Cleanup",
        handler_path_snapshot="app.tasks.demo.cleanup",
        trigger_source="scheduler",
        run_kind="tenant_binding",
        owner_tenant_id=None,
        effective_tenant_id=56,
        trace_id="trace-original",
    )
    send_task = MagicMock(return_value=SimpleNamespace(id="celery-retry"))
    monkeypatch.setattr(
        "app.services.system.task_manager_service.celery_app.send_task",
        send_task,
    )

    result = TaskManagerService.retry_task(
        "app.tasks.demo.cleanup",
        args=[1],
        kwargs={"tenant_id": 56},
        queue="scheduled",
        original_run=original_run,
    )

    headers = send_task.call_args.kwargs["headers"]
    assert result["new_task_id"] == "celery-retry"
    assert result["retry_of_run_id"] == 41
    assert result["trace_id"] == "trace-original"
    assert headers["task_definition_id"] == 12
    assert headers["binding_id"] == 34
    assert headers["effective_tenant_id"] == 56
    assert headers["trace_id"] == "trace-original"
    assert headers["retry_of_task_id"] == "celery-original"
    assert headers["trigger_id"].startswith("manual_retry:41:")
    assert headers["run_key"].startswith(
        "task_definition:12|binding:34|source:scheduler|trigger:manual_retry:41:"
    )
