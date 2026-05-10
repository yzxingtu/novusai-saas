"""中文: 任务调度 wrapper 分发行为测试。

EN: Task scheduling wrapper dispatch behavior tests.

Test type: behavioral
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.tasks.task_scheduling import (
    run_all_tenants_task_definition,
    run_tenant_task_binding,
)


def test_run_all_tenants_task_definition_dispatches_each_eligible_tenant() -> None:
    definition_query = MagicMock()
    definition_query.filter.return_value = definition_query
    definition_query.first.return_value = SimpleNamespace(
        id=18,
        code="tenant.everyone",
        name="Tenant Everyone",
        handler_path="app.tasks.demo.handle_tenant",
        owner_tenant_id=None,
        default_args=None,
        default_kwargs={"tenant_id": 999, "mode": "daily"},
        default_schedule_type="interval",
        default_cron_expression=None,
        default_interval_seconds=300,
        default_queue="scheduled",
        default_priority=6,
        is_enabled=True,
    )

    session = MagicMock()
    session.query.return_value = definition_query

    send_task = MagicMock(
        side_effect=[
            SimpleNamespace(id="tenant-task-7"),
            SimpleNamespace(id="tenant-task-11"),
        ]
    )

    with (
        patch("app.tasks.task_scheduling.sync_session_factory", return_value=session),
        patch(
            "app.tasks.task_scheduling._handler_requires_tenant",
            return_value=True,
        ),
        patch(
            "app.tasks.task_scheduling.handler_supports_tenant_dispatch",
            return_value=True,
        ),
        patch("app.tasks.task_scheduling.is_handler_registered", return_value=True),
        patch(
            "app.tasks.task_scheduling._resolve_all_tenant_ids",
            return_value=[7, 11],
        ),
        patch("app.tasks.task_scheduling.celery_app.send_task", send_task),
    ):
        result = run_all_tenants_task_definition.run(18)

    assert result["dispatched"] is True
    assert result["tenant_count"] == 2
    assert result["dispatched_task_ids"] == ["tenant-task-7", "tenant-task-11"]
    assert send_task.call_args_list[0].kwargs["kwargs"]["tenant_id"] == 7
    assert send_task.call_args_list[1].kwargs["kwargs"]["tenant_id"] == 11
    assert send_task.call_args_list[0].kwargs["kwargs"]["mode"] == "daily"
    assert send_task.call_args_list[0].kwargs["priority"] == 6
    assert send_task.call_args_list[1].kwargs["priority"] == 6
    assert send_task.call_args_list[0].kwargs["headers"]["queue"] == "scheduled"
    assert send_task.call_args_list[0].kwargs["headers"]["priority"] == 6
    assert (
        send_task.call_args_list[0].kwargs["headers"]["trigger_source"] == "scheduler"
    )
    assert (
        send_task.call_args_list[0].kwargs["headers"]["trigger_slot"]
        == send_task.call_args_list[1].kwargs["headers"]["trigger_slot"]
    )


def test_run_all_tenants_task_definition_prefers_registered_handler_queue() -> None:
    definition_query = MagicMock()
    definition_query.filter.return_value = definition_query
    definition_query.first.return_value = SimpleNamespace(
        id=18,
        code="tenant.ai",
        name="Tenant AI",
        handler_path="app.tasks.demo.handle_tenant",
        owner_tenant_id=None,
        default_args=None,
        default_kwargs={},
        default_schedule_type="interval",
        default_cron_expression=None,
        default_interval_seconds=300,
        default_queue="scheduled",
        default_priority=None,
        is_enabled=True,
    )

    session = MagicMock()
    session.query.return_value = definition_query
    send_task = MagicMock(return_value=SimpleNamespace(id="tenant-task-7"))

    with (
        patch("app.tasks.task_scheduling.sync_session_factory", return_value=session),
        patch(
            "app.tasks.task_scheduling.get_task_registry",
            return_value={
                "app.tasks.demo.handle_tenant": {
                    "base": "TenantTask",
                    "queue": "ai_gateway",
                }
            },
        ),
        patch("app.tasks.task_scheduling.is_handler_registered", return_value=True),
        patch(
            "app.tasks.task_scheduling._resolve_all_tenant_ids",
            return_value=[7],
        ),
        patch("app.tasks.task_scheduling.celery_app.send_task", send_task),
    ):
        result = run_all_tenants_task_definition.run(18)

    assert result["dispatched"] is True
    assert send_task.call_args.kwargs["queue"] == "ai_gateway"
    assert send_task.call_args.kwargs["headers"]["queue"] == "ai_gateway"


def test_run_all_tenants_task_definition_passes_definition_entitlements() -> None:
    definition_query = MagicMock()
    definition_query.filter.return_value = definition_query
    definition_query.first.return_value = SimpleNamespace(
        id=18,
        code="tenant.everyone",
        name="Tenant Everyone",
        handler_path="app.tasks.demo.handle_tenant",
        owner_tenant_id=None,
        default_args=None,
        default_kwargs={},
        default_schedule_type="interval",
        default_cron_expression=None,
        default_interval_seconds=300,
        default_queue="scheduled",
        default_priority=6,
        is_enabled=True,
        required_feature_codes=["storage_billing_enabled"],
        required_plugin_names=["storage-billing"],
    )

    session = MagicMock()
    session.query.return_value = definition_query
    send_task = MagicMock(return_value=SimpleNamespace(id="tenant-task-7"))
    captured_requirements = []

    def _resolve_all_tenant_ids(_session, task_definition_id, requirements=None):
        assert task_definition_id == 18
        captured_requirements.append(requirements)
        assert requirements.feature_codes == ("storage_billing_enabled",)
        assert requirements.plugin_names == ("storage-billing",)
        return [7]

    with (
        patch("app.tasks.task_scheduling.sync_session_factory", return_value=session),
        patch(
            "app.tasks.task_scheduling._resolve_all_tenant_ids",
            side_effect=_resolve_all_tenant_ids,
        ),
        patch(
            "app.tasks.task_scheduling.handler_supports_tenant_dispatch",
            return_value=True,
        ),
        patch("app.tasks.task_scheduling.is_handler_registered", return_value=True),
        patch("app.tasks.task_scheduling.celery_app.send_task", send_task),
    ):
        result = run_all_tenants_task_definition.run(18)

    assert result["dispatched"] is True
    assert result["tenant_count"] == 1
    assert result["dispatched_task_ids"] == ["tenant-task-7"]
    assert [
        (requirements.feature_codes, requirements.plugin_names)
        for requirements in captured_requirements
    ] == [(("storage_billing_enabled",), ("storage-billing",))]


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


def test_run_tenant_task_binding_overwrites_payload_tenant_id() -> None:
    binding_query = MagicMock()
    binding_query.filter.return_value = binding_query
    binding_query.first.return_value = SimpleNamespace(
        id=5,
        tenant_id=42,
        task_definition_id=18,
        is_enabled=True,
        args_override=None,
        kwargs_override={"tenant_id": 777, "binding_mode": "override"},
        schedule_type_override=None,
        cron_expression_override=None,
        interval_seconds_override=None,
    )

    definition_query = MagicMock()
    definition_query.filter.return_value = definition_query
    definition_query.first.return_value = SimpleNamespace(
        id=18,
        code="tenant.selected",
        name="Tenant Selected",
        handler_path="app.tasks.demo.handle_tenant",
        owner_tenant_id=None,
        default_args=None,
        default_kwargs={"tenant_id": 999, "base_mode": "default"},
        default_schedule_type="interval",
        default_cron_expression=None,
        default_interval_seconds=300,
        default_queue="scheduled",
        default_priority=5,
        is_enabled=True,
    )

    session = MagicMock()
    session.query.side_effect = [binding_query, definition_query]
    send_task = MagicMock(return_value=SimpleNamespace(id="tenant-task-42"))

    eligibility = SimpleNamespace(is_eligible=True, reason=None)
    with (
        patch("app.tasks.task_scheduling.sync_session_factory", return_value=session),
        patch(
            "app.tasks.task_scheduling.TaskTenantEligibilityService.resolve_tenant_eligibility_sync",
            return_value=eligibility,
        ),
        patch(
            "app.tasks.task_scheduling.handler_supports_tenant_dispatch",
            return_value=True,
        ),
        patch("app.tasks.task_scheduling._handler_requires_tenant", return_value=True),
        patch("app.tasks.task_scheduling.is_handler_registered", return_value=True),
        patch(
            "app.tasks.task_scheduling.celery_app.send_task",
            send_task,
        ),
    ):
        result = run_tenant_task_binding.run(5)

    assert result["dispatched"] is True
    kwargs = send_task.call_args.kwargs["kwargs"]
    assert kwargs["tenant_id"] == 42
    assert kwargs["base_mode"] == "default"
    assert kwargs["binding_mode"] == "override"
    assert send_task.call_args.kwargs["priority"] == 5


def test_run_tenant_task_binding_skips_tenant_without_active_plan() -> None:
    binding_query = MagicMock()
    binding_query.filter.return_value = binding_query
    binding_query.first.return_value = SimpleNamespace(
        id=5,
        tenant_id=42,
        task_definition_id=18,
        is_enabled=True,
    )

    session = MagicMock()
    session.query.return_value = binding_query

    eligibility = SimpleNamespace(
        is_eligible=False,
        reason="tenant_plan_not_available",
    )
    with (
        patch("app.tasks.task_scheduling.sync_session_factory", return_value=session),
        patch(
            "app.tasks.task_scheduling.TaskTenantEligibilityService.resolve_tenant_eligibility_sync",
            return_value=eligibility,
        ),
    ):
        result = run_tenant_task_binding.run(5)

    assert result == {
        "dispatched": False,
        "reason": "tenant_plan_not_available",
        "binding_id": 5,
        "tenant_id": 42,
    }


def test_run_tenant_task_binding_rejects_ineligible_tenant_requirement() -> None:
    binding_query = MagicMock()
    binding_query.filter.return_value = binding_query
    binding_query.first.return_value = SimpleNamespace(
        id=5,
        tenant_id=42,
        task_definition_id=18,
        is_enabled=True,
    )

    definition_query = MagicMock()
    definition_query.filter.return_value = definition_query
    definition_query.first.return_value = SimpleNamespace(
        id=18,
        code="tenant.selected",
        name="Tenant Selected",
        handler_path="app.tasks.demo.handle_tenant",
        owner_tenant_id=None,
        default_args=None,
        default_kwargs={},
        default_schedule_type="interval",
        default_cron_expression=None,
        default_interval_seconds=300,
        default_queue="scheduled",
        default_priority=5,
        is_enabled=True,
        required_feature_codes=["storage_billing_enabled"],
        required_plugin_names=[],
    )

    session = MagicMock()
    session.query.side_effect = [binding_query, definition_query]
    send_task = MagicMock()

    with (
        patch("app.tasks.task_scheduling.sync_session_factory", return_value=session),
        patch(
            "app.tasks.task_scheduling.TaskTenantEligibilityService.resolve_tenant_eligibility_sync",
            side_effect=[
                SimpleNamespace(is_eligible=True, reason=None),
                SimpleNamespace(
                    is_eligible=False,
                    reason="tenant_entitlement_not_available",
                ),
            ],
        ),
        patch(
            "app.tasks.task_scheduling.handler_supports_tenant_dispatch",
            return_value=True,
        ),
        patch("app.tasks.task_scheduling.is_handler_registered", return_value=True),
        patch("app.tasks.task_scheduling.celery_app.send_task", send_task),
    ):
        result = run_tenant_task_binding.run(5)

    assert result == {
        "dispatched": False,
        "reason": "tenant_entitlement_not_available",
        "binding_id": 5,
        "tenant_id": 42,
    }
    send_task.assert_not_called()


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
