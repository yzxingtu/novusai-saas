"""TenantDashboardService tests / 企业端仪表盘统计服务测试。"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

from tests.services.conftest import (
    make_mock_model,
    make_scalar_result,
    make_scalars_result,
)


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

    def test_visible_kb_condition_requires_assignment_for_partial_scopes(self):
        from app.models.ai.knowledge_base import KnowledgeBase
        from app.services.system.dashboard_service import _visible_kb_condition

        stmt = select(KnowledgeBase.id).where(_visible_kb_condition(7))
        sql = str(stmt.compile(compile_kwargs={"literal_binds": True}))

        assert "knowledge_bases.owner_tenant_id = 7" in sql
        assert "knowledge_bases.scope = 'all_tenants'" in sql
        assert "'selected_tenants'" in sql
        assert "'admin_and_selected_tenants'" in sql
        assert "resource_tenant_assignments.resource_type = 'knowledge_base'" in sql
        assert "knowledge_bases.scope != 'admin_only'" not in sql

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

    @pytest.mark.asyncio
    async def test_get_recent_activities_enriches_tenant_actor_identity(
        self,
        mock_db,
        monkeypatch,
    ):
        import app.services.system.dashboard_service as dashboard_service

        log = make_mock_model(
            action="query",
            created_at=datetime(2026, 4, 5, 11, 16, 26, tzinfo=timezone.utc),
            duration_ms=12,
            id=88,
            ip="10.0.0.9",
            method="GET",
            module="tenant_user",
            nickname=None,
            path="/tenant/system/users",
            resource="tenant_user:list",
            status_code=200,
            tenant_id=7,
            user_id=33,
            user_type="tenant_user",
            username="tenant_user_a",
        )
        mock_db.execute.return_value = make_scalars_result([log])
        load_identity_meta = AsyncMock(
            return_value={
                ("tenant_user", 33): {
                    "avatar": "avatars/user-33.png",
                    "display_name": "业务专员",
                    "display_role_name": "销售",
                    "is_active": True,
                    "is_leader": False,
                    "is_owner": False,
                    "nickname": "业务专员",
                    "org_node_id": 12,
                    "org_node_name": "华东一区",
                    "role_name": "销售",
                    "user_type": "tenant_user",
                    "username": "tenant_user_a",
                }
            }
        )
        monkeypatch.setattr(
            dashboard_service,
            "_load_operation_log_identity_meta_map",
            load_identity_meta,
        )

        service = dashboard_service.TenantDashboardService(mock_db, tenant_id=7)

        result = await service.get_recent_activities(limit=5)

        assert result == [
            {
                "action": "query",
                "avatar": "avatars/user-33.png",
                "created_at": "2026-04-05T11:16:26+00:00",
                "display_name": "业务专员",
                "display_role_name": "销售",
                "duration_ms": 12,
                "id": 88,
                "ip": "10.0.0.9",
                "is_active": True,
                "is_leader": False,
                "is_owner": False,
                "method": "GET",
                "module": "tenant_user",
                "nickname": "业务专员",
                "org_node_id": 12,
                "org_node_name": "华东一区",
                "path": "/tenant/system/users",
                "resource": "tenant_user:list",
                "role_name": "销售",
                "status_code": 200,
                "user_id": 33,
                "user_type": "tenant_user",
                "username": "tenant_user_a",
            }
        ]
        load_identity_meta.assert_awaited_once_with(
            mock_db,
            {("tenant_user", 33)},
            tenant_id=7,
        )
