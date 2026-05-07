"""TaskDefinitionService tests."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.i18n import _
from app.enums.common import ResourceScopeEnum
from app.enums.plugin import PluginStatusEnum
from app.exceptions import BusinessException
from app.services.system.task_definition_service import TaskDefinitionService


@pytest.mark.asyncio
async def test_trigger_now_dispatches_platform_wrapper(mock_db) -> None:
    service = TaskDefinitionService(mock_db)
    definition = SimpleNamespace(
        id=3,
        code="system.health",
        owner_tenant_id=None,
        scope=ResourceScopeEnum.ADMIN_ONLY.value,
        default_schedule_type="interval",
        default_cron_expression=None,
        default_interval_seconds=300,
        default_priority=4,
    )
    service.get_by_id = AsyncMock(return_value=definition)
    service.update = AsyncMock(return_value=definition)
    binding_rows = MagicMock()
    binding_rows.scalars.return_value.all.return_value = []
    mock_db.execute = AsyncMock(return_value=binding_rows)

    fake_result = SimpleNamespace(id="celery-123")
    with patch(
        "app.services.system.task_definition_service.celery_app.send_task",
        return_value=fake_result,
    ) as send_task:
        trigger_result = await service.trigger_now(3)

    assert trigger_result == {
        "triggered_task_id": "celery-123",
        "dispatched_task_ids": ["celery-123"],
        "dispatched_count": 1,
    }
    assert send_task.call_args.kwargs["queue"] == "scheduled"
    assert send_task.call_args.kwargs["priority"] == 4
    assert (
        send_task.call_args.args[0] == "app.tasks.task_scheduling.run_task_definition"
    )


@pytest.mark.asyncio
async def test_trigger_now_dispatches_binding_wrapper_for_tenant_owned_definition(
    mock_db,
) -> None:
    service = TaskDefinitionService(mock_db)
    definition = SimpleNamespace(
        id=5,
        code="tenant.job",
        handler_path="app.ai.rag.processor.process_document",
        owner_tenant_id=42,
        scope=ResourceScopeEnum.SELECTED_TENANTS.value,
        default_schedule_type="interval",
        default_cron_expression=None,
        default_interval_seconds=60,
    )
    service.get_by_id = AsyncMock(return_value=definition)
    service.update = AsyncMock(return_value=definition)

    fake_result = SimpleNamespace(id="celery-tenant-1")
    binding_rows = MagicMock()
    binding_rows.scalars.return_value.all.return_value = [
        SimpleNamespace(
            id=9,
            schedule_type_override=None,
            cron_expression_override=None,
            interval_seconds_override=None,
        )
    ]
    mock_db.execute = AsyncMock(return_value=binding_rows)

    with (
        patch(
            "app.services.system.task_definition_service.handler_supports_tenant_dispatch",
            return_value=True,
        ),
        patch(
            "app.services.system.task_definition_service.celery_app.send_task",
            return_value=fake_result,
        ) as send_task,
    ):
        trigger_result = await service.trigger_now(5)

    assert trigger_result["triggered_task_id"] == "celery-tenant-1"
    assert trigger_result["dispatched_task_ids"] == ["celery-tenant-1"]
    assert (
        send_task.call_args.args[0]
        == "app.tasks.task_scheduling.run_tenant_task_binding"
    )


@pytest.mark.asyncio
async def test_trigger_now_dispatches_all_tenants_wrapper(mock_db) -> None:
    service = TaskDefinitionService(mock_db)
    definition = SimpleNamespace(
        id=21,
        code="tenant.all",
        handler_path="app.ai.rag.processor.process_document",
        owner_tenant_id=None,
        scope=ResourceScopeEnum.ALL_TENANTS.value,
        default_schedule_type="interval",
        default_cron_expression=None,
        default_interval_seconds=120,
    )
    service.get_by_id = AsyncMock(return_value=definition)
    service.update = AsyncMock(return_value=definition)

    fake_result = SimpleNamespace(id="all-tenants-123")
    with (
        patch(
            "app.services.system.task_definition_service.handler_supports_tenant_dispatch",
            return_value=True,
        ),
        patch(
            "app.services.system.task_definition_service.celery_app.send_task",
            return_value=fake_result,
        ) as send_task,
    ):
        trigger_result = await service.trigger_now(21)

    assert trigger_result["triggered_task_id"] == "all-tenants-123"
    assert trigger_result["dispatched_task_ids"] == ["all-tenants-123"]
    assert (
        send_task.call_args.args[0]
        == "app.tasks.task_scheduling.run_all_tenants_task_definition"
    )
    assert send_task.call_args.kwargs["kwargs"]["trigger_source"] == "admin_manual"


@pytest.mark.asyncio
async def test_trigger_now_rejects_plugin_task_when_plugin_is_disabled(mock_db) -> None:
    service = TaskDefinitionService(mock_db)
    definition = SimpleNamespace(
        id=16,
        code="plugin.storage-billing.daily_reconciliation",
        owner_tenant_id=None,
        scope=ResourceScopeEnum.ADMIN_ONLY.value,
        default_schedule_type="cron",
        default_cron_expression="0 3 * * *",
        default_interval_seconds=None,
    )
    service.get_by_id = AsyncMock(return_value=definition)

    plugin_status_result = MagicMock()
    plugin_status_result.scalar_one_or_none.return_value = (
        PluginStatusEnum.DISABLED.value
    )
    mock_db.execute = AsyncMock(return_value=plugin_status_result)

    with pytest.raises(BusinessException) as exc_info:
        await service.trigger_now(16)

    assert exc_info.value.message == _(
        "periodic_task.error.plugin_disabled",
        plugin="storage-billing",
    )


@pytest.mark.asyncio
async def test_trigger_now_dispatches_all_bindings_and_returns_first_task_id(
    mock_db,
) -> None:
    service = TaskDefinitionService(mock_db)
    definition = SimpleNamespace(
        id=8,
        code="tenant.batch",
        handler_path="app.ai.rag.processor.process_document",
        owner_tenant_id=None,
        scope=ResourceScopeEnum.SELECTED_TENANTS.value,
        default_schedule_type="interval",
        default_cron_expression=None,
        default_interval_seconds=120,
    )
    service.get_by_id = AsyncMock(return_value=definition)
    service.update = AsyncMock(return_value=definition)
    binding_rows = MagicMock()
    binding_rows.scalars.return_value.all.return_value = [
        SimpleNamespace(
            id=31,
            schedule_type_override=None,
            cron_expression_override=None,
            interval_seconds_override=None,
        ),
        SimpleNamespace(
            id=32,
            schedule_type_override=None,
            cron_expression_override=None,
            interval_seconds_override=None,
        ),
    ]
    mock_db.execute = AsyncMock(return_value=binding_rows)

    send_task = MagicMock(
        side_effect=[
            SimpleNamespace(id="binding-task-1"),
            SimpleNamespace(id="binding-task-2"),
        ]
    )

    with (
        patch(
            "app.services.system.task_definition_service.handler_supports_tenant_dispatch",
            return_value=True,
        ),
        patch(
            "app.services.system.task_definition_service.celery_app.send_task",
            send_task,
        ),
    ):
        trigger_result = await service.trigger_now(8)

    assert trigger_result["triggered_task_id"] == "binding-task-1"
    assert trigger_result["dispatched_task_ids"] == [
        "binding-task-1",
        "binding-task-2",
    ]
    assert trigger_result["dispatched_count"] == 2
    assert send_task.call_count == 2
    assert (
        send_task.call_args_list[0].args[0]
        == "app.tasks.task_scheduling.run_tenant_task_binding"
    )
    assert (
        send_task.call_args_list[1].args[0]
        == "app.tasks.task_scheduling.run_tenant_task_binding"
    )


@pytest.mark.asyncio
async def test_trigger_now_dispatches_platform_and_selected_bindings_for_admin_and_selected_scope(
    mock_db,
) -> None:
    service = TaskDefinitionService(mock_db)
    definition = SimpleNamespace(
        id=13,
        code="hybrid.audit",
        handler_path="app.ai.rag.processor.process_document",
        owner_tenant_id=None,
        scope=ResourceScopeEnum.ADMIN_AND_SELECTED_TENANTS.value,
        default_schedule_type="interval",
        default_cron_expression=None,
        default_interval_seconds=120,
    )
    service.get_by_id = AsyncMock(return_value=definition)
    service.update = AsyncMock(return_value=definition)
    binding_rows = MagicMock()
    binding_rows.scalars.return_value.all.return_value = [
        SimpleNamespace(
            id=71,
            schedule_type_override=None,
            cron_expression_override=None,
            interval_seconds_override=None,
        )
    ]
    mock_db.execute = AsyncMock(return_value=binding_rows)

    send_task = MagicMock(
        side_effect=[
            SimpleNamespace(id="binding-task-1"),
            SimpleNamespace(id="platform-task-1"),
        ]
    )

    with (
        patch(
            "app.services.system.task_definition_service.handler_supports_tenant_dispatch",
            return_value=True,
        ),
        patch(
            "app.services.system.task_definition_service.celery_app.send_task",
            send_task,
        ),
    ):
        trigger_result = await service.trigger_now(13)

    assert trigger_result["triggered_task_id"] == "binding-task-1"
    assert trigger_result["dispatched_task_ids"] == [
        "binding-task-1",
        "platform-task-1",
    ]
    assert trigger_result["dispatched_count"] == 2
    assert send_task.call_count == 2
    assert (
        send_task.call_args_list[0].args[0]
        == "app.tasks.task_scheduling.run_tenant_task_binding"
    )
    assert (
        send_task.call_args_list[1].args[0]
        == "app.tasks.task_scheduling.run_task_definition"
    )


@pytest.mark.asyncio
async def test_trigger_now_rejects_selected_scope_without_dispatch_targets(
    mock_db,
) -> None:
    service = TaskDefinitionService(mock_db)
    definition = SimpleNamespace(
        id=21,
        code="tenant.missing",
        handler_path="app.ai.rag.processor.process_document",
        owner_tenant_id=None,
        scope=ResourceScopeEnum.SELECTED_TENANTS.value,
        default_schedule_type="interval",
        default_cron_expression=None,
        default_interval_seconds=120,
    )
    service.get_by_id = AsyncMock(return_value=definition)
    service.update = AsyncMock(return_value=definition)
    binding_rows = MagicMock()
    binding_rows.scalars.return_value.all.return_value = []
    mock_db.execute = AsyncMock(return_value=binding_rows)

    with (
        pytest.raises(BusinessException) as exc_info,
        patch(
            "app.services.system.task_definition_service.handler_supports_tenant_dispatch",
            return_value=True,
        ),
    ):
        await service.trigger_now(21)

    assert exc_info.value.message == _("periodic_task.error.binding_required")


@pytest.mark.asyncio
async def test_trigger_now_rejects_tenant_dispatch_scope_for_non_tenant_handler(
    mock_db,
) -> None:
    service = TaskDefinitionService(mock_db)
    definition = SimpleNamespace(
        id=31,
        code="tenant.invalid",
        owner_tenant_id=None,
        scope=ResourceScopeEnum.ALL_TENANTS.value,
        handler_path="app.tasks.scheduled.clean_expired_captchas",
        default_schedule_type="interval",
        default_cron_expression=None,
        default_interval_seconds=120,
    )
    service.get_by_id = AsyncMock(return_value=definition)

    with pytest.raises(BusinessException) as exc_info:
        await service.trigger_now(31)

    assert exc_info.value.message == _(
        "periodic_task.error.tenant_dispatch_requires_tenant_handler",
        handler="app.tasks.scheduled.clean_expired_captchas",
    )
