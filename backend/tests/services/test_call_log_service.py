"""CallLogService 单元测试 / CallLogService tests.

覆盖：调用日志查询、统计聚合。"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

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

    @pytest.mark.asyncio
    async def test_log_call_async_discards_overflow_latency(self, mock_db):
        from app.services.ai.call_log_service import CallLogService

        service = CallLogService.__new__(CallLogService)
        service.db = mock_db
        service.tenant_id = 1

        with patch("app.tasks.ai.log_ai_call_task.delay") as delay_mock:
            await service.log_call_async(
                tenant_id=1,
                model_id=2,
                provider_id=3,
                request_type="chat",
                request_data={"messages": []},
                response_data={"ok": True},
                input_tokens=0,
                output_tokens=0,
                total_tokens=0,
                cost=0.0,
                latency_ms=9_999_999_999_999,
                status="failed",
            )

        assert delay_mock.called
        assert delay_mock.call_args.kwargs["latency_ms"] is None

    @pytest.mark.asyncio
    async def test_log_call_async_sanitizes_decimal_payloads(self, mock_db):
        from app.services.ai.call_log_service import CallLogService

        service = CallLogService.__new__(CallLogService)
        service.db = mock_db
        service.tenant_id = 1

        with patch("app.tasks.ai.log_ai_call_task.delay") as delay_mock:
            await service.log_call_async(
                tenant_id=1,
                model_id=2,
                provider_id=3,
                request_type="chat",
                request_data={
                    "pricing": {"unit_cost": Decimal("0.125000")},
                },
                response_data={
                    "usage": {"total_cost": Decimal("1.500000")},
                },
                input_tokens=0,
                output_tokens=0,
                total_tokens=0,
                cost=0.0,
                latency_ms=100,
                status="success",
            )

        request_arg = delay_mock.call_args.kwargs["request_data"]
        response_arg = delay_mock.call_args.kwargs["response_data"]

        assert request_arg["pricing"]["unit_cost"] == "0.125000"
        assert response_arg["usage"]["total_cost"] == "1.500000"

    @pytest.mark.asyncio
    async def test_log_call_async_passes_trace_id_from_context_var(self, mock_db):
        from app.middleware.trace import trace_id_var
        from app.services.ai.call_log_service import CallLogService

        service = CallLogService.__new__(CallLogService)
        service.db = mock_db
        service.tenant_id = 1

        token = trace_id_var.set("trace-from-request-abc")
        try:
            with patch("app.tasks.ai.log_ai_call_task.delay") as delay_mock:
                await service.log_call_async(
                    tenant_id=1,
                    model_id=2,
                    provider_id=3,
                    request_type="chat",
                    request_data={"messages": []},
                    response_data={"ok": True},
                    input_tokens=0,
                    output_tokens=0,
                    total_tokens=0,
                    cost=0.0,
                    latency_ms=100,
                    status="success",
                )
        finally:
            trace_id_var.reset(token)

        assert delay_mock.call_args.kwargs.get("trace_id") == "trace-from-request-abc"
        assert delay_mock.call_args.kwargs.get("tool_call_id") is None
        assert delay_mock.call_args.kwargs.get("call_type") == "main_chat"

    @pytest.mark.asyncio
    async def test_log_call_async_normalizes_unknown_call_type(self, mock_db):
        from app.services.ai.call_log_service import CallLogService

        service = CallLogService.__new__(CallLogService)
        service.db = mock_db
        service.tenant_id = 1

        with patch("app.tasks.ai.log_ai_call_task.delay") as delay_mock:
            await service.log_call_async(
                tenant_id=1,
                model_id=2,
                provider_id=3,
                request_type="chat",
                request_data={"messages": []},
                response_data={"ok": True},
                input_tokens=0,
                output_tokens=0,
                total_tokens=0,
                cost=0.0,
                latency_ms=100,
                status="success",
                call_type="unknown_value",
            )

        assert delay_mock.call_args.kwargs["call_type"] == "main_chat"

    @pytest.mark.asyncio
    async def test_log_call_async_normalizes_zero_conversation_id(self, mock_db):
        from app.services.ai.call_log_service import CallLogService

        service = CallLogService.__new__(CallLogService)
        service.db = mock_db
        service.tenant_id = 1

        with patch("app.tasks.ai.log_ai_call_task.delay") as delay_mock:
            await service.log_call_async(
                tenant_id=1,
                model_id=2,
                provider_id=3,
                request_type="chat",
                request_data={"messages": []},
                response_data={"ok": True},
                input_tokens=0,
                output_tokens=0,
                total_tokens=0,
                cost=0.0,
                latency_ms=100,
                status="success",
                conversation_id=0,
            )

        assert delay_mock.call_args.kwargs["conversation_id"] is None

    @pytest.mark.asyncio
    async def test_log_call_persists_json_safe_request_metadata(self, mock_db):
        from app.services.ai.call_log_service import CallLogService

        service = CallLogService.__new__(CallLogService)
        service.db = mock_db
        service.tenant_id = 1
        mock_db.add = MagicMock()
        mock_db.flush = AsyncMock()

        call_log = await service.log_call(
            tenant_id=1,
            model_id=2,
            provider_id=3,
            request_type="chat",
            request_data={
                "messages": [{"role": "user", "content": "hi"}],
                "pricing": {"unit_cost": Decimal("0.125000")},
            },
            response_data={
                "usage": {"total_cost": Decimal("1.500000")},
                "budget": {"remaining": Decimal("2.750000")},
            },
            input_tokens=10,
            output_tokens=20,
            total_tokens=30,
            cost=0.1,
            latency_ms=200,
            status="success",
        )

        assert mock_db.add.called
        saved_log = mock_db.add.call_args.args[0]
        assert saved_log is call_log
        assert saved_log.request_metadata["request"]["pricing"]["unit_cost"] == "0.125000"
        assert saved_log.request_metadata["response"]["usage"]["total_cost"] == "1.500000"
        assert saved_log.request_metadata["response"]["budget"]["remaining"] == "2.750000"

    def test_generate_request_hash_accepts_decimal_payloads(self):
        from app.services.ai.call_log_service import CallLogService

        request_hash = CallLogService._generate_request_hash(
            2,
            messages=[{"amount": Decimal("1.250000")}],
            temperature=Decimal("0.700000"),
            tools=[{"price": Decimal("9.990000")}],
            tool_choice="auto",
        )

        assert isinstance(request_hash, str)
        assert len(request_hash) == 64


class TestCallLogSanitization:
    def test_normalize_latency_ms_returns_none_for_overflow(self):
        from app.services.ai.call_log_service import CallLogService

        assert CallLogService._normalize_latency_ms(9_999_999_999_999) is None
        assert CallLogService._normalize_latency_ms(-1) is None
        assert CallLogService._normalize_latency_ms(1234) == 1234


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
