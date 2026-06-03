"""AdminDashboardService tests / 平台端仪表盘服务测试。"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from tests.services.conftest import make_mock_model, make_scalars_result


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
        service.get_tenant_growth = AsyncMock(
            return_value=[{"date": "2026-03-22", "count": 2}]
        )
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

    @pytest.mark.asyncio
    async def test_get_recent_activities_enriches_actor_identity(
        self, mock_db, monkeypatch
    ):
        import app.services.system.dashboard_service as dashboard_service

        log = make_mock_model(
            action="update",
            created_at=datetime(2026, 4, 5, 11, 16, 26, tzinfo=timezone.utc),
            duration_ms=24,
            id=101,
            ip="127.0.0.1",
            method="PATCH",
            module="admin_user",
            nickname="旧昵称",
            path="/admin/system/admins/9",
            resource="admin_user:update",
            status_code=200,
            user_id=9,
            user_type="admin",
            username="legacy_admin",
        )
        mock_db.execute.return_value = make_scalars_result([log])
        load_identity_meta = AsyncMock(
            return_value={
                ("admin", 9): {
                    "avatar": "avatars/admin-9.png",
                    "display_name": "平台管理员",
                    "display_role_name": None,
                    "is_active": True,
                    "is_leader": True,
                    "is_owner": False,
                    "nickname": "平台管理员",
                    "org_node_id": 7,
                    "org_node_name": "平台管理组",
                    "role_name": "平台管理组",
                    "user_type": "admin",
                    "username": "admin_root",
                }
            }
        )
        monkeypatch.setattr(
            dashboard_service,
            "_load_operation_log_identity_meta_map",
            load_identity_meta,
        )

        service = dashboard_service.AdminDashboardService(mock_db)

        result = await service.get_recent_activities(limit=6)

        assert result == [
            {
                "action": "update",
                "avatar": "avatars/admin-9.png",
                "created_at": "2026-04-05T11:16:26+00:00",
                "display_name": "平台管理员",
                "display_role_name": None,
                "duration_ms": 24,
                "id": 101,
                "ip": "127.0.0.1",
                "is_active": True,
                "is_leader": True,
                "is_owner": False,
                "method": "PATCH",
                "module": "admin_user",
                "nickname": "平台管理员",
                "org_node_id": 7,
                "org_node_name": "平台管理组",
                "path": "/admin/system/admins/9",
                "resource": "admin_user:update",
                "role_name": "平台管理组",
                "status_code": 200,
                "user_id": 9,
                "user_type": "admin",
                "username": "admin_root",
            }
        ]
        load_identity_meta.assert_awaited_once_with(mock_db, {("admin", 9)})
