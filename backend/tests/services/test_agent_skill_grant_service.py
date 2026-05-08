"""Test type: behavioral / structural
Scope: Agent skill grant service behavior and repository query guards.
Mocked dependencies: async repositories and DB execute capture only; no LLM,
tool executor, or intent planner mocks.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest


class _EmptyScalarResult:
    def all(self) -> list[Any]:
        return []


class _EmptyExecuteResult:
    def scalars(self) -> _EmptyScalarResult:
        return _EmptyScalarResult()

    def scalar_one_or_none(self) -> None:
        return None


class _StatementCaptureDb:
    def __init__(self) -> None:
        self.statements: list[Any] = []

    async def execute(self, stmt: Any) -> _EmptyExecuteResult:
        self.statements.append(stmt)
        return _EmptyExecuteResult()


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
        lambda _db, _tenant_id: repo_stub,
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
    assert "default_consent_mode" not in result[0]
    assert "capability_consent_overrides" not in result[0]


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
        lambda _db, _tenant_id: repo_stub,
    )
    monkeypatch.setattr(
        "app.services.ai.agent_skill_grant_service.SkillRepository",
        lambda _db, _tenant_id: visible_skill_repo,
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
    assert "default_consent_mode" not in result[0]
    assert "capability_consent_overrides" not in result[0]


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


@pytest.mark.asyncio
async def test_bind_skill_rejects_retired_online_search_skill() -> None:
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
            name="联网搜索",
            key="web_search",
            source_ref="web_search",
            is_active=True,
            is_deleted=False,
            package=SimpleNamespace(
                name="百度公开搜索",
                source_plugin="baidu_public_search",
                is_active=True,
                is_deleted=False,
            ),
        )
    )
    service.grant_repo = AsyncMock()

    with pytest.raises(NotFoundException):
        await service.bind_skill(agent_id=59, skill_id=3)

    service.grant_repo.create.assert_not_called()


@pytest.mark.asyncio
async def test_grant_repository_queries_filter_retired_skill_catalog() -> None:
    from app.repositories.ai.agent_skill_grant_repository import (
        AgentSkillGrantRepository,
    )

    db = _StatementCaptureDb()
    repo = AgentSkillGrantRepository(db, tenant_id=9)

    await repo.get_by_agent_id(59)
    await repo.get_enabled_by_agent_id(59)
    await repo.get_grant(59, 3)
    await repo.get_by_id(7)

    assert len(db.statements) == 4
    for stmt in db.statements:
        compiled = stmt.compile(compile_kwargs={"render_postcompile": True})
        sql = str(compiled).lower()
        params = " ".join(str(value).lower() for value in compiled.params.values())

        assert "join skills" in sql
        assert "join skill_packages" in sql
        assert "skills.is_deleted is false" in sql
        assert "skill_packages.is_deleted is false" in sql
        assert "replace" in sql
        assert "web_search" in params
        assert "searchprovider" in params
