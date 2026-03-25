"""TaskDefinitionService tests."""

from types import SimpleNamespace
from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from app.enums.common import ResourceScopeEnum
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
    )
    service.get_by_id = AsyncMock(return_value=definition)
    service.update = AsyncMock(return_value=definition)
    binding_rows = MagicMock()
    binding_rows.scalars.return_value.all.return_value = []
    mock_db.execute = AsyncMock(return_value=binding_rows)

    fake_result = SimpleNamespace(id="celery-123")
    with patch("app.services.system.task_definition_service.celery_app.send_task",
        return_value=fake_result,
    ) as send_task:
        task_id = await service.trigger_now(3)

    assert task_id == "celery-123"
    assert send_task.call_args.kwargs["queue"] == "scheduled"
    assert send_task.call_args.args[0] == "app.tasks.task_scheduling.run_task_definition"


@pytest.mark.asyncio
async def test_trigger_now_dispatches_binding_wrapper_for_tenant_owned_definition(mock_db) -> None:
    service = TaskDefinitionService(mock_db)
    definition = SimpleNamespace(
        id=5,
        code="tenant.job",
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

    with patch("app.services.system.task_definition_service.celery_app.send_task",
        return_value=fake_result,
    ) as send_task:
        task_id = await service.trigger_now(5)

    assert task_id == "celery-tenant-1"
    assert send_task.call_args.args[0] == "app.tasks.task_scheduling.run_tenant_task_binding"


@pytest.mark.asyncio
async def test_trigger_now_dispatches_all_bindings_and_returns_first_task_id(mock_db) -> None:
    service = TaskDefinitionService(mock_db)
    definition = SimpleNamespace(
        id=8,
        code="tenant.batch",
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

    with patch(
        "app.services.system.task_definition_service.celery_app.send_task",
        send_task,
    ):
        task_id = await service.trigger_now(8)

    assert task_id == "binding-task-1"
    assert send_task.call_count == 2
    assert send_task.call_args_list[0].args[0] == "app.tasks.task_scheduling.run_tenant_task_binding"
    assert send_task.call_args_list[1].args[0] == "app.tasks.task_scheduling.run_tenant_task_binding"


@pytest.mark.asyncio
async def test_trigger_now_dispatches_platform_and_selected_bindings_for_admin_and_selected_scope(
    mock_db,
) -> None:
    service = TaskDefinitionService(mock_db)
    definition = SimpleNamespace(
        id=13,
        code="hybrid.audit",
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

    with patch(
        "app.services.system.task_definition_service.celery_app.send_task",
        send_task,
    ):
        task_id = await service.trigger_now(13)

    assert task_id == "binding-task-1"
    assert send_task.call_count == 2
    assert send_task.call_args_list[0].args[0] == "app.tasks.task_scheduling.run_tenant_task_binding"
    assert send_task.call_args_list[1].args[0] == "app.tasks.task_scheduling.run_task_definition"


@pytest.mark.asyncio
async def test_trigger_now_rejects_tenant_scope_without_dispatch_targets(mock_db) -> None:
    service = TaskDefinitionService(mock_db)
    definition = SimpleNamespace(
        id=21,
        code="tenant.missing",
        owner_tenant_id=None,
        scope=ResourceScopeEnum.ALL_TENANTS.value,
        default_schedule_type="interval",
        default_cron_expression=None,
        default_interval_seconds=120,
    )
    service.get_by_id = AsyncMock(return_value=definition)
    service.update = AsyncMock(return_value=definition)
    binding_rows = MagicMock()
    binding_rows.scalars.return_value.all.return_value = []
    mock_db.execute = AsyncMock(return_value=binding_rows)

    with pytest.raises(BusinessException):
        await service.trigger_now(21)
