"""Tenant analytics service tests / 租户侧 AI 分析服务测试。"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest


def _result_with_all(rows):
    result = MagicMock()
    result.all.return_value = rows
    return result


class TestTenantAnalyticsDelegation:
    @pytest.mark.asyncio
    async def test_get_call_trend_delegates_to_admin_service_with_tenant_id(
        self, mock_db
    ):
        from app.services.ai.tenant_analytics_service import TenantAnalyticsService

        service = TenantAnalyticsService.__new__(TenantAnalyticsService)
        service.db = mock_db
        service.tenant_id = 9
        service._admin_svc = MagicMock()
        service._admin_svc.get_call_trend = AsyncMock(
            return_value=[{"date": "2026-04-01"}]
        )

        result = await service.get_call_trend()

        assert result == [{"date": "2026-04-01"}]
        service._admin_svc.get_call_trend.assert_awaited_once_with(None, None, 9)

    @pytest.mark.asyncio
    async def test_get_model_distribution_returns_empty_list_when_admin_service_is_empty(
        self, mock_db
    ):
        from app.services.ai.tenant_analytics_service import TenantAnalyticsService

        service = TenantAnalyticsService.__new__(TenantAnalyticsService)
        service.db = mock_db
        service.tenant_id = 9
        service._admin_svc = MagicMock()
        service._admin_svc.get_model_distribution = AsyncMock(return_value=[])

        result = await service.get_model_distribution()

        assert result == []
        service._admin_svc.get_model_distribution.assert_awaited_once_with(
            None, None, 9
        )


class TestTenantAnalyticsTransforms:
    @pytest.mark.asyncio
    async def test_get_cost_trend_projects_date_cost_and_calls(self, mock_db):
        from app.services.ai.tenant_analytics_service import TenantAnalyticsService

        service = TenantAnalyticsService.__new__(TenantAnalyticsService)
        service.db = mock_db
        service.tenant_id = 3
        service.get_call_trend = AsyncMock(
            return_value=[
                {"date": "2026-04-01", "cost": 1.2, "calls": 4, "tokens": 100},
            ]
        )

        result = await service.get_cost_trend()

        assert result == [{"date": "2026-04-01", "cost": 1.2, "calls": 4}]

    @pytest.mark.asyncio
    async def test_get_cost_trend_returns_empty_when_no_call_trend(self, mock_db):
        from app.services.ai.tenant_analytics_service import TenantAnalyticsService

        service = TenantAnalyticsService.__new__(TenantAnalyticsService)
        service.db = mock_db
        service.tenant_id = 3
        service.get_call_trend = AsyncMock(return_value=[])

        result = await service.get_cost_trend()

        assert result == []


class TestTenantAgentRanking:
    @pytest.mark.asyncio
    async def test_get_agent_ranking_joins_agent_names(self, mock_db):
        from app.services.ai.tenant_analytics_service import TenantAnalyticsService

        service = TenantAnalyticsService.__new__(TenantAnalyticsService)
        service.db = mock_db
        service.tenant_id = 5

        mock_db.execute = AsyncMock(
            side_effect=[
                _result_with_all(
                    [
                        SimpleNamespace(agent_id=1, calls=7),
                        SimpleNamespace(agent_id=2, calls=3),
                    ]
                ),
                _result_with_all(
                    [
                        SimpleNamespace(id=1, name="Agent One"),
                        SimpleNamespace(id=2, name="Agent Two"),
                    ]
                ),
            ]
        )

        ranking = await service.get_agent_ranking(top_n=2)

        assert ranking == [
            {
                "agent_id": 1,
                "agent_name": "Agent One",
                "calls": 7,
                "tokens": 0,
                "cost": 0.0,
            },
            {
                "agent_id": 2,
                "agent_name": "Agent Two",
                "calls": 3,
                "tokens": 0,
                "cost": 0.0,
            },
        ]

    @pytest.mark.asyncio
    async def test_get_agent_ranking_returns_empty_when_no_usage_rows(self, mock_db):
        from app.services.ai.tenant_analytics_service import TenantAnalyticsService

        service = TenantAnalyticsService.__new__(TenantAnalyticsService)
        service.db = mock_db
        service.tenant_id = 5
        mock_db.execute = AsyncMock(return_value=_result_with_all([]))

        ranking = await service.get_agent_ranking()

        assert ranking == []
        mock_db.execute.assert_awaited_once()
