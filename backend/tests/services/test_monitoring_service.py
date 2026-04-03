"""Monitoring service unit tests / AI 监控服务单元测试。"""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.schemas.ai.monitoring import MonitoringActorInfo
from app.schemas.common.query import QuerySpec


def _utc_dt() -> datetime:
    return datetime(2026, 4, 3, 12, 0, tzinfo=timezone.utc)


def _result_with_one(row):
    result = MagicMock()
    result.one.return_value = row
    return result


def _result_with_all(rows):
    result = MagicMock()
    result.all.return_value = rows
    return result


class TestMonitoringScope:

    def test_scope_builders_return_expected_flags(self):
        from app.services.ai.monitoring_service import MonitoringService

        admin_scope = MonitoringService.admin_scope()
        tenant_scope = MonitoringService.tenant_scope(7)

        assert admin_scope.is_admin is True
        assert admin_scope.is_tenant is False
        assert admin_scope.tenant_id is None
        assert tenant_scope.is_admin is False
        assert tenant_scope.is_tenant is True
        assert tenant_scope.tenant_id == 7


class TestUsageDashboard:

    @pytest.mark.asyncio
    async def test_get_usage_dashboard_builds_admin_breakdowns(self, mock_db):
        from app.configs.service import PLATFORM_TENANT_ID
        from app.services.ai.monitoring_service import MonitoringService

        service = MonitoringService.__new__(MonitoringService)
        service.db = mock_db
        service._load_actor_map = AsyncMock(
            return_value={
                ("tenant_user", 7): MonitoringActorInfo(
                    id=7,
                    type="tenant_user",
                    display_name="Alice",
                )
            }
        )
        service._load_tenant_names = AsyncMock(return_value={})

        mock_db.execute = AsyncMock(
            side_effect=[
                _result_with_one(
                    SimpleNamespace(
                        total_calls=10,
                        total_tokens=1000,
                        input_tokens=400,
                        output_tokens=600,
                        total_cost=1.5,
                        success_calls=9,
                        failed_calls=1,
                    )
                ),
                _result_with_all(
                    [
                        SimpleNamespace(
                            date="2026-04-01",
                            call_count=4,
                            input_tokens=100,
                            output_tokens=200,
                            total_tokens=300,
                            total_cost=0.6,
                            success_calls=3,
                            failed_calls=1,
                        )
                    ]
                ),
                _result_with_all(
                    [
                        SimpleNamespace(
                            key=8,
                            label="gpt-4o",
                            call_count=5,
                            total_tokens=500,
                            total_cost=0.8,
                            success_calls=5,
                            failed_calls=0,
                        )
                    ]
                ),
                _result_with_all(
                    [
                        SimpleNamespace(
                            key="chat",
                            label="chat",
                            call_count=6,
                            total_tokens=600,
                            total_cost=0.7,
                            success_calls=5,
                            failed_calls=1,
                        )
                    ]
                ),
                _result_with_all(
                    [
                        SimpleNamespace(
                            key=10,
                            label="Support Agent",
                            call_count=3,
                            total_tokens=450,
                            total_cost=0.5,
                            success_calls=2,
                            failed_calls=1,
                        )
                    ]
                ),
                _result_with_all(
                    [
                        SimpleNamespace(
                            actor_type="tenant_user",
                            actor_id=7,
                            call_count=4,
                            total_tokens=320,
                            total_cost=0.4,
                            success_calls=4,
                            failed_calls=0,
                        )
                    ]
                ),
                _result_with_all(
                    [
                        SimpleNamespace(
                            key=PLATFORM_TENANT_ID,
                            label=None,
                            call_count=2,
                            total_tokens=180,
                            total_cost=0.2,
                            success_calls=2,
                            failed_calls=0,
                        )
                    ]
                ),
            ]
        )

        dashboard = await service.get_usage_dashboard(MonitoringService.admin_scope())

        assert dashboard.scope == "admin"
        assert dashboard.summary.total_calls == 10
        assert dashboard.summary.success_rate == 90.0
        assert dashboard.daily_stats[0].total_tokens == 300
        assert dashboard.model_stats[0].label == "gpt-4o"
        assert dashboard.access_channel_stats[0].key == "chat"
        assert dashboard.top_agents[0].label == "Support Agent"
        assert dashboard.top_users[0].label == "Alice"
        assert dashboard.top_tenants[0].label == "平台管理端"

    @pytest.mark.asyncio
    async def test_get_usage_dashboard_loads_tenant_name_for_tenant_scope(self, mock_db):
        from app.services.ai.monitoring_service import MonitoringService

        service = MonitoringService.__new__(MonitoringService)
        service.db = mock_db
        service._load_actor_map = AsyncMock(return_value={})
        service._load_tenant_names = AsyncMock(return_value={11: "Tenant A"})

        mock_db.execute = AsyncMock(
            side_effect=[
                _result_with_one(
                    SimpleNamespace(
                        total_calls=0,
                        total_tokens=0,
                        input_tokens=0,
                        output_tokens=0,
                        total_cost=0,
                        success_calls=0,
                        failed_calls=0,
                    )
                ),
                _result_with_all([]),
                _result_with_all([]),
                _result_with_all([]),
                _result_with_all([]),
                _result_with_all([]),
            ]
        )

        dashboard = await service.get_usage_dashboard(MonitoringService.tenant_scope(11))

        assert dashboard.scope == "tenant"
        assert dashboard.tenant_id == 11
        assert dashboard.tenant_name == "Tenant A"
        assert dashboard.summary.success_rate == 0.0
        assert dashboard.top_tenants == []


