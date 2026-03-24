"""TaskBindingService tests."""

from types import SimpleNamespace
from unittest.mock import AsyncMock
from unittest.mock import MagicMock

import pytest

from app.services.system.task_binding_service import TaskBindingService


@pytest.mark.asyncio
async def test_list_by_definition_returns_serializable_rows(mock_db) -> None:
    service = TaskBindingService(mock_db)
    binding = SimpleNamespace(
        id=5,
        tenant_id=42,
        is_enabled=True,
        schedule_type_override=None,
        cron_expression_override=None,
        interval_seconds_override=None,
        last_run_at=None,
        next_run_at=None,
    )
    result = MagicMock()
    result.all.return_value = [(binding, "Acme")]
    mock_db.execute = AsyncMock(return_value=result)

    rows = await service.list_by_definition(99)

    assert rows == [
        {
            "id": 5,
            "tenant_id": 42,
            "tenant_name": "Acme",
            "is_enabled": True,
            "schedule_type_override": None,
            "cron_expression_override": None,
            "interval_seconds_override": None,
            "last_run_at": None,
            "next_run_at": None,
        }
    ]


@pytest.mark.asyncio
async def test_sync_definition_bindings_adds_reenables_and_removes(mock_db) -> None:
    service = TaskBindingService(mock_db)
    existing_enabled = SimpleNamespace(id=1, tenant_id=10, is_enabled=True)
    existing_disabled = SimpleNamespace(id=2, tenant_id=20, is_enabled=False)

    result = MagicMock()
    result.scalars.return_value.all.return_value = [
        existing_enabled,
        existing_disabled,
    ]
    delete_result = MagicMock()
    delete_result.rowcount = 1
    mock_db.execute = AsyncMock(side_effect=[result, delete_result])

    service.repo.create = AsyncMock()
    service.repo.update = AsyncMock()

    stats = await service.sync_definition_bindings(99, [20, 30])

    assert stats == {"added": 1, "removed": 1, "reenabled": 1}
    service.repo.create.assert_awaited_once_with(
        {
            "task_definition_id": 99,
            "tenant_id": 30,
            "is_enabled": True,
        }
    )
    service.repo.update.assert_awaited_once_with(2, {"is_enabled": True})
