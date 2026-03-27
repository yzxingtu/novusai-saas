"""AICallLogRepository unit tests."""

from __future__ import annotations

from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.schemas.common.query import QuerySpec
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
            model_name_snapshot=None,
            provider_name_snapshot=None,
            agent_name_snapshot=None,
            billing_tenant_name_snapshot=None,
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

    @pytest.mark.asyncio
    async def test_query_usage_stats_includes_platform_internal_usage_bucket(self, mock_db):
        from app.repositories.ai.call_log_repository import AICallLogRepository

        repo = AICallLogRepository(mock_db)
        count_result = MagicMock()
        count_result.scalar.return_value = 1

        rows_result = MagicMock()
        rows_result.mappings.return_value.all.return_value = [{
            "stat_date": date(2026, 3, 27),
            "tenant_id": 0,
            "tenant_name": "平台管理端",
            "model_id": 9,
            "model_name": "gpt-5.4-xhigh",
            "request_type": "chat",
            "input_tokens": 120,
            "output_tokens": 80,
            "total_tokens": 200,
            "call_count": 3,
            "success_count": 3,
            "failed_count": 0,
            "total_cost": 0.42,
            "avg_latency_ms": 1234.5,
            "max_latency_ms": 3000,
        }]

        mock_db.execute.side_effect = [count_result, rows_result]

        items, total = await repo.query_usage_stats(QuerySpec())

        assert total == 1
        assert items[0]["tenant_id"] == 0
        assert items[0]["tenant_name"] == "平台管理端"
        assert items[0]["total_tokens"] == 200

        main_stmt = mock_db.execute.await_args_list[1].args[0]
        main_sql = str(main_stmt)
        assert "coalesce(ai_call_logs.billing_tenant_id" in main_sql
        assert "ai_call_logs.tenant_id = :tenant_id_" in main_sql

    @pytest.mark.asyncio
    async def test_billing_tenant_summary_with_platform_tenant_zero_uses_effective_usage_tenant(self, mock_db):
        from app.repositories.ai.call_log_repository import AICallLogRepository

        repo = AICallLogRepository(mock_db)
        mock_db.execute.side_effect = [
            make_row_result({
                "total_tokens": 200,
                "input_tokens": 120,
                "output_tokens": 80,
                "call_count": 3,
                "total_cost": 0.42,
                "success_count": 3,
                "failed_count": 0,
            }),
            MagicMock(all=MagicMock(return_value=[])),
            MagicMock(all=MagicMock(return_value=[])),
            MagicMock(all=MagicMock(return_value=[])),
        ]

        summary = await repo.get_billing_tenant_usage_summary(tenant_id=0)

        assert summary["total_tokens"] == 200
        first_stmt = mock_db.execute.await_args_list[0].args[0]
        first_sql = str(first_stmt)
        assert "coalesce(ai_call_logs.billing_tenant_id" in first_sql
        assert "ai_call_logs.tenant_id = :tenant_id_" in first_sql
