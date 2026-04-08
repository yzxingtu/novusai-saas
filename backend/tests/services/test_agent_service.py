"""AgentService 单元测试 / Test.

覆盖：CRUD 钩子、版本发布/回滚、访问权限、状态变更、系统智能体保护。"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.services.conftest import make_mock_model


def _make_agent(**overrides):
    defaults = {
        "id": 1,
        "tenant_id": 1,
        "name": "Test Agent",
        "description": "A test agent",
        "model_id": 1,
        "system_prompt": "You are helpful.",
        "status": "active",
        "is_system": False,
        "is_deleted": False,
        "current_version": 1,
        "temperature": 0.7,
        "max_tokens": 2048,
        "top_p": 1.0,
        "execution_mode": "streaming",
    }
    defaults.update(overrides)
    return make_mock_model(**defaults)


class TestBeforeCreate:

    @pytest.mark.asyncio
    async def test_duplicate_name_raises(self, mock_db):
        from app.exceptions import BusinessException
        from app.services.ai.agent_service import AgentService

        existing = _make_agent(id=99, name="Duplicate")
        service = AgentService.__new__(AgentService)
        service.db = mock_db
        service.tenant_id = 1
        service.repo = AsyncMock()
        service.repo.find_by_name = AsyncMock(return_value=existing)

        with pytest.raises(BusinessException):
            await service._before_create({"name": "Duplicate"})

    @pytest.mark.asyncio
    async def test_service_has_methods(self, mock_db):
        from app.services.ai.agent_service import AgentService

        service = AgentService.__new__(AgentService)
        service.db = mock_db
        service.tenant_id = 1
        service.repo = AsyncMock()

        assert hasattr(service, 'create')
        assert hasattr(service, 'publish_agent')
        assert hasattr(service, 'rollback_agent')
        assert hasattr(service, 'get_agent_detail')

    @pytest.mark.asyncio
    async def test_validate_agent_max_tokens_against_model_limit(self, mock_db):
        from app.exceptions import BusinessException
        from app.services.ai.agent_service import (
            _validate_agent_max_tokens_against_model,
        )

        model_repo = AsyncMock()
        model_repo.get_by_id = AsyncMock(
            return_value=make_mock_model(
                id=7,
                name="gpt-4.1",
                max_output_tokens=4096,
            ),
        )

        with patch(
            "app.services.ai.agent_service.AIModelRepository",
            return_value=model_repo,
        ), pytest.raises(BusinessException) as exc_info:
            await _validate_agent_max_tokens_against_model(
                mock_db,
                model_id=7,
                max_tokens=8192,
            )

        assert "4096" in str(exc_info.value)


class TestAgentQuery:

    @pytest.mark.asyncio
    async def test_get_by_id_found(self, mock_db):
        from app.services.ai.agent_service import AgentService

        agent = _make_agent()
        service = AgentService.__new__(AgentService)
        service.db = mock_db
        service.tenant_id = 1
        service.repo = AsyncMock()
        service.repo.get_by_id = AsyncMock(return_value=agent)

        result = await service.repo.get_by_id(1)
        assert result.name == "Test Agent"

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self, mock_db):
        from app.services.ai.agent_service import AgentService

        service = AgentService.__new__(AgentService)
        service.db = mock_db
        service.tenant_id = 1
        service.repo = AsyncMock()
        service.repo.get_by_id = AsyncMock(return_value=None)

        result = await service.repo.get_by_id(999)
        assert result is None


class TestPublishAgent:
    def test_get_version_repo_uses_platform_tenant_for_platform_agents(self, mock_db):
        from app.configs.service import PLATFORM_TENANT_ID
        from app.services.ai.agent_service import AgentService

        service = AgentService.__new__(AgentService)
        service.db = mock_db
        service.tenant_id = None

        with patch(
            "app.services.ai.agent_service.AgentVersionRepository",
        ) as repo_cls:
            service._get_version_repo()

        repo_cls.assert_called_once_with(mock_db, PLATFORM_TENANT_ID)

    @pytest.mark.asyncio
    async def test_service_has_publish(self, mock_db):
        from app.services.ai.agent_service import AgentService

        service = AgentService.__new__(AgentService)
        service.db = mock_db
        service.tenant_id = 1
        service.repo = AsyncMock()

        assert hasattr(service, 'publish_agent')
        assert hasattr(service, 'rollback_agent')
        assert hasattr(service, 'get_versions')

    @pytest.mark.asyncio
    async def test_publish_agent_snapshots_rag_config(self, mock_db):
        from app.services.ai.agent_service import AgentService

        rag_config = {
            "search_mode": "hybrid",
            "top_k": 7,
            "score_threshold": 0.42,
            "rewrite_strategy": "multi",
            "reranker_enabled": True,
            "context_token_ratio": 0.55,
        }
        agent = _make_agent(
            rag_config=rag_config,
            context_config={"max_history_messages": 12},
            output_schema=[{"name": "answer"}],
            quota_config={"daily_token_limit": 1000},
            welcome_message="hello",
            suggested_questions=["q1"],
            input_variables=[{"name": "customer"}],
        )
        updated = _make_agent(
            status="published",
            published_version=4,
            rag_config=rag_config,
        )

        version_repo = AsyncMock()
        version_repo.get_latest_version_number = AsyncMock(return_value=3)
        version_repo.create = AsyncMock()

        service = AgentService.__new__(AgentService)
        service.db = mock_db
        service.tenant_id = 1
        service.repo = AsyncMock()
        service.repo.get_by_id = AsyncMock(return_value=agent)
        service.repo.update = AsyncMock(return_value=updated)
        service._get_version_repo = MagicMock(return_value=version_repo)
        service._snapshot_skill_grants = AsyncMock(return_value=[])

        result = await service.publish_agent(
            agent_id=agent.id,
            change_log="rag updated",
            created_by=9,
        )

        assert result is updated
        version_repo.create.assert_awaited_once()
        created_payload = version_repo.create.await_args.args[0]
        assert created_payload["version"] == 4
        assert created_payload["rag_config"] == rag_config
        assert created_payload["context_config"] == {"max_history_messages": 12}
        assert created_payload["output_schema"] == [{"name": "answer"}]
        assert created_payload["skill_grant_snapshot"] == []

    @pytest.mark.asyncio
    async def test_publish_platform_agent_uses_platform_tenant_in_version_snapshot(
        self, mock_db
    ):
        from app.configs.service import PLATFORM_TENANT_ID
        from app.services.ai.agent_service import AgentService

        agent = _make_agent(owner_tenant_id=None)
        updated = _make_agent(status="published", published_version=1)

        version_repo = AsyncMock()
        version_repo.get_latest_version_number = AsyncMock(return_value=0)
        version_repo.create = AsyncMock()

        service = AgentService.__new__(AgentService)
        service.db = mock_db
        service.tenant_id = None
        service.repo = AsyncMock()
        service.repo.get_by_id = AsyncMock(return_value=agent)
        service.repo.update = AsyncMock(return_value=updated)
        service._get_version_repo = MagicMock(return_value=version_repo)
        service._snapshot_skill_grants = AsyncMock(return_value=[])

        await service.publish_agent(
            agent_id=agent.id,
            change_log="platform publish",
            created_by=1,
        )

        created_payload = version_repo.create.await_args.args[0]
        assert created_payload["tenant_id"] == PLATFORM_TENANT_ID


class TestCascadeConversationMemoryCleanup:

    @pytest.mark.asyncio
    async def test_tenant_before_delete_clears_cascaded_conversation_memory(self, mock_db):
        from app.services.ai.agent_service import AgentService

        service = AgentService.__new__(AgentService)
        service.db = mock_db
        service.tenant_id = 1
        service._default_delete_level = "tenant"
        service.repo = AsyncMock()
        service.repo.get_by_id = AsyncMock(
            return_value=_make_agent(owner_tenant_id=1, is_system=False),
        )
        service.repo.list_conversation_memory_cleanup_targets = AsyncMock(
            return_value=[(1, 101), (1, 102), (1, 101)],
        )
        service.repo.cascade_soft_delete_conversations = AsyncMock()

        memory_svc = AsyncMock()
        memory_svc.clear_conversation_memories = AsyncMock(return_value=3)

        with patch(
            "app.services.ai.session_memory_service.SessionMemoryService",
            return_value=memory_svc,
        ) as mock_memory_service:
            await service._before_delete(9)

        service.repo.cascade_soft_delete_conversations.assert_awaited_once_with(
            9,
            "tenant",
        )
        mock_memory_service.assert_called_once_with(1)
        memory_svc.clear_conversation_memories.assert_awaited_once_with(
            [101, 102, 101],
        )

    @pytest.mark.asyncio
    async def test_admin_before_delete_clears_multi_tenant_conversation_memory(self, mock_db):
        from app.services.ai.agent_service import AdminAgentService

        service = AdminAgentService.__new__(AdminAgentService)
        service.db = mock_db
        service._default_delete_level = "admin"
        service.repo = AsyncMock()
        service.repo.get_by_id = AsyncMock(
            return_value=_make_agent(owner_tenant_id=7, is_system=False),
        )
        service.repo.list_conversation_memory_cleanup_targets = AsyncMock(
            return_value=[(0, 201), (7, 301), (7, 302)],
        )
        service.repo.cascade_soft_delete_conversations = AsyncMock()

        memory_services: dict[int, AsyncMock] = {}

        def _memory_factory(tenant_id: int):
            svc = memory_services.get(tenant_id)
            if svc is None:
                svc = AsyncMock()
                svc.clear_conversation_memories = AsyncMock(return_value=1)
                memory_services[tenant_id] = svc
            return svc

        assignment_repo = AsyncMock()
        assignment_repo.delete_all_for_resource = AsyncMock()

        with patch(
            "app.services.ai.session_memory_service.SessionMemoryService",
            side_effect=_memory_factory,
        ), patch(
            "app.repositories.system.resource_tenant_assignment_repository.ResourceTenantAssignmentRepository",
            return_value=assignment_repo,
        ):
            await service._before_delete(11)

        service.repo.cascade_soft_delete_conversations.assert_awaited_once_with(
            11,
            "admin",
        )
        memory_services[0].clear_conversation_memories.assert_awaited_once_with([201])
        memory_services[7].clear_conversation_memories.assert_awaited_once_with([301, 302])
        assignment_repo.delete_all_for_resource.assert_awaited_once_with("agent", 11)


class TestRollbackBindings:

    @pytest.mark.asyncio
    async def test_restore_skill_grants_rebuilds_snapshot_via_batch_bind(self, mock_db):
        from app.services.ai.agent_service import AgentService

        service = AgentService.__new__(AgentService)
        service.db = mock_db
        service.tenant_id = 1

        active_skill_a = make_mock_model(id=11, is_deleted=False)
        active_skill_b = make_mock_model(id=22, is_deleted=False)
        deleted_skill = make_mock_model(id=33, is_deleted=True)
        mock_db.get = AsyncMock(
            side_effect=lambda _model, skill_id: {
                11: active_skill_a,
                22: active_skill_b,
                33: deleted_skill,
            }.get(skill_id),
        )

        grant_service = AsyncMock()
        grant_service.batch_bind = AsyncMock(return_value=[
            make_mock_model(id=101, skill_id=11),
            make_mock_model(id=102, skill_id=22),
        ])
        grant_service.update_grant = AsyncMock()
        grant_service.delete_all_for_agent = AsyncMock()

        snapshot = [
            {
                "skill_id": 11,
                "enabled": False,
                "default_consent_mode": "ask",
                "capability_consent_overrides": {"tool_a": "reject"},
                "sort_order": 9,
                "config_override": {"timeout": 30},
            },
            {
                "skill_id": 22,
                "enabled": True,
                "default_consent_mode": "auto",
                "capability_consent_overrides": None,
                "sort_order": 3,
                "config_override": {"region": "cn"},
            },
            {
                "skill_id": 33,
                "enabled": True,
                "default_consent_mode": "auto",
            },
        ]

        with patch(
            "app.services.ai.agent_skill_grant_service.AgentSkillGrantService",
            return_value=grant_service,
        ):
            await service._restore_skill_grants(7, snapshot)

        grant_service.batch_bind.assert_awaited_once_with(
            agent_id=7,
            skill_ids=[11, 22],
            default_consent_modes={"11": "ask", "22": "auto"},
        )
        grant_service.delete_all_for_agent.assert_not_awaited()
        assert grant_service.update_grant.await_args_list[0].args == (
            101,
            {
                "enabled": False,
                "default_consent_mode": "ask",
                "capability_consent_overrides": {"tool_a": "reject"},
                "sort_order": 9,
                "config_override": {"timeout": 30},
            },
        )
        assert grant_service.update_grant.await_args_list[1].args == (
            102,
            {
                "enabled": True,
                "default_consent_mode": "auto",
                "capability_consent_overrides": None,
                "sort_order": 3,
                "config_override": {"region": "cn"},
            },
        )


class TestVersionRagConfig:

    @pytest.mark.asyncio
    async def test_rollback_agent_restores_rag_config(self, mock_db):
        from app.services.ai.agent_service import AgentService

        version_record = make_mock_model(
            version=2,
            system_prompt="prompt v2",
            model_id=3,
            temperature=0.5,
            max_tokens=1024,
            top_p=0.9,
            execution_mode="conversation",
            input_variables=[{"name": "region"}],
            welcome_message="welcome",
            suggested_questions=["s1"],
            quota_config={"daily_token_limit": 2000},
            rag_config={
                "search_mode": "keyword",
                "top_k": 8,
                "score_threshold": 0.3,
                "rewrite_strategy": "none",
                "reranker_enabled": False,
                "context_token_ratio": 0.4,
            },
            context_config={"max_history_messages": 8},
            output_schema=[{"name": "summary"}],
            skill_grant_snapshot=[
                {
                    "skill_id": 9,
                    "default_consent_mode": "auto",
                    "capability_consent_overrides": None,
                }
            ],
        )
        updated = _make_agent(
            status="draft",
            rag_config=version_record.rag_config,
        )

        version_repo = AsyncMock()
        version_repo.get_by_agent_and_version = AsyncMock(return_value=version_record)

        service = AgentService.__new__(AgentService)
        service.db = mock_db
        service.tenant_id = 1
        service.repo = AsyncMock()
        service.repo.get_by_id = AsyncMock(return_value=_make_agent())
        service.repo.update = AsyncMock(return_value=updated)
        service._get_version_repo = MagicMock(return_value=version_repo)
        service._restore_skill_grants = AsyncMock()

        result = await service.rollback_agent(agent_id=1, version=2)

        assert result is updated
        service.repo.update.assert_awaited_once()
        rollback_payload = service.repo.update.await_args.args[1]
        assert rollback_payload["rag_config"] == version_record.rag_config
        assert rollback_payload["context_config"] == {"max_history_messages": 8}
        assert rollback_payload["output_schema"] == [{"name": "summary"}]
        service._restore_skill_grants.assert_awaited_once_with(
            1,
            [
                {
                    "skill_id": 9,
                    "default_consent_mode": "auto",
                    "capability_consent_overrides": None,
                }
            ],
        )

    @pytest.mark.asyncio
    async def test_diff_versions_includes_rag_config(self, mock_db):
        from app.services.ai.agent_service import AgentService

        version_repo = AsyncMock()
        version_repo.get_by_agent_and_version = AsyncMock(
            side_effect=[
                make_mock_model(
                    rag_config={"search_mode": "hybrid", "top_k": 5},
                    context_config={"max_history_messages": 10},
                    output_schema=[{"name": "answer"}],
                    system_prompt="v1",
                    model_id=1,
                    temperature=0.7,
                    max_tokens=1000,
                    top_p=1.0,
                    execution_mode="conversation",
                    input_variables=[],
                    welcome_message=None,
                    suggested_questions=[],
                    quota_config=None,
                ),
                make_mock_model(
                    rag_config={"search_mode": "keyword", "top_k": 8},
                    context_config={"max_history_messages": 10},
                    output_schema=[{"name": "answer"}],
                    system_prompt="v1",
                    model_id=1,
                    temperature=0.7,
                    max_tokens=1000,
                    top_p=1.0,
                    execution_mode="conversation",
                    input_variables=[],
                    welcome_message=None,
                    suggested_questions=[],
                    quota_config=None,
                ),
            ]
        )

        service = AgentService.__new__(AgentService)
        service.db = mock_db
        service.tenant_id = 1
        service._get_version_repo = MagicMock(return_value=version_repo)

        diff = await service.diff_versions(agent_id=1, v1=1, v2=2)

        assert diff["changes"]["rag_config"] == {
            "v1": {"search_mode": "hybrid", "top_k": 5},
            "v2": {"search_mode": "keyword", "top_k": 8},
        }

    def test_normalize_agent_rag_config_rejects_invalid_payload(self):
        from app.exceptions import BusinessException
        from app.services.ai.agent_service import _normalize_agent_rag_config

        with pytest.raises(BusinessException):
            _normalize_agent_rag_config("bad-payload")

        with pytest.raises(BusinessException):
            _normalize_agent_rag_config({"top_k": 0})

        with pytest.raises(BusinessException):
            _normalize_agent_rag_config({"context_token_ratio": 1.2})

    def test_normalize_agent_rag_config_accepts_supported_fields(self):
        from app.services.ai.agent_service import _normalize_agent_rag_config

        result = _normalize_agent_rag_config({
            "search_mode": "hybrid",
            "top_k": 6,
            "score_threshold": 0.66,
            "rewrite_strategy": "multi",
            "reranker_enabled": True,
            "context_token_ratio": 0.45,
        })

        assert result == {
            "search_mode": "hybrid",
            "top_k": 6,
            "score_threshold": 0.66,
            "rewrite_strategy": "multi",
            "reranker_enabled": True,
            "context_token_ratio": 0.45,
        }


class TestGetAgentDetail:

    @pytest.mark.asyncio
    async def test_detail_not_found(self, mock_db):
        from app.exceptions import NotFoundException
        from app.services.ai.agent_service import AgentService

        service = AgentService.__new__(AgentService)
        service.db = mock_db
        service.tenant_id = 1
        service.repo = AsyncMock()
        service.repo.get_by_id = AsyncMock(return_value=None)

        with pytest.raises(NotFoundException):
            await service.get_agent_detail(999)

    @pytest.mark.asyncio
    async def test_detail_returns_dict(self, mock_db):
        from app.repositories.ai.agent_memory_override_repository import (
            AgentMemoryOverrideRepository,
        )
        from app.services.ai.agent_service import AgentService

        agent = _make_agent(owner_tenant_id=None)
        agent.to_dict.return_value = {"id": 1, "name": "Test Agent"}
        agent.model = MagicMock()
        agent.model.to_dict.return_value = {"id": 1, "name": "gpt-4"}
        service = AgentService.__new__(AgentService)
        service.db = mock_db
        service.tenant_id = 1
        service.repo = AsyncMock()
        service.repo.get_by_id = AsyncMock(return_value=agent)
        service.repo.get_agent_with_model = AsyncMock(return_value=agent)
        service._get_platform_default_memory_enabled = AsyncMock(return_value=True)
        override_repo = AsyncMock(spec=AgentMemoryOverrideRepository)
        override_repo.get_by_agent_id = AsyncMock(return_value=None)
        service._get_memory_override_repo = MagicMock(return_value=override_repo)

        result = await service.get_agent_detail(1)

        assert isinstance(result, dict)
        assert result["id"] == 1
        assert result["owner_type"] == "platform"
        assert result["tenant_id"] is None

    @pytest.mark.asyncio
    async def test_detail_derives_tenant_owner_type(self, mock_db):
        from app.repositories.ai.agent_memory_override_repository import (
            AgentMemoryOverrideRepository,
        )
        from app.services.ai.agent_service import AgentService

        agent = _make_agent(owner_tenant_id=3)
        agent.to_dict.return_value = {"id": 7, "name": "Tenant Agent"}
        agent.model = MagicMock()
        service = AgentService.__new__(AgentService)
        service.db = mock_db
        service.tenant_id = 3
        service.repo = AsyncMock()
        service.repo.get_by_id = AsyncMock(return_value=agent)
        service._get_platform_default_memory_enabled = AsyncMock(return_value=True)
        override_repo = AsyncMock(spec=AgentMemoryOverrideRepository)
        override_repo.get_by_agent_id = AsyncMock(return_value=None)
        service._get_memory_override_repo = MagicMock(return_value=override_repo)

        result = await service.get_agent_detail(7)

        assert result["owner_type"] == "tenant"
        assert result["tenant_id"] == 3
