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


@pytest.mark.asyncio
async def test_get_agent_skills_filters_inactive_package_grants(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services.ai.agent_skill_grant_service import AgentSkillGrantService

    active_grant = SimpleNamespace(
        id=1,
        agent_id=59,
        skill_id=3,
        enabled=True,
        config_override=None,
        sort_order=0,
        default_consent_mode="auto",
        capability_consent_overrides=None,
        skill=SimpleNamespace(
            id=3,
            name="active_skill",
            key="active_skill",
            description="active",
            type="toolkit",
            source_type="custom",
            status="active",
            package_id=11,
            is_active=True,
            is_deleted=False,
            package=SimpleNamespace(
                name="active-package",
                description="active",
                is_system=False,
                is_active=True,
                is_deleted=False,
            ),
        ),
    )
    inactive_package_grant = SimpleNamespace(
        id=2,
        agent_id=59,
        skill_id=4,
        enabled=True,
        config_override=None,
        sort_order=1,
        default_consent_mode="auto",
        capability_consent_overrides=None,
        skill=SimpleNamespace(
            id=4,
            name="inactive_package_skill",
            key="inactive_package_skill",
            description="inactive",
            type="toolkit",
            source_type="custom",
            status="active",
            package_id=12,
            is_active=True,
            is_deleted=False,
            package=SimpleNamespace(
                name="inactive-package",
                description="inactive",
                is_system=False,
                is_active=False,
                is_deleted=False,
            ),
        ),
    )
    repo_stub = AsyncMock()
    repo_stub.get_by_agent_id = AsyncMock(
        return_value=[active_grant, inactive_package_grant]
    )

    monkeypatch.setattr(
        "app.services.ai.agent_skill_grant_service.AgentSkillGrantRepository",
        lambda db, tenant_id: repo_stub,
    )

    service = AgentSkillGrantService.__new__(AgentSkillGrantService)
    service.db = AsyncMock()
    service.tenant_id = 9
    service.skill_repo = AsyncMock()
    service.skill_repo.get_by_ids = AsyncMock(return_value=[active_grant.skill])
    service.agent_repo = AsyncMock()
    service.agent_repo.get_by_id = AsyncMock(
        return_value=SimpleNamespace(id=59, owner_tenant_id=9),
    )

    result = await service.get_agent_skills(agent_id=59)

    service.skill_repo.get_by_ids.assert_awaited_once_with([3, 4])
    assert [item["skill_name"] for item in result] == ["active_skill"]


@pytest.mark.asyncio
async def test_get_agent_skills_filters_tenant_invisible_grants(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services.ai.agent_skill_grant_service import AgentSkillGrantService

    visible_grant = SimpleNamespace(
        id=1,
        agent_id=59,
        skill_id=3,
        enabled=True,
        config_override=None,
        sort_order=0,
        default_consent_mode="auto",
        capability_consent_overrides=None,
        skill=SimpleNamespace(
            id=3,
            name="visible_skill",
            key="visible_skill",
            description="visible",
            type="toolkit",
            source_type="custom",
            status="active",
            package_id=11,
            is_active=True,
            is_deleted=False,
            package=SimpleNamespace(
                name="visible-package",
                description="visible",
                is_system=False,
                is_active=True,
                is_deleted=False,
            ),
        ),
    )
    invisible_grant = SimpleNamespace(
        id=2,
        agent_id=59,
        skill_id=4,
        enabled=True,
        config_override=None,
        sort_order=1,
        default_consent_mode="auto",
        capability_consent_overrides=None,
        skill=SimpleNamespace(
            id=4,
            name="invisible_skill",
            key="invisible_skill",
            description="invisible",
            type="toolkit",
            source_type="custom",
            status="active",
            package_id=12,
            is_active=True,
            is_deleted=False,
            package=SimpleNamespace(
                name="invisible-package",
                description="invisible",
                is_system=False,
                is_active=True,
                is_deleted=False,
            ),
        ),
    )
    repo_stub = AsyncMock()
    repo_stub.get_by_agent_id = AsyncMock(return_value=[visible_grant, invisible_grant])
    visible_skill_repo = AsyncMock()
    visible_skill_repo.get_by_ids = AsyncMock(return_value=[visible_grant.skill])

    monkeypatch.setattr(
        "app.services.ai.agent_skill_grant_service.AgentSkillGrantRepository",
        lambda db, tenant_id: repo_stub,
    )
    monkeypatch.setattr(
        "app.services.ai.agent_skill_grant_service.SkillRepository",
        lambda db, tenant_id: visible_skill_repo,
    )

    service = AgentSkillGrantService.__new__(AgentSkillGrantService)
    service.db = AsyncMock()
    service.tenant_id = 9
    service.agent_repo = AsyncMock()
    service.agent_repo.get_by_id = AsyncMock(
        return_value=SimpleNamespace(id=59, owner_tenant_id=9),
    )

    result = await service.get_agent_skills(agent_id=59)

    visible_skill_repo.get_by_ids.assert_awaited_once_with([3, 4])
    assert [item["skill_name"] for item in result] == ["visible_skill"]


@pytest.mark.asyncio
async def test_bind_skill_rejects_inactive_package_skill() -> None:
    from app.exceptions import NotFoundException
    from app.services.ai.agent_skill_grant_service import AgentSkillGrantService

    service = AgentSkillGrantService.__new__(AgentSkillGrantService)
    service.db = AsyncMock()
    service.tenant_id = None
    service.agent_repo = AsyncMock()
    service.agent_repo.get_by_id = AsyncMock(
        return_value=SimpleNamespace(id=59, owner_tenant_id=None),
    )
    service.skill_repo = AsyncMock()
    service.skill_repo.get_by_id = AsyncMock(
        return_value=SimpleNamespace(
            id=3,
            is_active=True,
            is_deleted=False,
            package=SimpleNamespace(
                is_active=False,
                is_deleted=False,
            ),
        )
    )
    service.grant_repo = AsyncMock()

    with pytest.raises(NotFoundException):
        await service.bind_skill(agent_id=59, skill_id=3)

    service.grant_repo.create.assert_not_called()
