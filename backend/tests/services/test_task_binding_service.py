"""TaskBindingService tests."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.i18n import _
from app.enums.common import ResourceScopeEnum
from app.exceptions import BusinessException
from app.services.system.task_binding_service import TaskBindingService


@pytest.mark.asyncio
async def test_list_by_definition_returns_serializable_rows(mock_db) -> None:
    service = TaskBindingService(mock_db)
    mock_db.get = AsyncMock(return_value=None)
    binding = SimpleNamespace(
        id=5,
        tenant_id=42,
        is_enabled=True,
        disabled_reason=None,
        schedule_type_override=None,
        cron_expression_override=None,
        interval_seconds_override=None,
        config_override=None,
        args_override=None,
        kwargs_override=None,
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
            "disabled_reason": None,
            "schedule_type_override": None,
            "cron_expression_override": None,
            "interval_seconds_override": None,
            "config_override": None,
            "args_override": None,
            "kwargs_override": None,
            "effective_schedule_type": None,
            "effective_cron_expression": None,
            "effective_interval_seconds": None,
            "last_run_at": None,
            "next_run_at": None,
        }
    ]


@pytest.mark.asyncio
async def test_get_definition_binding_summary_returns_names_and_counts(mock_db) -> None:
    service = TaskBindingService(mock_db)
    result = MagicMock()
    result.all.return_value = [
        (
            SimpleNamespace(task_definition_id=9, tenant_id=11, is_enabled=True),
            "Acme",
        ),
        (
            SimpleNamespace(task_definition_id=9, tenant_id=12, is_enabled=True),
            "Beta",
        ),
    ]
    mock_db.execute = AsyncMock(return_value=result)

    summary = await service.get_definition_binding_summary([9])

    assert summary == {
        9: {
            "active_binding_count": 2,
            "assigned_tenant_ids": [11, 12],
            "assigned_tenant_names": ["Acme", "Beta"],
            "binding_count": 2,
            "binding_summary": "Acme, Beta",
        }
    }


@pytest.mark.asyncio
async def test_sync_definition_bindings_adds_reenables_and_removes(mock_db) -> None:
    service = TaskBindingService(mock_db)
    definition = SimpleNamespace(
        scope="admin_only",
        handler_path="app.ai.rag.processor.process_document",
    )
    mock_db.get = AsyncMock(return_value=definition)
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

    with (
        patch(
            "app.services.system.task_binding_service.handler_supports_tenant_dispatch",
            return_value=True,
        ),
        patch(
            "app.services.system.task_binding_service.TaskTenantEligibilityService.resolve_tenant_eligibility",
            return_value=SimpleNamespace(is_eligible=True, reason=None),
        ),
    ):
        stats = await service.sync_definition_bindings(
            99,
            [20, 30],
            target_scope="selected_tenants",
        )

    assert stats == {"added": 1, "removed": 1, "reenabled": 1, "updated": 1}
    assert definition.scope == "selected_tenants"
    service.repo.create.assert_awaited_once_with(
        {
            "task_definition_id": 99,
            "tenant_id": 30,
            "is_enabled": True,
        }
    )
    service.repo.update.assert_awaited_once_with(2, {"is_enabled": True})


@pytest.mark.asyncio
async def test_resolve_target_tenant_ids_accepts_all_tenants_denylist(mock_db) -> None:
    service = TaskBindingService(mock_db)
    tenant_ids = await service.resolve_target_tenant_ids(
        ResourceScopeEnum.ALL_TENANTS.value,
        [3, 7, 11],
    )

    assert tenant_ids == [3, 7, 11]


@pytest.mark.asyncio
async def test_resolve_target_tenant_ids_deduplicates_selected_scope(mock_db) -> None:
    service = TaskBindingService(mock_db)

    tenant_ids = await service.resolve_target_tenant_ids(
        ResourceScopeEnum.SELECTED_TENANTS.value,
        [7, 3, 7, 11],
    )

    assert tenant_ids == [7, 3, 11]


@pytest.mark.asyncio
async def test_sync_definition_bindings_keeps_explicit_scope_pending_when_empty(
    mock_db,
) -> None:
    service = TaskBindingService(mock_db)
    definition = SimpleNamespace(
        scope=ResourceScopeEnum.SELECTED_TENANTS.value,
        handler_path="app.ai.rag.processor.process_document",
    )
    mock_db.get = AsyncMock(return_value=definition)
    existing = SimpleNamespace(id=1, tenant_id=10, is_enabled=True)

    result = MagicMock()
    result.scalars.return_value.all.return_value = [existing]
    delete_result = MagicMock()
    delete_result.rowcount = 1
    mock_db.execute = AsyncMock(side_effect=[result, delete_result])

    service.repo.create = AsyncMock()
    service.repo.update = AsyncMock()

    with (
        patch(
            "app.services.system.task_binding_service.handler_supports_tenant_dispatch",
            return_value=True,
        ),
        patch(
            "app.services.system.task_binding_service.TaskTenantEligibilityService.resolve_tenant_eligibility",
            return_value=SimpleNamespace(is_eligible=True, reason=None),
        ),
    ):
        stats = await service.sync_definition_bindings(
            99,
            [],
            target_scope=ResourceScopeEnum.SELECTED_TENANTS.value,
        )

    assert stats == {"added": 0, "removed": 1, "reenabled": 0, "updated": 0}
    assert definition.scope == ResourceScopeEnum.SELECTED_TENANTS.value


@pytest.mark.asyncio
async def test_sync_definition_bindings_clears_explicit_bindings_for_all_tenants_scope(
    mock_db,
) -> None:
    service = TaskBindingService(mock_db)
    definition = SimpleNamespace(
        scope=ResourceScopeEnum.ADMIN_AND_SELECTED_TENANTS.value,
        handler_path="app.ai.rag.processor.process_document",
    )
    mock_db.get = AsyncMock(return_value=definition)
    existing = SimpleNamespace(id=1, tenant_id=10, is_enabled=True)

    result = MagicMock()
    result.scalars.return_value.all.return_value = [existing]
    delete_result = MagicMock()
    delete_result.rowcount = 1
    mock_db.execute = AsyncMock(side_effect=[result, delete_result])

    service.repo.create = AsyncMock()
    service.repo.update = AsyncMock()

    with (
        patch(
            "app.services.system.task_binding_service.handler_supports_tenant_dispatch",
            return_value=True,
        ),
        patch(
            "app.services.system.task_binding_service.TaskTenantEligibilityService.resolve_tenant_eligibility",
            return_value=SimpleNamespace(is_eligible=True, reason=None),
        ),
    ):
        stats = await service.sync_definition_bindings(
            99,
            [10, 20],
            target_scope=ResourceScopeEnum.ALL_TENANTS.value,
        )

    assert stats == {"added": 1, "removed": 0, "reenabled": 0, "updated": 1}
    assert definition.scope == ResourceScopeEnum.ALL_TENANTS.value


@pytest.mark.asyncio
async def test_sync_definition_bindings_preserves_disabled_all_tenants_denies(
    mock_db,
) -> None:
    service = TaskBindingService(mock_db)
    definition = SimpleNamespace(
        scope=ResourceScopeEnum.ALL_TENANTS.value,
        handler_path="app.ai.rag.processor.process_document",
    )
    mock_db.get = AsyncMock(return_value=definition)
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

    with patch(
        "app.services.system.task_binding_service.handler_supports_tenant_dispatch",
        return_value=True,
    ):
        stats = await service.sync_definition_bindings(
            99,
            [],
            target_scope=ResourceScopeEnum.ALL_TENANTS.value,
        )

    assert stats == {"added": 0, "removed": 1, "reenabled": 0, "updated": 0}
    delete_stmt = mock_db.execute.await_args_list[1].args[0]
    assert "tenant_task_bindings.id IN" in str(delete_stmt)


@pytest.mark.asyncio
async def test_sync_definition_bindings_rejects_non_tenant_handler_for_tenant_dispatch_scope(
    mock_db,
) -> None:
    service = TaskBindingService(mock_db)
    definition = SimpleNamespace(
        scope=ResourceScopeEnum.ADMIN_ONLY.value,
        handler_path="app.tasks.scheduled.clean_expired_captchas",
    )
    mock_db.get = AsyncMock(return_value=definition)
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    mock_db.execute = AsyncMock(return_value=result)

    with pytest.raises(BusinessException) as exc_info:
        await service.sync_definition_bindings(
            99,
            [1],
            target_scope=ResourceScopeEnum.ALL_TENANTS.value,
        )

    assert exc_info.value.message == _(
        "periodic_task.error.tenant_dispatch_requires_tenant_handler",
        handler="app.tasks.scheduled.clean_expired_captchas",
    )


@pytest.mark.asyncio
async def test_upsert_tenant_binding_creates_disabled_all_tenants_deny(mock_db) -> None:
    service = TaskBindingService(mock_db)
    definition = SimpleNamespace(
        scope=ResourceScopeEnum.ALL_TENANTS.value,
        handler_path="app.ai.rag.processor.process_document",
        is_deleted=False,
    )
    mock_db.get = AsyncMock(return_value=definition)
    result = MagicMock()
    result.scalars.return_value.first.return_value = None
    mock_db.execute = AsyncMock(return_value=result)
    created = SimpleNamespace(id=9, tenant_id=42, is_enabled=False)
    service.repo.create = AsyncMock(return_value=created)

    with (
        patch(
            "app.services.system.task_binding_service.handler_supports_tenant_dispatch",
            return_value=True,
        ),
        patch(
            "app.services.system.task_binding_service.TaskTenantEligibilityService.resolve_tenant_eligibility",
            return_value=SimpleNamespace(is_eligible=True, reason=None),
        ),
    ):
        binding = await service.upsert_tenant_binding(
            99,
            42,
            {
                "is_enabled": False,
                "disabled_reason": "tenant opted out",
            },
        )

    assert binding is created
    service.repo.create.assert_awaited_once_with(
        {
            "task_definition_id": 99,
            "tenant_id": 42,
            "is_enabled": False,
            "disabled_reason": "tenant opted out",
        }
    )


@pytest.mark.asyncio
async def test_upsert_tenant_binding_rejects_all_tenants_enabled_overrides(
    mock_db,
) -> None:
    service = TaskBindingService(mock_db)
    definition = SimpleNamespace(
        scope=ResourceScopeEnum.ALL_TENANTS.value,
        handler_path="app.ai.rag.processor.process_document",
        is_deleted=False,
    )
    mock_db.get = AsyncMock(return_value=definition)

    with (
        patch(
            "app.services.system.task_binding_service.handler_supports_tenant_dispatch",
            return_value=True,
        ),
        patch(
            "app.services.system.task_binding_service.TaskTenantEligibilityService.resolve_tenant_eligibility",
            return_value=SimpleNamespace(is_eligible=True, reason=None),
        ),
        pytest.raises(BusinessException) as exc_info,
    ):
        await service.upsert_tenant_binding(
            99,
            42,
            {"is_enabled": True, "kwargs_override": {"mode": "quiet"}},
        )

    assert exc_info.value.message == _(
        "periodic_task.error.all_tenants_binding_deny_only"
    )


@pytest.mark.asyncio
async def test_upsert_tenant_binding_updates_existing_override(mock_db) -> None:
    service = TaskBindingService(mock_db)
    definition = SimpleNamespace(
        scope=ResourceScopeEnum.SELECTED_TENANTS.value,
        handler_path="app.ai.rag.processor.process_document",
        is_deleted=False,
    )
    mock_db.get = AsyncMock(return_value=definition)
    existing = SimpleNamespace(id=4, tenant_id=42)
    result = MagicMock()
    result.scalars.return_value.first.return_value = existing
    mock_db.execute = AsyncMock(return_value=result)
    updated = SimpleNamespace(id=4, tenant_id=42, is_enabled=True)
    service.repo.update = AsyncMock(return_value=updated)

    with (
        patch(
            "app.services.system.task_binding_service.handler_supports_tenant_dispatch",
            return_value=True,
        ),
        patch(
            "app.services.system.task_binding_service.TaskTenantEligibilityService.resolve_tenant_eligibility",
            return_value=SimpleNamespace(is_eligible=True, reason=None),
        ),
    ):
        binding = await service.upsert_tenant_binding(
            99,
            42,
            {"is_enabled": True, "interval_seconds_override": 300},
        )

    assert binding is updated
    service.repo.update.assert_awaited_once_with(
        4,
        {"is_enabled": True, "interval_seconds_override": 300},
    )
