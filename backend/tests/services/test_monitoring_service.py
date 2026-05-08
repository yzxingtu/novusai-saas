"""
Test type: behavioral
Scope: AI monitoring read-model projection, diagnostics normalization, and scrubbed
invalid runtime metadata metadata.
Mock strategy: DB/service edges are mocked; projector and diagnostic normalization
logic run through the real implementation.
"""

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


class TestCallTraceDiagnostics:
    def test_extract_call_trace_diagnostics_prefers_turn_record_fields_and_infers_partial(
        self,
    ):
        from app.services.ai.monitoring_service import MonitoringService

        diagnostics = MonitoringService._extract_call_trace_diagnostics(
            {
                "turn_diagnostics": {
                    "partial": True,
                    "completion_reason": "elapsed_budget_exceeded",
                    "turn_record": {
                        "execution_path": "deep",
                        "candidate_tool_names": ["get_current_weather"],
                        "retry_events": [
                            {
                                "action": "retry_intent",
                                "target_intent_id": "intent-1",
                            }
                        ],
                        "partial_exit_reason": "elapsed_budget_exceeded",
                        "failure_kind": "budget_exit",
                        "provider_events": [
                            {
                                "kind": "budget_exit",
                                "reason": "elapsed_budget_exceeded",
                            }
                        ],
                        "budget_status": "exited",
                        "budget_exit_reason": "elapsed_budget_exceeded",
                    },
                }
            }
        )

        assert diagnostics["turn_outcome"] == "partial"
        assert diagnostics["termination_reason"] == "elapsed_budget_exceeded"
        assert diagnostics["execution_path"] == "deep"
        assert diagnostics["candidate_tool_names"] == ["get_current_weather"]
        assert diagnostics["retry_events"] == [
            {
                "action": "retry_intent",
                "target_intent_id": "intent-1",
                "retry_family": None,
                "allowed_tool_names": [],
                "completed_intent_ids": [],
                "unfinished_intent_ids": [],
                "reason": None,
                "provider_failure_kind": None,
                "metadata": {},
            }
        ]
        assert diagnostics["partial_exit_reason"] == "elapsed_budget_exceeded"
        assert diagnostics["failure_kind"] == "budget_exit"
        assert diagnostics["provider_events"] == [
            {
                "kind": "budget_exit",
                "reason": "elapsed_budget_exceeded",
            }
        ]
        assert diagnostics["budget_status"] == "exited"
        assert diagnostics["budget_exit_reason"] == "elapsed_budget_exceeded"

    def test_extract_call_trace_diagnostics_scrubs_invalid_runtime_continuation(
        self,
    ):
        from app.services.ai.monitoring_service import MonitoringService

        diagnostics = MonitoringService._extract_call_trace_diagnostics(
            {
                "turn_diagnostics": {
                    "tool_planner": {
                        "intent": "page_summary",
                        "family": "page_ops",
                    },
                    "active_intent_id": "intent-1",
                    "continuation_source": "page_ops",
                    "conversation_outcome": "failed",
                    "assistant_claimed_tool_call_without_tool_event": True,
                    "turn_record": {
                        "candidate_tool_names": ["ui_get_snapshot"],
                        "metadata": {
                            "turn_diagnostics": {
                                "contract_breach_type": (
                                    "assistant_claimed_tool_call_without_tool_event"
                                )
                            }
                        },
                    },
                }
            }
        )

        assert diagnostics["active_intent_id"] == "intent-1"
        assert diagnostics["tool_planner"] is None
        assert diagnostics["continuation_source"] is None
        assert diagnostics["conversation_outcome"] == "failed"
        assert diagnostics["candidate_tool_names"] == []
        assert diagnostics["contract_breach_type"] == (
            "assistant_claimed_tool_call_without_tool_event"
        )
        assert diagnostics["assistant_claimed_tool_call_without_tool_event"] is True


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

    @pytest.mark.asyncio
    async def test_load_actor_map_includes_identity_rich_fields(self, mock_db):
        from app.services.ai.monitoring_service import MonitoringService

        service = MonitoringService.__new__(MonitoringService)
        service.db = mock_db
        mock_db.execute = AsyncMock(
            return_value=_result_with_all(
                [
                    SimpleNamespace(
                        id=1,
                        username="root",
                        nickname="Root",
                        avatar="1",
                        org_node_id=3,
                        is_active=True,
                        is_super=True,
                        role_name="Super",
                        org_node_name="HQ",
                        org_leader_id=1,
                    )
                ]
            )
        )

        actor_map = await service._load_actor_map({("platform_admin", 1)})
        actor = actor_map[("platform_admin", 1)]

        assert actor.display_name == "Root"
        assert actor.org_node_id == 3
        assert actor.org_node_name == "HQ"
        assert actor.role_name == "Super"
        assert actor.display_role_name == "Super"
        assert actor.is_active is True
        assert actor.is_owner is True
        assert actor.is_leader is True


