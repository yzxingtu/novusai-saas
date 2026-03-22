"""TenantDashboardService tests / 企业端仪表盘统计服务测试。"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from tests.services.conftest import make_scalar_result


class TestTenantDashboardService:

    @pytest.mark.asyncio
    async def test_count_visible_agents_uses_owner_tenant_visibility(self, mock_db):
        from app.services.system.dashboard_service import TenantDashboardService

        mock_db.execute.return_value = make_scalar_result(5)
        service = TenantDashboardService(mock_db, tenant_id=7)

        result = await service._count_visible_agents()

        assert result == 5
        stmt = mock_db.execute.await_args.args[0]
        sql = str(stmt)
        assert "owner_tenant_id" in sql
        assert "agents.tenant_id" not in sql

    @pytest.mark.asyncio
    async def test_count_visible_knowledge_documents_joins_visible_kbs(self, mock_db):
        from app.services.system.dashboard_service import TenantDashboardService

        mock_db.execute.return_value = make_scalar_result(12)
        service = TenantDashboardService(mock_db, tenant_id=7)

        result = await service._count_visible_knowledge_documents()

        assert result == 12
        stmt = mock_db.execute.await_args.args[0]
        sql = str(stmt)
        assert "JOIN knowledge_bases" in sql
        assert "owner_tenant_id" in sql

    @pytest.mark.asyncio
    async def test_get_stats_uses_visible_resource_counters(self, mock_db):
        from app.models.ai.agent_conversation import AgentConversation
        from app.services.system.dashboard_service import TenantDashboardService

        service = TenantDashboardService.__new__(TenantDashboardService)
        service.db = mock_db
        service.tenant_id = 7
        service._count_admins = AsyncMock(side_effect=[3, 2])
        service._get_ai_stats = AsyncMock(
            return_value={
                "total_calls": 11,
                "total_tokens": 22,
                "total_cost": 0.5,
            }
        )
        service._get_storage_used = AsyncMock(return_value=1_048_576)
        service._count_visible_agents = AsyncMock(return_value=5)
        service._count_visible_knowledge_bases = AsyncMock(return_value=4)
        service._count_visible_knowledge_documents = AsyncMock(return_value=12)

        async def _count_tenant_model_side_effect(model, *extra_filters):
            assert model is AgentConversation
            assert extra_filters
            return 9

        service._count_tenant_model = AsyncMock(
            side_effect=_count_tenant_model_side_effect
        )

        result = await service.get_stats()

        assert result["total_users"] == 3
        assert result["active_users"] == 2
        assert result["api_calls"] == 11
        assert result["total_tokens"] == 22
        assert result["total_cost"] == 0.5
        assert result["storage_used_bytes"] == 1_048_576
        assert result["storage_used_mb"] == 1.0
        assert result["total_agents"] == 5
        assert result["total_knowledge_bases"] == 4
        assert result["total_kb_documents"] == 12
        assert result["monthly_conversations"] == 9

        service._count_visible_agents.assert_awaited_once()
        service._count_visible_knowledge_bases.assert_awaited_once()
        service._count_visible_knowledge_documents.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_overview_aggregates_service_sections(self, mock_db):
        from app.services.system.dashboard_service import TenantDashboardService

        service = TenantDashboardService.__new__(TenantDashboardService)
        service.db = mock_db
        service.tenant_id = 7
        service.get_stats = AsyncMock(return_value={"total_users": 3})
        service.get_ai_trend = AsyncMock(return_value=[{"date": "2026-03-22", "calls": 4, "tokens": 20}])
        service.get_storage_detail = AsyncMock(return_value={"total_files": 6})
        service.get_recent_activities = AsyncMock(return_value=[{"id": 9}])

        result = await service.get_overview(activity_limit=6, trend_days=21)

        assert result["stats"] == {"total_users": 3}
        assert result["ai_trend"] == [{"date": "2026-03-22", "calls": 4, "tokens": 20}]
        assert result["storage_detail"] == {"total_files": 6}
        assert result["recent_activities"] == [{"id": 9}]
        assert result["generated_at"]

        service.get_ai_trend.assert_awaited_once_with(days=21)
        service.get_recent_activities.assert_awaited_once_with(limit=6)
