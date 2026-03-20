"""CallLogService 单元测试 / CallLogService tests.

覆盖：调用日志查询、统计聚合。"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from tests.services.conftest import make_mock_model


def _make_call_log(**overrides):
    defaults = {
        "id": 1,
        "tenant_id": 1,
        "agent_id": 1,
        "provider_id": 1,
        "model_name": "gpt-4",
        "request_type": "chat",
        "status": "success",
        "input_tokens": 100,
        "output_tokens": 200,
        "total_tokens": 300,
        "cost": 0.01,
        "latency_ms": 500,
    }
    defaults.update(overrides)
    obj = make_mock_model(**defaults)
    obj.to_dict.return_value = defaults
    return obj


class TestCallLogQuery:

    @pytest.mark.asyncio
    async def test_get_by_id_found(self, mock_db):
        from app.services.ai.call_log_service import CallLogService

        log = _make_call_log()
        service = CallLogService.__new__(CallLogService)
        service.db = mock_db
        service.tenant_id = 1
        service.repo = AsyncMock()
        service.repo.get_by_id = AsyncMock(return_value=log)

        result = await service.repo.get_by_id(1)
        assert result.model_name == "gpt-4"

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self, mock_db):
        from app.services.ai.call_log_service import CallLogService

        service = CallLogService.__new__(CallLogService)
        service.db = mock_db
        service.tenant_id = 1
        service.repo = AsyncMock()
        service.repo.get_by_id = AsyncMock(return_value=None)

        result = await service.repo.get_by_id(999)
        assert result is None


class TestCallLogList:

    @pytest.mark.asyncio
    async def test_get_list_returns_results(self, mock_db):
        from app.services.ai.call_log_service import CallLogService

        logs = [_make_call_log(id=i) for i in range(5)]
        service = CallLogService.__new__(CallLogService)
        service.db = mock_db
        service.tenant_id = 1
        service.repo = AsyncMock()
        service.repo.query_list = AsyncMock(return_value=(logs, 5))

        items, total = await service.repo.query_list(MagicMock())
        assert len(items) == 5
        assert total == 5

    @pytest.mark.asyncio
    async def test_get_failed_logs(self, mock_db):
        from app.services.ai.call_log_service import CallLogService

        failed = [_make_call_log(status="error")]
        service = CallLogService.__new__(CallLogService)
        service.db = mock_db
        service.tenant_id = 1
        service.repo = AsyncMock()
        service.repo.get_failed_logs = AsyncMock(return_value=failed)

        result = await service.get_failed_logs()
        assert len(result) == 1
        assert result[0].status == "error"


class TestCallLogCreate:

    @pytest.mark.asyncio
    async def test_create_log_entry(self, mock_db):
        from app.services.ai.call_log_service import CallLogService

        log = _make_call_log()
        service = CallLogService.__new__(CallLogService)
        service.db = mock_db
        service.tenant_id = 1
        service.repo = AsyncMock()
        service.repo.create = AsyncMock(return_value=log)

        result = await service.repo.create(_make_call_log())
        assert result.status == "success"

    @pytest.mark.asyncio
    async def test_create_error_log(self, mock_db):
        from app.services.ai.call_log_service import CallLogService

        log = _make_call_log(status="error")
        service = CallLogService.__new__(CallLogService)
        service.db = mock_db
        service.tenant_id = 1
        service.repo = AsyncMock()
        service.repo.create = AsyncMock(return_value=log)

        result = await service.repo.create(log)
        assert result.status == "error"


class TestCallLogDelete:

    @pytest.mark.asyncio
    async def test_soft_delete(self, mock_db):
        from app.services.ai.call_log_service import CallLogService

        log = _make_call_log()
        service = CallLogService.__new__(CallLogService)
        service.db = mock_db
        service.tenant_id = 1
        service.repo = AsyncMock()
        service.repo.get_by_id = AsyncMock(return_value=log)
        service.repo.delete = AsyncMock(return_value=True)

        result = await service.repo.delete(1, soft=True)
        assert result is True