class TestUsageDashboard:
    @pytest.mark.asyncio
    async def test_get_usage_dashboard_builds_admin_breakdowns(self, mock_db):
        from app.configs.service import PLATFORM_TENANT_ID
        from app.services.ai.monitoring_service import MonitoringService

        service = MonitoringService.__new__(MonitoringService)
        service.db = mock_db
        service._load_actor_snapshot_map = AsyncMock(
            return_value={
                ("tenant_user", 7): {
                    "user_id": 7,
                    "user_type": "tenant_user",
                    "display_name": "历史 Alice",
                    "username": "alice_old",
                    "nickname": "历史 Alice",
                    "avatar": "snapshot-avatar",
                    "org_node_id": 55,
                    "org_node_name": "历史组织",
                    "role_name": "历史成员",
                    "display_role_name": "历史成员",
                    "is_active": True,
                    "is_owner": False,
                    "is_leader": False,
                }
            }
        )
        service._load_actor_map = AsyncMock(
            return_value={
                ("tenant_user", 7): MonitoringActorInfo(
                    avatar="12",
                    id=7,
                    type="tenant_user",
                    display_name="Alice",
                    nickname="Alice",
                    org_node_name="Sales",
                    role_name="Member",
                    display_role_name="Member",
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
        assert dashboard.top_users[0].label == "历史 Alice"
        assert dashboard.top_users[0].actor is not None
        assert dashboard.top_users[0].actor.avatar == "snapshot-avatar"
        assert dashboard.top_users[0].actor.display_name == "历史 Alice"
        assert dashboard.top_users[0].actor.org_node_name == "历史组织"
        assert dashboard.top_users[0].actor.display_role_name == "历史成员"
        assert dashboard.top_users[0].actor.type == "tenant_user"
        assert dashboard.top_tenants[0].label == "平台管理端"

    @pytest.mark.asyncio
    async def test_get_usage_dashboard_groups_model_usage_by_live_model_identity(
        self,
        mock_db,
    ):
        from app.services.ai.monitoring_service import MonitoringService

        service = MonitoringService.__new__(MonitoringService)
        service.db = mock_db
        service._load_actor_map = AsyncMock(return_value={})
        service._load_actor_snapshot_map = AsyncMock(return_value={})
        service._load_tenant_names = AsyncMock(return_value={})

        mock_db.execute = AsyncMock(
            side_effect=[
                _result_with_one(
                    SimpleNamespace(
                        total_calls=2,
                        total_tokens=300,
                        input_tokens=120,
                        output_tokens=180,
                        total_cost=0.3,
                        success_calls=2,
                        failed_calls=0,
                    )
                ),
                _result_with_all([]),
                _result_with_all(
                    [
                        SimpleNamespace(
                            key=9,
                            label="gpt-5.5-xhigh",
                            call_count=2,
                            total_tokens=300,
                            total_cost=0.3,
                            success_calls=2,
                            failed_calls=0,
                        )
                    ]
                ),
                _result_with_all([]),
                _result_with_all([]),
                _result_with_all([]),
                _result_with_all([]),
            ]
        )

        dashboard = await service.get_usage_dashboard(MonitoringService.admin_scope())

        assert dashboard.model_stats[0].key == "9:gpt-5.5-xhigh"
        assert dashboard.model_stats[0].label == "gpt-5.5-xhigh"
        model_stmt = mock_db.execute.await_args_list[2].args[0]
        model_sql = str(model_stmt)
        assert "ai_models.name" in model_sql
        assert "ai_models.code" in model_sql
        assert "ai_call_logs.model_name_snapshot" not in model_sql

    @pytest.mark.asyncio
    async def test_get_usage_dashboard_loads_tenant_name_for_tenant_scope(
        self, mock_db
    ):
        from app.services.ai.monitoring_service import MonitoringService

        service = MonitoringService.__new__(MonitoringService)
        service.db = mock_db
        service._load_actor_map = AsyncMock(return_value={})
        service._load_actor_snapshot_map = AsyncMock(return_value={})
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

        dashboard = await service.get_usage_dashboard(
            MonitoringService.tenant_scope(11)
        )

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
        service._load_conversation_latest_turn_map = AsyncMock(return_value={})
        service._load_conversation_actor_snapshot_map = AsyncMock(
            return_value={
                1: {
                    "snapshot": {
                        "user_id": 7,
                        "user_type": "tenant_user",
                        "display_name": "历史 Alice",
                        "username": "alice_old",
                        "nickname": "历史 Alice",
                        "avatar": "snapshot-avatar",
                        "org_node_name": "历史组织",
                        "display_role_name": None,
                        "is_active": True,
                        "is_owner": False,
                        "is_leader": False,
                    },
                    "actor_type": "tenant_user",
                    "actor_id": 7,
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

        with patch.object(
            MonitoringService,
            "ConversationService",
            return_value=conversation_service,
        ):
            items, total = await service.list_conversations(
                MonitoringService.tenant_scope(11),
                QuerySpec(),
            )

        assert total == 1
        assert items[0].tenant_name == "Tenant A"
        assert items[0].actor.display_name == "历史 Alice"
        assert items[0].actor.org_node_name == "历史组织"
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
        service._load_conversation_latest_turn_map = AsyncMock(return_value={})
        service._load_tenant_names = AsyncMock(return_value={})
        service._load_conversation_actor_snapshot_map = AsyncMock(return_value={})
        service._load_actor_map = AsyncMock(return_value={})

        with patch.object(
            MonitoringService,
            "AdminAgentConversationRepository",
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
    async def test_conversation_2344_active_lifecycle_exposes_failed_latest_turn_status_in_list(
        self, mock_db
    ):
        """Regression for: BUG-2026-05-06-2344.

        Conversation 2344 kept the lifecycle row active after a provider outage,
        but monitoring must expose the latest terminal turn as failed so the UI
        does not render the row as in-progress.
        """
        from app.services.ai.monitoring_service import MonitoringService

        now = _utc_dt()
        conversation = SimpleNamespace(
            id=2344,
            tenant_id=0,
            agent_id=59,
            agent=SimpleNamespace(name="猫娘智能体", avatar=None),
            owner_type="platform_admin",
            user_id=1,
            title="明天北京该穿什么衣服呢？",
            status="active",
            message_count=2,
            token_count=0,
            cost=0,
            created_at=now,
            updated_at=now,
        )
        repo = MagicMock()
        repo.query_list = AsyncMock(return_value=([conversation], 1))

        service = MonitoringService.__new__(MonitoringService)
        service.db = mock_db
        service._load_conversation_usage_map = AsyncMock(return_value={})
        service._load_tenant_names = AsyncMock(return_value={})
        service._load_conversation_actor_snapshot_map = AsyncMock(return_value={})
        service._load_actor_map = AsyncMock(return_value={})
        mock_db.execute = AsyncMock(
            return_value=_result_with_all(
                [
                    SimpleNamespace(
                        conversation_id=2344,
                        content="Connection error.",
                        message_metadata={
                            "completion_reason": "provider_unavailable",
                            "turn_record": {
                                "turn_outcome": "partial",
                                "conversation_outcome": "failed",
                                "termination_reason": "provider_unavailable",
                                "failure_kind": "provider_unavailable",
                                "protocol_path": "responses",
                                "execution_path": "fast",
                                "final_output_source": "partial_output",
                                "turn_flow": {
                                    "timeline": [
                                        {
                                            "id": "terminal",
                                            "type": "failed",
                                            "status": "error",
                                            "summary": "provider_unavailable",
                                        }
                                    ],
                                    "completion_reason": "provider_unavailable",
                                    "error_surface": {
                                        "message": "Connection error.",
                                        "error_type": "untrusted_final_output_source",
                                    },
                                },
                                "provider_events": [
                                    {
                                        "kind": "provider_unavailable",
                                        "error": "Connection error.",
                                        "protocol_path": "responses",
                                    }
                                ],
                            },
                            "error_surface": {
                                "message": "Connection error.",
                                "error_type": "provider_unavailable",
                            },
                        },
                        tool_calls=None,
                        token_count=0,
                        created_at=now,
                    )
                ]
            )
        )

        with patch.object(
            MonitoringService,
            "AdminAgentConversationRepository",
            return_value=repo,
        ):
            items, total = await service.list_conversations(
                MonitoringService.admin_scope(),
                QuerySpec(),
            )

        assert total == 1
        assert items[0].status == "active"
        assert items[0].lifecycle_status == "active"
        assert items[0].display_status == "failed"
        assert items[0].latest_turn_status == "failed"
        assert items[0].latest_turn_outcome == "partial"
        assert items[0].latest_conversation_outcome == "failed"
        assert items[0].latest_failure_kind == "provider_unavailable"
        assert items[0].latest_termination_reason == "provider_unavailable"
        assert items[0].latest_error_message == "Connection error."
        assert items[0].latest_turn_flow_terminal_status == "error"
        assert items[0].latest_turn_flow_terminal_type == "failed"
        assert items[0].latest_turn_error_type == "untrusted_final_output_source"

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
                "context_diagnostics": {
                    "execution_path": "deep",
                    "failure_kind": "provider_unavailable",
                    "budget_status": "within_budget",
                    "intent_plan": [
                        {
                            "intent_id": "weather-1",
                            "kind": "weather_query",
                            "family": "weather",
                            "status": "completed",
                        }
                    ],
                },
                "last_run_summary": {
                    "execution_path": "deep",
                    "budget_exit_reason": "elapsed_budget_exceeded",
                    "provider_events": [
                        {
                            "kind": "provider_http_5xx",
                            "status_code": 503,
                        }
                    ],
                },
                "metadata": {"topic": "demo"},
                "message_list": [
                    {
                        "role": "assistant",
                        "content": "天气晴朗",
                        "metadata": {
                            "turn_record": {
                                "termination_reason": "completed",
                                "execution_path": "deep",
                                "selected_tool_names": ["get_current_weather"],
                            }
                        },
                    }
                ],
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
        service._load_conversation_actor_snapshot_map = AsyncMock(
            return_value={
                5: {
                    "snapshot": {
                        "user_id": 7,
                        "user_type": "tenant_user",
                        "display_name": "历史 Alice",
                        "username": "alice_old",
                        "nickname": "历史 Alice",
                        "avatar": "snapshot-avatar",
                        "org_node_name": "历史组织",
                        "display_role_name": None,
                        "is_active": True,
                        "is_owner": False,
                        "is_leader": False,
                    },
                    "actor_type": "tenant_user",
                    "actor_id": 7,
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
                        request_metadata={
                            "response": {"usage_mode": "stream"},
                            "turn_diagnostics": {
                                "turn_outcome": "partial",
                                "termination_reason": "elapsed_budget_exceeded",
                                "budget": {
                                    "status": "exited",
                                    "exit_reason": "elapsed_budget_exceeded",
                                },
                                "budget_status": "exited",
                                "budget_exit_reason": "elapsed_budget_exceeded",
                                "failures": {
                                    "failure_kind": "budget_exit",
                                    "provider_events": [
                                        {
                                            "kind": "budget_exit",
                                            "reason": "elapsed_budget_exceeded",
                                        }
                                    ],
                                },
                                "turn_record": {
                                    "execution_path": "deep",
                                    "last_tool_name": "get_current_weather",
                                    "tool_loop_progress": {
                                        "budget_exit_reason": "elapsed_budget_exceeded"
                                    },
                                },
                            },
                        },
                    )
                ]
            )
        )

        with patch.object(
            MonitoringService,
            "ConversationService",
            return_value=conversation_service,
        ):
            detail = await service.get_conversation_detail(
                MonitoringService.tenant_scope(11),
                conversation_id=5,
            )

        assert detail.id == 5
        assert detail.tenant_name == "Tenant A"
        assert detail.actor.display_name == "历史 Alice"
        assert detail.actor.org_node_name == "历史组织"
        assert detail.total_tokens == 120
        assert detail.total_cost == 0.9
        assert detail.call_count == 4
        assert detail.call_trace[0].usage_mode == "stream"
        assert detail.call_trace[0].turn_outcome == "partial"
        assert detail.call_trace[0].execution_path == "deep"
        assert detail.call_trace[0].budget_exit_reason == "elapsed_budget_exceeded"
        assert detail.call_trace[0].failure_kind == "budget_exit"
        assert detail.call_trace[0].last_tool_name == "get_current_weather"
        assert detail.call_trace[0].turn_record == {
            "execution_path": "deep",
            "last_tool_name": "get_current_weather",
            "tool_loop_progress": {"budget_exit_reason": "elapsed_budget_exceeded"},
        }
        assert detail.context_diagnostics == {
            "execution_path": "deep",
            "failure_kind": "provider_unavailable",
            "budget_status": "within_budget",
            "intent_plan": [
                {
                    "intent_id": "weather-1",
                    "kind": "weather_query",
                    "family": "weather",
                    "status": "completed",
                }
            ],
        }
        assert detail.last_run_summary == {
            "execution_path": "deep",
            "budget_exit_reason": "elapsed_budget_exceeded",
            "provider_events": [
                {
                    "kind": "provider_http_5xx",
                    "status_code": 503,
                }
            ],
        }
        assert (
            detail.message_list[0]["turn_flow"]["timeline"][-1]["type"] == "completed"
        )
        assert detail.message_list[0]["turn_flow"]["completion_reason"] == "completed"

    @pytest.mark.asyncio
    async def test_get_conversation_detail_strips_legacy_conversation_metadata(
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
                "message_count": 1,
                "token_count": 20,
                "cost": 0.1,
                "context_diagnostics": {},
                "last_run_summary": {},
                "metadata": {
                    "interaction_mode": "confirm",
                    "interaction_mode_requested": "trusted_auto",
                    "topic": "demo",
                },
                "message_list": [],
            }
        )

        service = MonitoringService.__new__(MonitoringService)
        service.db = mock_db
        service._load_conversation_usage_map = AsyncMock(return_value={})
        service._load_conversation_actor_snapshot_map = AsyncMock(return_value={})
        service._load_actor_map = AsyncMock(return_value={})
        service._load_tenant_names = AsyncMock(return_value={11: "Tenant A"})
        mock_db.execute = AsyncMock(return_value=_result_with_all([]))

        with patch.object(
            MonitoringService,
            "ConversationService",
            return_value=conversation_service,
        ):
            detail = await service.get_conversation_detail(
                MonitoringService.tenant_scope(11),
                conversation_id=5,
            )

        assert detail.metadata == {"topic": "demo"}

    @pytest.mark.asyncio
    async def test_get_conversation_detail_normalizes_provider_failure_after_partial_progress(
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
                "message_count": 1,
                "token_count": 20,
                "cost": 0.1,
                "context_diagnostics": {},
                "last_run_summary": {},
                "metadata": {"topic": "demo"},
                "message_list": [
                    {
                        "role": "assistant",
                        "content": "已输出部分内容",
                        "metadata": {
                            "turn_record": {
                                "turn_outcome": "partial",
                                "termination_reason": "provider_failure_after_partial_progress",
                                "metadata": {
                                    "turn_diagnostics": {
                                        "failures": {
                                            "failure_kind": "provider_http_5xx",
                                        }
                                    }
                                },
                            },
                            "turn_flow": {
                                "timeline": [
                                    {
                                        "id": "answer_assembly",
                                        "type": "answer_assembly",
                                        "status": "completed",
                                        "title": "答案生成",
                                        "summary": "已生成最终答复",
                                    },
                                    {
                                        "id": "terminal",
                                        "type": "completed",
                                        "status": "completed",
                                        "title": "本轮结束",
                                        "summary": "provider_failure_after_partial_progress",
                                    },
                                ],
                                "completion_reason": "provider_failure_after_partial_progress",
                                "interrupted": False,
                                "error_surface": None,
                            },
                        },
                    }
                ],
            }
        )

        service = MonitoringService.__new__(MonitoringService)
        service.db = mock_db
        service._load_conversation_usage_map = AsyncMock(return_value={})
        service._load_conversation_actor_snapshot_map = AsyncMock(return_value={})
        service._load_actor_map = AsyncMock(return_value={})
        service._load_tenant_names = AsyncMock(return_value={11: "Tenant A"})
        mock_db.execute = AsyncMock(return_value=_result_with_all([]))

        with patch.object(
            MonitoringService,
            "ConversationService",
            return_value=conversation_service,
        ):
            detail = await service.get_conversation_detail(
                MonitoringService.tenant_scope(11),
                conversation_id=5,
            )

        turn_flow = detail.message_list[0]["turn_flow"]
        answer_assembly = next(
            stage
            for stage in turn_flow["timeline"]
            if stage["type"] == "answer_assembly"
        )
        assert (
            turn_flow["completion_reason"] == "provider_failure_after_partial_progress"
        )
        assert answer_assembly["status"] == "error"
        assert turn_flow["timeline"][-1]["type"] == "failed"
        assert turn_flow["timeline"][-1]["status"] == "error"
        assert turn_flow["error_surface"]["message"]

    @pytest.mark.asyncio
    async def test_get_conversation_detail_projects_turn_flow_and_strips_legacy_assistant_fields(
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
                "message_count": 1,
                "token_count": 20,
                "cost": 0.1,
                "context_diagnostics": {},
                "last_run_summary": {},
                "metadata": {"topic": "demo"},
                "message_list": [
                    {
                        "role": "assistant",
                        "content": "最终答复",
                        "tool_calls": [
                            {
                                "id": "tc_1",
                                "display_name": "数据查询",
                                "summary": "按今天范围统计调用",
                                "result_link": "/admin/ai/chat",
                            }
                        ],
                        "metadata": {
                            "thinking_content": "先分析上下文。",
                            "rag_sources": [
                                {
                                    "source": "KB",
                                    "chunk_id": 1,
                                    "title": "知识库证据",
                                    "snippet": "命中了相关文档",
                                }
                            ],
                        },
                    }
                ],
            }
        )

        service = MonitoringService.__new__(MonitoringService)
        service.db = mock_db
        service._load_conversation_usage_map = AsyncMock(return_value={})
        service._load_conversation_actor_snapshot_map = AsyncMock(return_value={})
        service._load_actor_map = AsyncMock(return_value={})
        service._load_tenant_names = AsyncMock(return_value={11: "Tenant A"})
        mock_db.execute = AsyncMock(return_value=_result_with_all([]))

        with patch.object(
            MonitoringService,
            "ConversationService",
            return_value=conversation_service,
        ):
            detail = await service.get_conversation_detail(
                MonitoringService.tenant_scope(11),
                conversation_id=5,
            )

        assistant_payload = detail.message_list[0]
        assert "tool_calls" not in assistant_payload
        assert "thinking_content" not in assistant_payload["metadata"]
        assert "rag_sources" not in assistant_payload["metadata"]
        assert (
            assistant_payload["metadata"]["turn_flow"] == assistant_payload["turn_flow"]
        )
        assert any(
            stage["type"] == "thinking"
            for stage in assistant_payload["turn_flow"]["timeline"]
        )
        assert any(
            item["tool_call_id"] == "tc_1"
            for item in assistant_payload["turn_flow"]["evidence"]
        )

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

        with (
            patch.object(
                MonitoringService,
                "ConversationService",
                return_value=conversation_service,
            ),
            pytest.raises(NotFoundException, match="conversation not found"),
        ):
            await service.get_conversation_detail(
                MonitoringService.tenant_scope(11),
                conversation_id=5,
            )


class TestMonitoringFacadeDelegation:
    @pytest.mark.asyncio
    async def test_get_usage_dashboard_delegates_to_usage_query_service(self, mock_db):
        from app.services.ai.monitoring_service import MonitoringService

        service = MonitoringService.__new__(MonitoringService)
        service.db = mock_db
        expected = object()

        with patch(
            "app.services.ai.monitoring_service.MonitoringUsageQueryService"
        ) as query_service_cls:
            query_service = query_service_cls.return_value
            query_service.get_usage_dashboard = AsyncMock(return_value=expected)

            result = await service.get_usage_dashboard(
                MonitoringService.admin_scope(),
                start_date=None,
                end_date=None,
            )

        assert result is expected
        query_service_cls.assert_called_once_with(service)
        query_service.get_usage_dashboard.assert_awaited_once_with(
            MonitoringService.admin_scope(),
            start_date=None,
            end_date=None,
        )

    @pytest.mark.asyncio
    async def test_list_conversations_delegates_to_conversation_query_service(
        self, mock_db
    ):
        from app.services.ai.monitoring_service import MonitoringService

        service = MonitoringService.__new__(MonitoringService)
        service.db = mock_db
        expected = ([], 0)
        spec = QuerySpec()

        with patch(
            "app.services.ai.monitoring_service.MonitoringConversationQueryService"
        ) as query_service_cls:
            query_service = query_service_cls.return_value
            query_service.list_conversations = AsyncMock(return_value=expected)

            result = await service.list_conversations(
                MonitoringService.tenant_scope(11),
                spec,
            )

        assert result == expected
        query_service_cls.assert_called_once_with(service)
        query_service.list_conversations.assert_awaited_once_with(
            MonitoringService.tenant_scope(11),
            spec,
        )

    @pytest.mark.asyncio
    async def test_get_conversation_detail_delegates_to_conversation_query_service(
        self, mock_db
    ):
        from app.services.ai.monitoring_service import MonitoringService

        service = MonitoringService.__new__(MonitoringService)
        service.db = mock_db
        expected = object()

        with patch(
            "app.services.ai.monitoring_service.MonitoringConversationQueryService"
        ) as query_service_cls:
            query_service = query_service_cls.return_value
            query_service.get_conversation_detail = AsyncMock(return_value=expected)

            result = await service.get_conversation_detail(
                MonitoringService.admin_scope(),
                conversation_id=42,
                message_skip=3,
                message_limit=20,
            )

        assert result is expected
        query_service_cls.assert_called_once_with(service)
        query_service.get_conversation_detail.assert_awaited_once_with(
            MonitoringService.admin_scope(),
            42,
            message_skip=3,
            message_limit=20,
        )
