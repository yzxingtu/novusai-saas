"""
AnalyticsService + TenantAnalyticsService 单元测试

覆盖：调用趋势、模型分布、供应商性能、企业排行、延迟分布、成功率趋势。
"""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock

import pytest

# ── Helpers ──

def _make_trend_rows(days: int = 3):
    """生成 mock 调用趋势数据"""
    rows = []
    for i in range(days):
        row = MagicMock()
        row.date = date(2026, 2, 20 + i)
        row.calls = 10 + i * 5
        row.success = 8 + i * 4
        row.failed = 2 + i
        row.input_tokens = 1000 + i * 500
        row.output_tokens = 500 + i * 200
        rows.append(row)
    return rows


def _make_model_dist_rows():
    rows = []
    for name, calls in [("gpt-4", 50), ("gpt-3.5", 30), ("claude-3", 20)]:
        row = MagicMock()
        row.model_name = name
        row.calls = calls
        rows.append(row)
    return rows


# ── Tests: AnalyticsService ──

class TestCallTrend:

    @pytest.mark.asyncio
    async def test_call_trend_returns_list(self, mock_db):
        from app.services.ai.analytics_service import AnalyticsService

        rows = _make_trend_rows(3)
        result_mock = MagicMock()
        result_mock.all.return_value = rows
        mock_db.execute.return_value = result_mock

        service = AnalyticsService(mock_db)
        result = await service.get_call_trend()

        assert len(result) == 3
        assert result[0]["date"] == "2026-02-20"
        assert result[0]["calls"] == 10

    @pytest.mark.asyncio
    async def test_call_trend_with_date_filter(self, mock_db):
        from app.services.ai.analytics_service import AnalyticsService

        result_mock = MagicMock()
        result_mock.all.return_value = []
        mock_db.execute.return_value = result_mock

        service = AnalyticsService(mock_db)
        result = await service.get_call_trend(
            start_date=date(2026, 2, 1),
            end_date=date(2026, 2, 28),
        )

        assert result == []
        mock_db.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_call_trend_with_tenant_id(self, mock_db):
        from app.services.ai.analytics_service import AnalyticsService

        result_mock = MagicMock()
        result_mock.all.return_value = _make_trend_rows(1)
        mock_db.execute.return_value = result_mock

        service = AnalyticsService(mock_db)
        result = await service.get_call_trend(tenant_id=42)

        assert len(result) == 1


class TestModelDistribution:

    @pytest.mark.asyncio
    async def test_model_distribution_returns_list(self, mock_db):
        from app.services.ai.analytics_service import AnalyticsService

        rows = _make_model_dist_rows()
        result_mock = MagicMock()
        result_mock.all.return_value = rows
        mock_db.execute.return_value = result_mock

        service = AnalyticsService(mock_db)
        result = await service.get_model_distribution()

        assert len(result) == 3
        assert result[0]["calls"] == 50


class TestLatencyDistribution:

    @pytest.mark.asyncio
    async def test_latency_distribution_single_query(self, mock_db):
        from app.services.ai.analytics_service import AnalyticsService

        row = MagicMock()
        row.__getitem__ = lambda _self, idx: [100, 50, 30, 10, 5, 2][idx]
        result_mock = MagicMock()
        result_mock.one.return_value = row
        mock_db.execute.return_value = result_mock

        service = AnalyticsService(mock_db)
        result = await service.get_latency_distribution()

        assert len(result) == 6
        assert result[0]["range"] == "0-200ms"
        assert result[0]["count"] == 100
        assert result[5]["range"] == "5s+"
        assert result[5]["count"] == 2
        # Single query — only called once
        assert mock_db.execute.call_count == 1


class TestSuccessRateTrend:

    @pytest.mark.asyncio
    async def test_success_rate_trend(self, mock_db):
        from app.services.ai.analytics_service import AnalyticsService

        rows = _make_trend_rows(2)
        result_mock = MagicMock()
        result_mock.all.return_value = rows
        mock_db.execute.return_value = result_mock

        service = AnalyticsService(mock_db)
        result = await service.get_success_rate_trend()

        assert len(result) == 2
        assert "rate" in result[0]
        assert "total" in result[0]
        assert "success" in result[0]
        assert "failed" in result[0]


class TestProviderPerformance:

    @pytest.mark.asyncio
    async def test_provider_performance_returns_list(self, mock_db):
        from app.services.ai.analytics_service import AnalyticsService

        rows = []
        for i, _name in enumerate(["OpenAI", "Anthropic"]):
            row = MagicMock()
            row.provider_id = i + 1
            row.calls = 100
            row.success_count = 95
            row.total_tokens = 50000
            row.avg_latency = 500.0
            rows.append(row)

        result_mock = MagicMock()
        result_mock.all.return_value = rows
        mock_db.execute.return_value = result_mock

        service = AnalyticsService(mock_db)
        result = await service.get_provider_performance()

        assert len(result) == 2
        assert result[0]["calls"] == 100


class TestTenantRanking:

    @pytest.mark.asyncio
    async def test_tenant_ranking_returns_list(self, mock_db):
        from app.services.ai.analytics_service import AnalyticsService

        rows = []
        for i in range(5):
            row = MagicMock()
            row.tenant_id = i + 1
            row.calls = 100 - i * 10
            rows.append(row)

        result_mock = MagicMock()
        result_mock.all.return_value = rows
        mock_db.execute.return_value = result_mock

        service = AnalyticsService(mock_db)
        result = await service.get_tenant_ranking()

        assert len(result) == 5
        assert result[0]["calls"] == 100
