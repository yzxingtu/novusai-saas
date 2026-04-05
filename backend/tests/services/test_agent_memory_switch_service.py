"""Agent 记忆开关服务测试 / Service.

覆盖：
1) 三层开关生效规则计算
2) 企业关闭覆盖写入/清除
3) 管理端 Agent 开关更新"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest


def _make_agent(**overrides):
    data = {
        "id": 1,
        "tenant_id": 1,
        "owner_tenant_id": 1,
        "memory_enabled": True,
        "is_deleted": False,
    }
    data.update(overrides)
    return MagicMock(**data)


def _make_override(**overrides):
    data = {
        "id": 10,
        "tenant_id": 1,
        "agent_id": 1,
        "disabled": True,
        "is_deleted": False,
    }
    data.update(overrides)
    return MagicMock(**data)


@pytest.mark.asyncio
async def test_resolve_memory_effective_config_all_enabled(mock_db):
    from app.services.ai.agent_service import AgentService

    svc = AgentService.__new__(AgentService)
    svc.db = mock_db
    svc.tenant_id = 1
    svc.repo = AsyncMock()
    svc.repo.get_by_id = AsyncMock(return_value=_make_agent(memory_enabled=True))
    svc._get_platform_default_memory_enabled = AsyncMock(return_value=True)
    override_repo = AsyncMock()
    override_repo.get_by_agent_id = AsyncMock(return_value=None)
    svc._get_memory_override_repo = MagicMock(return_value=override_repo)

    result = await svc.resolve_memory_effective_config(1)

    assert result["platform_default_memory_enabled"] is True
    assert result["admin_agent_memory_enabled"] is True
    assert result["tenant_agent_memory_disabled"] is False
    assert result["effective_memory_enabled"] is True


@pytest.mark.asyncio
async def test_resolve_memory_effective_config_disabled_by_tenant(mock_db):
    from app.services.ai.agent_service import AgentService

    svc = AgentService.__new__(AgentService)
    svc.db = mock_db
    svc.tenant_id = 1
    svc.repo = AsyncMock()
    svc.repo.get_by_id = AsyncMock(return_value=_make_agent(memory_enabled=True))
    svc._get_platform_default_memory_enabled = AsyncMock(return_value=True)
    override_repo = AsyncMock()
    override_repo.get_by_agent_id = AsyncMock(return_value=_make_override(disabled=True))
    svc._get_memory_override_repo = MagicMock(return_value=override_repo)

    result = await svc.resolve_memory_effective_config(1)
    assert result["effective_memory_enabled"] is False
    assert result["tenant_agent_memory_disabled"] is True


@pytest.mark.asyncio
async def test_set_memory_disabled_create_and_clear_override(mock_db):
    from app.services.ai.agent_service import AgentService

    svc = AgentService.__new__(AgentService)
    svc.db = mock_db
    svc.tenant_id = 1
    svc.repo = AsyncMock()
    svc.repo.get_by_id = AsyncMock(
        return_value=_make_agent(tenant_id=1, owner_tenant_id=1)
    )
    svc.get_memory_config = AsyncMock(return_value={"effective_memory_enabled": False})

    override_repo = AsyncMock()
    override_repo.get_by_agent_id = AsyncMock(side_effect=[None, _make_override(id=22)])
    svc._get_memory_override_repo = MagicMock(return_value=override_repo)

    # 关闭：创建覆盖记录
    await svc.set_memory_disabled(agent_id=1, disabled=True)
    override_repo.create.assert_awaited_once()

    # 恢复默认：删除覆盖记录
    await svc.set_memory_disabled(agent_id=1, disabled=False)
    override_repo.delete.assert_awaited_once_with(22, soft=False)


@pytest.mark.asyncio
async def test_admin_set_memory_enabled_updates_agent(mock_db):
    from app.services.ai.agent_service import AdminAgentService

    svc = AdminAgentService.__new__(AdminAgentService)
    svc.db = mock_db
    svc.repo = AsyncMock()
    svc.repo.get_by_id = AsyncMock(return_value=_make_agent(memory_enabled=True))
    svc.get_memory_config = AsyncMock(return_value={"admin_agent_memory_enabled": False})

    result = await svc.set_memory_enabled(1, enabled=False)

    svc.repo.update.assert_awaited_once_with(1, {"memory_enabled": False})
    assert result["admin_agent_memory_enabled"] is False
