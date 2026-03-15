"""OperationLogService 单元测试 / Test.

覆盖：日志记录、查询、清理。"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from tests.services.conftest import make_mock_model


def _make_log(**overrides):
    defaults = {
        "id": 1,
        "admin_id": 1,
        "tenant_id": None,
        "username": "admin",
        "action": "create",
        "module": "tenant",
        "path": "/admin/tenants",
        "method": "POST",
        "status_code": 200,
        "duration_ms": 50,
    }
    defaults.update(overrides)
    return make_mock_model(**defaults)


class TestLogRecord:

    @pytest.mark.asyncio
    async def test_create_log_entry(self, mock_db):
        from app.services.system.operation_log_service import OperationLogService

        service = OperationLogService.__new__(OperationLogService)
        service.db = mock_db
        service.repo = AsyncMock()
        service.repo.create = AsyncMock(return_value=_make_log())

        result = await service.repo.create({
            "admin_id": 1,
            "username": "admin",
            "action": "create",
            "module": "tenant",
            "path": "/admin/tenants",
            "method": "POST",
            "status_code": 200,
        })
        assert result.action == "create"


class TestLogQuery:

    @pytest.mark.asyncio
    async def test_query_returns_list(self, mock_db):
        from app.services.system.operation_log_service import OperationLogService

        logs = [_make_log(id=i) for i in range(5)]
        service = OperationLogService.__new__(OperationLogService)
        service.db = mock_db
        service.repo = AsyncMock()
        service.repo.query_list = AsyncMock(return_value=(logs, 5))

        items, total = await service.repo.query_list(MagicMock())
        assert len(items) == 5
        assert total == 5

    @pytest.mark.asyncio
    async def test_query_empty(self, mock_db):
        from app.services.system.operation_log_service import OperationLogService

        service = OperationLogService.__new__(OperationLogService)
        service.db = mock_db
        service.repo = AsyncMock()
        service.repo.query_list = AsyncMock(return_value=([], 0))

        items, total = await service.repo.query_list(MagicMock())
        assert len(items) == 0
        assert total == 0


class TestLogFilter:

    @pytest.mark.asyncio
    async def test_filter_by_module(self, mock_db):
        from app.services.system.operation_log_service import OperationLogService

        logs = [_make_log(module="tenant")]
        service = OperationLogService.__new__(OperationLogService)
        service.db = mock_db
        service.repo = AsyncMock()
        service.repo.query_list = AsyncMock(return_value=(logs, 1))

        items, total = await service.repo.query_list(MagicMock())
        assert items[0].module == "tenant"

    @pytest.mark.asyncio
    async def test_filter_by_method(self, mock_db):
        from app.services.system.operation_log_service import OperationLogService

        logs = [_make_log(method="DELETE")]
        service = OperationLogService.__new__(OperationLogService)
        service.db = mock_db
        service.repo = AsyncMock()
        service.repo.query_list = AsyncMock(return_value=(logs, 1))

        items, _ = await service.repo.query_list(MagicMock())
        assert items[0].method == "DELETE"


class TestLogCleanup:

    @pytest.mark.asyncio
    async def test_cleanup_old_logs(self, mock_db):
        from app.services.system.operation_log_service import OperationLogService

        service = OperationLogService.__new__(OperationLogService)
        service.db = mock_db
        service.repo = AsyncMock()
        service.repo.delete_before = AsyncMock(return_value=100)

        deleted = await service.repo.delete_before(days=30)
        assert deleted == 100
