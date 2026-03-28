"""Task scheduling wrapper tests."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.tasks.task_scheduling import run_all_tenants_task_definition, run_tenant_task_binding


def test_run_all_tenants_task_definition_dispatches_each_non_deleted_tenant() -> None:
    definition_query = MagicMock()
    definition_query.filter.return_value = definition_query
    definition_query.first.return_value = SimpleNamespace(
        id=18,
        code="tenant.everyone",
        name="Tenant Everyone",
        handler_path="app.tasks.demo.handle_tenant",
        owner_tenant_id=None,
        default_args=None,
        default_kwargs=None,
        default_queue="scheduled",
        is_enabled=True,
    )

    tenant_query = MagicMock()
    tenant_query.filter.return_value = tenant_query
    tenant_query.order_by.return_value = tenant_query
    tenant_query.all.return_value = [(7,), (11,)]

    session = MagicMock()
    session.query.side_effect = [definition_query, tenant_query]

    send_task = MagicMock(
        side_effect=[
            SimpleNamespace(id="tenant-task-7"),
            SimpleNamespace(id="tenant-task-11"),
        ]
    )

    with patch("app.tasks.task_scheduling.sync_session_factory", return_value=session), patch(
        "app.tasks.task_scheduling._handler_requires_tenant",
        return_value=True,
    ), patch(
        "app.tasks.task_scheduling.handler_supports_tenant_dispatch",
        return_value=True,
    ), patch("app.tasks.task_scheduling.celery_app.send_task", send_task):
        result = run_all_tenants_task_definition.run(18)

    assert result["dispatched"] is True
    assert result["tenant_count"] == 2
    assert result["dispatched_task_ids"] == ["tenant-task-7", "tenant-task-11"]
    assert send_task.call_args_list[0].kwargs["kwargs"]["tenant_id"] == 7
    assert send_task.call_args_list[1].kwargs["kwargs"]["tenant_id"] == 11
    assert send_task.call_args_list[0].kwargs["headers"]["trigger_source"] == "scheduler"


def test_run_tenant_task_binding_skips_soft_deleted_tenant() -> None:
    binding_query = MagicMock()
    binding_query.filter.return_value = binding_query
    binding_query.first.return_value = SimpleNamespace(
        id=5,
        tenant_id=42,
        task_definition_id=18,
        is_enabled=True,
    )

    tenant_query = MagicMock()
    tenant_query.filter.return_value = tenant_query
    tenant_query.first.return_value = None

    session = MagicMock()
    session.query.side_effect = [binding_query, tenant_query]

    with patch("app.tasks.task_scheduling.sync_session_factory", return_value=session):
        result = run_tenant_task_binding.run(5)

    assert result == {
        "dispatched": False,
        "reason": "tenant_not_available",
        "binding_id": 5,
        "tenant_id": 42,
    }


def test_run_all_tenants_task_definition_rejects_non_tenant_handler() -> None:
    definition_query = MagicMock()
    definition_query.filter.return_value = definition_query
    definition_query.first.return_value = SimpleNamespace(
        id=18,
        code="tenant.everyone",
        name="Tenant Everyone",
        handler_path="app.tasks.scheduled.clean_expired_captchas",
        owner_tenant_id=None,
        default_args=None,
        default_kwargs=None,
        default_queue="scheduled",
        is_enabled=True,
    )

    session = MagicMock()
    session.query.return_value = definition_query

    with patch("app.tasks.task_scheduling.sync_session_factory", return_value=session):
        result = run_all_tenants_task_definition.run(18)

    assert result == {
        "dispatched": False,
        "reason": "tenant_dispatch_unsupported",
        "task_definition_id": 18,
        "handler_path": "app.tasks.scheduled.clean_expired_captchas",
    }
