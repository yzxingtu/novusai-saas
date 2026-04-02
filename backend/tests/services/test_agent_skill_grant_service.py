from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest


@pytest.mark.asyncio
async def test_unbind_skill_hard_deletes_active_grant() -> None:
    from app.services.ai.agent_skill_grant_service import AgentSkillGrantService

    service = AgentSkillGrantService.__new__(AgentSkillGrantService)
    service.db = AsyncMock()
    service.tenant_id = None
    service.grant_repo = AsyncMock()
    service.grant_repo.get_grant = AsyncMock(
        return_value=SimpleNamespace(id=7, agent_id=59, skill_id=3),
    )
    service.grant_repo.delete = AsyncMock(return_value=True)

    await service.unbind_skill(agent_id=59, skill_id=3)

    service.grant_repo.get_grant.assert_awaited_once_with(59, 3)
    service.grant_repo.delete.assert_awaited_once_with(7, soft=False)


@pytest.mark.asyncio
async def test_unbind_skill_raises_when_hard_delete_fails() -> None:
    from app.exceptions import BusinessException
    from app.services.ai.agent_skill_grant_service import AgentSkillGrantService

    service = AgentSkillGrantService.__new__(AgentSkillGrantService)
    service.db = AsyncMock()
    service.tenant_id = None
    service.grant_repo = AsyncMock()
    service.grant_repo.get_grant = AsyncMock(
        return_value=SimpleNamespace(id=7, agent_id=59, skill_id=3),
    )
    service.grant_repo.delete = AsyncMock(return_value=False)

    with pytest.raises(BusinessException):
        await service.unbind_skill(agent_id=59, skill_id=3)

    service.grant_repo.delete.assert_awaited_once_with(7, soft=False)
