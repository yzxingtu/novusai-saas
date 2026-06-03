"""Regression tests for BaseRepository facade delegation."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.sql import Select


@pytest.fixture()
def mock_db():
    db = MagicMock()
    db.execute = AsyncMock()
    db.flush = AsyncMock()
    db.refresh = AsyncMock()
    db.add = MagicMock()
    db.delete = AsyncMock()
    return db


@pytest.mark.asyncio
async def test_operation_log_repository_create_keeps_mapping_payload(mock_db):
    from app.repositories.system.operation_log_repository import OperationLogRepository

    repo = OperationLogRepository(mock_db)

    created = await repo.create_log(
        {
            "user_type": "admin",
            "user_id": 1,
            "username": "admin",
            "action": "query",
            "module": "operation_log",
            "method": "GET",
            "path": "/admin/system/logs",
            "status_code": 200,
        }
    )

    assert created.path == "/admin/system/logs"
    assert created.method == "GET"
    mock_db.add.assert_called_once_with(created)
    mock_db.flush.assert_awaited_once()
    mock_db.refresh.assert_awaited_once_with(created)


@pytest.mark.asyncio
async def test_attachment_repository_get_by_id_executes_select_statement(mock_db):
    from app.repositories.tenant.attachment_repository import AttachmentRepository

    attachment = SimpleNamespace(tenant_id=23)
    result = MagicMock()
    result.scalar_one_or_none.return_value = attachment
    mock_db.execute.return_value = result

    repo = AttachmentRepository(mock_db, tenant_id=23)
    found = await repo.get_by_id(26)

    stmt = mock_db.execute.await_args.args[0]
    assert found is attachment
    assert isinstance(stmt, Select)
