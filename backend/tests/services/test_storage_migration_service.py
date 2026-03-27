from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

PLUGINS_ROOT = Path(__file__).resolve().parents[2] / 'plugins'


def _load_migration_module():
    module_path = (
        PLUGINS_ROOT
        / 'storage-migration'
        / 'backend'
        / 'services'
        / 'migration_service.py'
    )
    module_name = 'test_runtime_storage_migration_service'
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.mark.asyncio
async def test_storage_migration_analyzer_rejects_same_driver(mock_db):
    migration_module = _load_migration_module()
    analyzer = migration_module.MigrationImpactAnalyzer(mock_db)

    with pytest.raises(ValueError, match='different'):
        await analyzer.analyze('local', 'local')


def test_storage_migration_normalize_task_row_defaults_cleanup_fields(mock_db):
    migration_module = _load_migration_module()
    service = migration_module.StorageMigrationService.__new__(
        migration_module.StorageMigrationService,
    )
    service._db = mock_db

    row = service._normalize_task_row(
        {
            'scope': 'tenant:42',
            'source_config_snapshot': '{"driver": "local"}',
            'target_config_snapshot': None,
            'source_cleanup_deleted_files': '3',
            'source_cleanup_error_count': None,
        }
    )

    assert row['scope'] == 'tenant:42'
    assert row['source_config_snapshot'] == {'driver': 'local'}
    assert row['source_cleanup_deleted_files'] == 3
    assert row['source_cleanup_error_count'] == 0


@pytest.mark.asyncio
async def test_storage_migration_start_task_clears_stale_error(mock_db):
    migration_module = _load_migration_module()
    migration_module._pause_events.clear()
    migration_module._running_migrations.clear()
    migration_module._cancel_flags.clear()

    service = migration_module.StorageMigrationService.__new__(
        migration_module.StorageMigrationService,
    )
    service._db = mock_db
    service.get_task = AsyncMock(return_value={'status': 'pending'})
    service._update_task_status = AsyncMock()
    service._run_migration = AsyncMock()

    fake_bg_task = MagicMock()

    with patch.object(
        migration_module.asyncio,
        'create_task',
        return_value=fake_bg_task,
    ):
        result = await migration_module.StorageMigrationService.start_task(
            service,
            7,
        )

    assert result == {'status': 'running', 'task_id': 7}
    assert service._update_task_status.await_args.args[:2] == (7, 'running')
    assert service._update_task_status.await_args.kwargs['error_message'] is None
    mock_db.commit.assert_awaited_once()
    assert migration_module._pause_events[7].is_set() is True
    assert migration_module._running_migrations[7] is fake_bg_task


@pytest.mark.asyncio
async def test_storage_migration_retry_failed_restarts_task(mock_db):
    migration_module = _load_migration_module()
    service = migration_module.StorageMigrationService.__new__(
        migration_module.StorageMigrationService,
    )
    service._db = mock_db
    service.get_task = AsyncMock(return_value={'status': 'failed'})
    service.start_task = AsyncMock(return_value={'status': 'running', 'task_id': 9})

    reset_result = MagicMock()
    reset_result.rowcount = 2
    mock_db.execute = AsyncMock(side_effect=[reset_result, MagicMock()])

    result = await migration_module.StorageMigrationService.retry_failed(
        service,
        9,
    )

    assert result == {'status': 'running', 'task_id': 9}
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
            'status': 'completed',
            'source_cleanup_started_at': '2026-03-25T00:00:00Z',
            'source_cleanup_completed_at': None,
            'source_cleanup_deleted_files': 0,
        }
    )

    result = await migration_module.StorageMigrationService.rollback_task(
        service,
        3,
    )

    assert 'cleanup' in result['error']
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
            'status': 'completed',
            'source_cleanup_completed_at': '2026-03-25T00:00:00Z',
        }
    )

    result = await migration_module.StorageMigrationService.cleanup_source_files(
        service,
        5,
    )

    assert result == {'error': 'Source files were already cleaned up for this task'}
