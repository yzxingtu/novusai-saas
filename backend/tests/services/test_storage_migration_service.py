"""
Test type: behavioral
Scope: storage migration plugin service loading, runtime registry, and storage
config resolution.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.plugins.module_loader import load_plugin_module


def _load_migration_module():
    module = load_plugin_module("storage-migration", "services.migration_service")
    assert module is not None
    return module


def test_storage_migration_service_does_not_export_runtime_state_shims() -> None:
    migration_module = _load_migration_module()

    assert not hasattr(migration_module, "_pause_events")
    assert not hasattr(migration_module, "_running_migrations")
    assert not hasattr(migration_module, "_cancel_flags")


@pytest.mark.asyncio
async def test_storage_migration_analyzer_rejects_same_driver(mock_db):
    migration_module = _load_migration_module()
    analyzer = migration_module.MigrationImpactAnalyzer(mock_db)

    with pytest.raises(ValueError, match="different"):
        await analyzer.analyze("local", "local")


def test_storage_migration_normalize_task_row_defaults_cleanup_fields(mock_db):
    migration_module = _load_migration_module()
    service = migration_module.StorageMigrationService.__new__(
        migration_module.StorageMigrationService,
    )
    service._db = mock_db

    row = service._normalize_task_row(
        {
            "scope": "tenant:42",
            "source_config_snapshot": '{"driver": "local"}',
            "target_config_snapshot": None,
            "source_cleanup_deleted_files": "3",
            "source_cleanup_error_count": None,
        }
    )

    assert row["scope"] == "tenant:42"
    assert row["source_config_snapshot"] == {"driver": "local"}
    assert row["source_cleanup_deleted_files"] == 3
    assert row["source_cleanup_error_count"] == 0


@pytest.mark.asyncio
async def test_storage_migration_start_task_clears_stale_error(mock_db):
    migration_module = _load_migration_module()
    migration_module.runtime_registry.clear_runtime(7)

    service = migration_module.StorageMigrationService.__new__(
        migration_module.StorageMigrationService,
    )
    service._db = mock_db
    service.get_task = AsyncMock(return_value={"status": "pending"})
    service._update_task_status = AsyncMock()
    service._run_migration = AsyncMock()

    fake_bg_task = MagicMock()

    with patch.object(
        migration_module.asyncio,
        "create_task",
        return_value=fake_bg_task,
    ):
        result = await migration_module.StorageMigrationService.start_task(
            service,
            7,
        )

    assert result == {"status": "running", "task_id": 7}
    assert service._update_task_status.await_args.args[:2] == (7, "running")
    assert service._update_task_status.await_args.kwargs["error_message"] is None
    mock_db.commit.assert_awaited_once()
    pause_event = migration_module.runtime_registry.get_pause_event(7)
    assert pause_event is not None
    assert pause_event.is_set() is True
    assert migration_module.runtime_registry.pop_background_task(7) is fake_bg_task
    migration_module.runtime_registry.clear_runtime(7)


@pytest.mark.asyncio
async def test_storage_migration_retry_failed_restarts_task(mock_db):
    migration_module = _load_migration_module()
    service = migration_module.StorageMigrationService.__new__(
        migration_module.StorageMigrationService,
    )
    service._db = mock_db
    service.get_task = AsyncMock(return_value={"status": "failed"})
    service.start_task = AsyncMock(return_value={"status": "running", "task_id": 9})

    reset_result = MagicMock()
    reset_result.rowcount = 2
    mock_db.execute = AsyncMock(side_effect=[reset_result, MagicMock()])

    result = await migration_module.StorageMigrationService.retry_failed(
        service,
        9,
    )

    assert result == {"status": "running", "task_id": 9}
    mock_db.commit.assert_awaited_once()
    service.start_task.assert_awaited_once_with(9)


@pytest.mark.asyncio
async def test_storage_migration_rollback_blocks_after_cleanup_started(mock_db):
    migration_module = _load_migration_module()
    service = migration_module.StorageMigrationService.__new__(
        migration_module.StorageMigrationService,
    )
    service._db = mock_db
    service.get_task = AsyncMock(
        return_value={
            "status": "completed",
            "source_cleanup_started_at": "2026-03-25T00:00:00Z",
            "source_cleanup_completed_at": None,
            "source_cleanup_deleted_files": 0,
        }
    )

    result = await migration_module.StorageMigrationService.rollback_task(
        service,
        3,
    )

    assert "cleanup" in result["error"]
    mock_db.execute.assert_not_called()


@pytest.mark.asyncio
async def test_storage_migration_cleanup_rejects_repeated_run(mock_db):
    migration_module = _load_migration_module()
    service = migration_module.StorageMigrationService.__new__(
        migration_module.StorageMigrationService,
    )
    service._db = mock_db
    service.get_task = AsyncMock(
        return_value={
            "status": "completed",
            "source_cleanup_completed_at": "2026-03-25T00:00:00Z",
        }
    )

    result = await migration_module.StorageMigrationService.cleanup_source_files(
        service,
        5,
    )

    assert result == {"error": "Source files were already cleaned up for this task"}


@pytest.mark.asyncio
async def test_storage_migration_tenant_config_resolution_fails_closed(mock_db):
    migration_module = _load_migration_module()
    service = migration_module.StorageMigrationService.__new__(
        migration_module.StorageMigrationService,
    )
    service._db = mock_db

    resolver = MagicMock()
    resolver.resolve_for_attachment = AsyncMock(side_effect=RuntimeError("tenant down"))
    resolver.resolve_platform_config = AsyncMock(
        return_value=migration_module.StorageConfig(driver="local", root_path="")
    )

    with pytest.raises(RuntimeError, match="tenant down"):
        await service._resolve_driver_config(resolver, "local", "tenant:42")

    resolver.resolve_platform_config.assert_not_awaited()
