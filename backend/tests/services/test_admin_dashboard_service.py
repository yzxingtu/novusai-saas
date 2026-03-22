"""AdminDashboardService tests / 平台端仪表盘服务测试。"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest


class TestAdminDashboardService:

    @pytest.mark.asyncio
    async def test_get_overview_aggregates_service_sections(self, mock_db):
        from app.services.system.dashboard_service import AdminDashboardService

        service = AdminDashboardService.__new__(AdminDashboardService)
        service.db = mock_db
        service.get_stats = AsyncMock(return_value={"total_tenants": 3})
        service.get_system_health = AsyncMock(return_value={"status": "healthy"})
        service.get_ai_overview = AsyncMock(return_value={"today_calls": 7})
        service.get_storage_overview = AsyncMock(return_value={"total_files": 14})
        service.get_plugin_overview = AsyncMock(return_value={"enabled": 5})
        service.get_tenant_growth = AsyncMock(return_value=[{"date": "2026-03-22", "count": 2}])
        service.get_recent_activities = AsyncMock(return_value=[{"id": 1}])

        result = await service.get_overview(activity_limit=8, growth_days=21)

        assert result["stats"] == {"total_tenants": 3}
        assert result["health"] == {"status": "healthy"}
        assert result["ai_overview"] == {"today_calls": 7}
        assert result["storage_overview"] == {"total_files": 14}
        assert result["plugin_overview"] == {"enabled": 5}
        assert result["tenant_growth"] == [{"date": "2026-03-22", "count": 2}]
        assert result["recent_activities"] == [{"id": 1}]
        assert result["generated_at"]

        service.get_tenant_growth.assert_awaited_once_with(days=21)
        service.get_recent_activities.assert_awaited_once_with(limit=8)