class TestConversationQueries:

    @pytest.mark.asyncio
    async def test_list_conversations_uses_tenant_service_and_enriches_usage(
        self, mock_db
    ):
        from app.services.ai.monitoring_service import MonitoringService

        now = _utc_dt()
        conversation = SimpleNamespace(
            id=1,
            tenant_id=11,
            agent_id=5,
            agent=SimpleNamespace(name="Helper", avatar="helper.png"),
            owner_type="tenant_user",
            user_id=7,
            title="Demo",
            status="active",
            message_count=2,
            token_count=30,
            cost=0.1,
            created_at=now,
            updated_at=now,
        )
        conversation_service = MagicMock()
        conversation_service.query_list = AsyncMock(return_value=([conversation], 1))

        service = MonitoringService.__new__(MonitoringService)
        service.db = mock_db
        service._load_conversation_usage_map = AsyncMock(
            return_value={
                1: {
                    "call_count": 4,
                    "total_tokens": 120,
                    "total_cost": 0.9,
                    "last_call_at": now,
                }
            }
        )
        service._load_tenant_names = AsyncMock(return_value={11: "Tenant A"})
        service._load_actor_map = AsyncMock(
            return_value={
                ("tenant_user", 7): MonitoringActorInfo(
                    id=7,
                    type="tenant_user",
                    display_name="Alice",
                )
            }
        )

        with patch(
            "app.services.ai.monitoring_service.ConversationService",
            return_value=conversation_service,
        ):
            items, total = await service.list_conversations(
                MonitoringService.tenant_scope(11),
                QuerySpec(),
            )

        assert total == 1
        assert items[0].tenant_name == "Tenant A"
        assert items[0].actor.display_name == "Alice"
        assert items[0].call_count == 4
        assert items[0].total_tokens == 120
        assert items[0].total_cost == 0.9

    @pytest.mark.asyncio
    async def test_list_conversations_uses_admin_repository_for_admin_scope(
        self, mock_db
    ):
        from app.services.ai.monitoring_service import MonitoringService

        now = _utc_dt()
        repo = MagicMock()
        repo.query_list = AsyncMock(
            return_value=(
                [
                    SimpleNamespace(
                        id=2,
                        tenant_id=0,
                        agent_id=None,
                        agent=None,
                        owner_type=None,
                        user_id=None,
                        title="Platform",
                        status="done",
                        message_count=0,
                        token_count=0,
                        cost=0,
                        created_at=now,
                        updated_at=now,
                    )
                ],
                1,
            )
        )

        service = MonitoringService.__new__(MonitoringService)
        service.db = mock_db
        service._load_conversation_usage_map = AsyncMock(return_value={})
        service._load_tenant_names = AsyncMock(return_value={})
        service._load_actor_map = AsyncMock(return_value={})

        with patch(
            "app.services.ai.monitoring_service.AdminAgentConversationRepository",
            return_value=repo,
        ):
            items, total = await service.list_conversations(
                MonitoringService.admin_scope(),
                QuerySpec(),
            )

        assert total == 1
        assert items[0].id == 2
        repo.query_list.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_conversation_detail_returns_tenant_detail_with_trace(
        self, mock_db
    ):
        from app.services.ai.monitoring_service import MonitoringService

        now = _utc_dt()
        conversation = SimpleNamespace(
            id=5,
            tenant_id=11,
            agent_id=9,
            owner_type="tenant_user",
            user_id=7,
            title="Thread",
            status="active",
            created_at=now,
            updated_at=now,
        )
        conversation_service = MagicMock()
        conversation_service.get_by_id = AsyncMock(return_value=conversation)
        conversation_service.get_conversation_detail = AsyncMock(
            return_value={
                "agent_name": "Writer",
                "agent_avatar": "writer.png",
                "message_count": 3,
                "token_count": 80,
                "cost": 0.4,
                "metadata": {"topic": "demo"},
                "message_list": [{"role": "user", "content": "hello"}],
            }
        )

        service = MonitoringService.__new__(MonitoringService)
        service.db = mock_db
        service._load_conversation_usage_map = AsyncMock(
            return_value={
                5: {
                    "call_count": 4,
                    "total_tokens": 120,
                    "total_cost": 0.9,
                    "last_call_at": now,
                }
            }
        )
        service._load_actor_map = AsyncMock(
            return_value={
                ("tenant_user", 7): MonitoringActorInfo(
                    id=7,
                    type="tenant_user",
                    display_name="Alice",
                )
            }
        )
        service._load_tenant_names = AsyncMock(return_value={11: "Tenant A"})
        mock_db.execute = AsyncMock(
            return_value=_result_with_all(
                [
                    SimpleNamespace(
                        id=99,
                        created_at=now,
                        status="success",
                        request_type="chat",
                        model_name="gpt-4o",
                        provider_name="OpenAI",
                        total_tokens=50,
                        cost=0.2,
                        latency_ms=120,
                        error_message=None,
                        request_metadata={"response": {"usage_mode": "stream"}},
                    )
                ]
            )
        )

        with patch(
            "app.services.ai.monitoring_service.ConversationService",
            return_value=conversation_service,
        ):
            detail = await service.get_conversation_detail(
                MonitoringService.tenant_scope(11),
                conversation_id=5,
            )

        assert detail.id == 5
        assert detail.tenant_name == "Tenant A"
        assert detail.actor.display_name == "Alice"
        assert detail.total_tokens == 120
        assert detail.total_cost == 0.9
        assert detail.call_count == 4
        assert detail.call_trace[0].usage_mode == "stream"

    @pytest.mark.asyncio
    async def test_get_conversation_detail_raises_when_tenant_conversation_missing(
        self, mock_db
    ):
        from app.exceptions import NotFoundException
        from app.services.ai.monitoring_service import MonitoringService

        conversation_service = MagicMock()
        conversation_service.get_by_id = AsyncMock(return_value=None)

        service = MonitoringService.__new__(MonitoringService)
        service.db = mock_db

        with patch(
            "app.services.ai.monitoring_service.ConversationService",
            return_value=conversation_service,
        ), pytest.raises(NotFoundException, match="conversation not found"):
            await service.get_conversation_detail(
                MonitoringService.tenant_scope(11),
                conversation_id=5,
            )
