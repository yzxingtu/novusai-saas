"""AICallLogRepository unit tests."""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from tests.services.conftest import make_mock_model, make_row_result


class TestEnrichLogs:

    @pytest.mark.asyncio
    async def test_enrich_detail_unpacks_request_and_response_payloads(self, mock_db):
        from app.repositories.ai.call_log_repository import AICallLogRepository

        repo = AICallLogRepository(mock_db)
        log = make_mock_model(
            id=1,
            tenant_id=0,
            model_id=10,
            provider_id=20,
            routed_model_id=30,
            route_reason="router_override",
            request_type="chat",
            input_tokens=1,
            output_tokens=2,
            total_tokens=3,
            cost=0.01,
            latency_ms=120,
            status="success",
            error_message=None,
            user_id=None,
            user_type=None,
            created_at=datetime(2026, 3, 20, 12, 0, 0),
            updated_at=None,
            deleted_at=None,
            request_metadata={
                "request": {"messages": ["hi"]},
                "response": {"model": "deepseek"},
            },
        )

        model_rows = [
            SimpleNamespace(id=10, name="GPT-5.4 XHigh"),
            SimpleNamespace(id=30, name="DeepSeek Routed"),
        ]
        provider_rows = [
            SimpleNamespace(id=20, name="OpenAI Compatible", icon=None),
        ]
        mock_db.execute.side_effect = [
            MagicMock(all=MagicMock(return_value=model_rows)),
            MagicMock(all=MagicMock(return_value=provider_rows)),
        ]

        result = await repo.enrich_logs_to_dicts(
            [log],
            include_tenant_names=False,
            include_caller_names=False,
            include_payload=True,
        )

        assert result[0]["model_name"] == "GPT-5.4 XHigh"
        assert result[0]["routed_model_name"] == "DeepSeek Routed"
        assert result[0]["request_data"] == {"messages": ["hi"]}
        assert result[0]["response_data"] == {"model": "deepseek"}
        assert "request_metadata" not in result[0]


class TestTenantZeroFilter:

    @pytest.mark.asyncio
    async def test_overall_summary_with_platform_tenant_zero_keeps_filter(self, mock_db):
        from app.repositories.ai.call_log_repository import AICallLogRepository

        repo = AICallLogRepository(mock_db)
        mock_db.execute.return_value = make_row_result({
            "total_calls": 0,
            "total_tokens": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "total_cost": 0,
            "avg_latency": 0,
            "success_calls": 0,
            "failed_calls": 0,
        })

        await repo.get_overall_summary(tenant_id=0)

        stmt = mock_db.execute.await_args.args[0]
        assert "ai_call_logs.tenant_id" in str(stmt)
