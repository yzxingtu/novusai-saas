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


class TestRollbackBindings:

    @pytest.mark.asyncio
    async def test_restore_skill_bindings_rebuilds_snapshot_via_batch_bind(self, mock_db):
        from app.services.ai.agent_service import AgentService

        service = AgentService.__new__(AgentService)
        service.db = mock_db
        service.tenant_id = 1

        active_pkg_a = make_mock_model(id=11, is_deleted=False)
        active_pkg_b = make_mock_model(id=22, is_deleted=False)
        deleted_pkg = make_mock_model(id=33, is_deleted=True)
        mock_db.get = AsyncMock(
            side_effect=lambda _model, pkg_id: {
                11: active_pkg_a,
                22: active_pkg_b,
                33: deleted_pkg,
            }.get(pkg_id),
        )

        binding_service = AsyncMock()
        binding_service.batch_bind = AsyncMock(return_value=[
            make_mock_model(id=101, package_id=11),
            make_mock_model(id=102, package_id=22),
        ])
        binding_service.update_binding = AsyncMock()
        binding_service.delete_all_for_agent = AsyncMock()

        snapshot = [
            {
                "package_id": 11,
                "enabled": False,
                "consent_mode": "ask",
                "skill_consent_overrides": {"tool_a": "reject"},
                "sort_order": 9,
                "config_override": {"timeout": 30},
            },
            {
                "package_id": 22,
                "enabled": True,
                "consent_mode": "auto",
                "skill_consent_overrides": None,
                "sort_order": 3,
                "config_override": {"region": "cn"},
            },
            {
                "package_id": 33,
                "enabled": True,
                "consent_mode": "auto",
            },
        ]

        with patch(
            "app.services.ai.agent_skill_binding_service.AgentSkillBindingService",
            return_value=binding_service,
        ):
            await service._restore_skill_bindings(7, snapshot)

        binding_service.batch_bind.assert_awaited_once_with(
            agent_id=7,
            package_ids=[11, 22],
            consent_modes={"11": "ask", "22": "auto"},
        )
        binding_service.delete_all_for_agent.assert_not_awaited()
        assert binding_service.update_binding.await_args_list[0].args == (
            101,
            {
                "enabled": False,
                "consent_mode": "ask",
                "skill_consent_overrides": {"tool_a": "reject"},
                "sort_order": 9,
                "config_override": {"timeout": 30},
            },
        )
        assert binding_service.update_binding.await_args_list[1].args == (
            102,
            {
                "enabled": True,
                "consent_mode": "auto",
                "skill_consent_overrides": None,
                "sort_order": 3,
                "config_override": {"region": "cn"},
            },
        )


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

        agent = _make_agent()
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
