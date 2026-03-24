"""TaskDefinitionService tests."""

from types import SimpleNamespace
from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from app.services.system.task_definition_service import TaskDefinitionService


@pytest.mark.asyncio
async def test_trigger_now_dispatches_platform_wrapper(mock_db) -> None:
    service = TaskDefinitionService(mock_db)
    definition = SimpleNamespace(
        id=3,
        code="system.health",
        owner_tenant_id=None,
        default_schedule_type="interval",
        default_cron_expression=None,
        default_interval_seconds=300,
    )
    service.get_by_id = AsyncMock(return_value=definition)
    service.update = AsyncMock(return_value=definition)

    fake_result = SimpleNamespace(id="celery-123")
    with patch(
        "app.services.system.task_definition_service.celery_app.send_task",
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
        default_schedule_type="interval",
        default_cron_expression=None,
        default_interval_seconds=60,
    )
    service.get_by_id = AsyncMock(return_value=definition)
    service.update = AsyncMock(return_value=definition)

    fake_result = SimpleNamespace(id="celery-tenant-1")
    binding_repo = MagicMock()
    binding_repo.get_one_by = AsyncMock(return_value=SimpleNamespace(id=9))

    with patch(
        "app.services.system.task_definition_service.TenantTaskBindingRepository",
        return_value=binding_repo,
    ), patch(
        "app.services.system.task_definition_service.celery_app.send_task",
        return_value=fake_result,
    ) as send_task:
        task_id = await service.trigger_now(5)

    assert task_id == "celery-tenant-1"
    assert send_task.call_args.args[0] == "app.tasks.task_scheduling.run_tenant_task_binding"
