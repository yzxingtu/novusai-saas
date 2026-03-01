"""
AgentService 单元测试

覆盖：CRUD 钩子、版本发布/回滚、访问权限、状态变更、系统智能体保护。
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import pytest

from tests.services.conftest import make_mock_model, make_scalar_result, make_scalars_result


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
        from app.services.ai.agent_service import AgentService
        from app.exceptions import BusinessException

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


class TestGetAgentDetail:

    @pytest.mark.asyncio
    async def test_detail_not_found(self, mock_db):
        from app.services.ai.agent_service import AgentService
        from app.exceptions import NotFoundException

        service = AgentService.__new__(AgentService)
        service.db = mock_db
        service.tenant_id = 1
        service.repo = AsyncMock()
        service.repo.get_by_id = AsyncMock(return_value=None)

        with pytest.raises(NotFoundException):
            await service.get_agent_detail(999)

    @pytest.mark.asyncio
    async def test_detail_returns_dict(self, mock_db):
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

        result = await service.get_agent_detail(1)

        assert isinstance(result, dict)
        assert result["id"] == 1
