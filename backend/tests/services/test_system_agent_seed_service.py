"""
Test type: behavioral
Scope: system agent bootstrap status and seed prerequisite decisions.
Mock strategy: fake repository; no database, provider API, or real AI dialogue is used.
"""

from types import SimpleNamespace

import pytest

from app.enums.agent import AgentStatusEnum
from app.exceptions import BusinessException
from app.services.system.system_agent_seed_service import (
    SYSTEM_AGENT_FEATURES,
    SystemAgentSeedService,
)


class FakeSeedRepository:
    def __init__(
        self,
        *,
        assignments: dict[str, SimpleNamespace] | None = None,
        model: SimpleNamespace | None = None,
        provider: SimpleNamespace | None = None,
    ) -> None:
        self.assignments = assignments or {}
        self.model = model
        self.provider = provider

    async def get_first_active_provider(self):
        return self.provider

    async def get_first_active_chat_model(self):
        return self.model

    async def get_global_assignment(
        self,
        feature_code: str,
        *,
        include_deleted: bool = False,
    ):
        _ = include_deleted
        return self.assignments.get(feature_code)

    async def get_ready_chat_model_with_active_provider(self, model_id: int):
        if self.model is None:
            return None
        if self.model.id != model_id:
            return None
        return self.model

    async def get_any_skill_by_key(
        self,
        key: str,
        *,
        include_deleted: bool = False,
    ):
        _ = key, include_deleted
        return None


class FakeDb:
    async def flush(self):
        return None

    async def refresh(self, obj):
        return obj


def _service(repo: FakeSeedRepository) -> SystemAgentSeedService:
    service = SystemAgentSeedService(db=FakeDb())
    service.repo = repo
    return service


def _provider() -> SimpleNamespace:
    return SimpleNamespace(
        code="openai",
        id=1,
        is_active=True,
        name="OpenAI",
        sort_order=0,
    )


def _model() -> SimpleNamespace:
    return SimpleNamespace(
        code="gpt-5.4",
        id=10,
        is_active=True,
        is_deleted=False,
        name="GPT-5.4",
        provider=_provider(),
        provider_id=1,
        type="chat",
    )


def _assignment(
    feature,
    *,
    active: bool = True,
    agent: SimpleNamespace | None = None,
    agent_id: int | None = 100,
    deleted: bool = False,
) -> SimpleNamespace:
    return SimpleNamespace(
        agent=agent,
        agent_id=agent_id,
        feature_code=feature.feature_code,
        feature_name=feature.feature_name,
        id=1,
        is_active=active,
        is_deleted=deleted,
    )


def _agent(
    feature,
    *,
    is_system: bool = True,
    model_id: int = 10,
    scope: str | None = None,
    status: str = AgentStatusEnum.PUBLISHED.value,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=100,
        is_deleted=False,
        is_system=is_system,
        model_id=model_id,
        name=f"{feature.feature_name} Agent",
        owner_tenant_id=None,
        scope=scope or feature.required_scope,
        status=status,
    )


@pytest.mark.asyncio
async def test_bootstrap_status_reports_missing_provider() -> None:
    service = _service(FakeSeedRepository())

    status = await service.get_bootstrap_status()

    assert status["bootstrap_state"] == "missing_provider"
    assert status["runtime_ready"] is False
    assert status["has_active_provider"] is False
    assert status["needs_seed"] is False


@pytest.mark.asyncio
async def test_bootstrap_status_reports_missing_chat_model() -> None:
    service = _service(FakeSeedRepository(provider=_provider()))

    status = await service.get_bootstrap_status()

    assert status["bootstrap_state"] == "missing_model"
    assert status["has_active_provider"] is True
    assert status["has_active_chat_model"] is False
    assert status["needs_seed"] is False


@pytest.mark.asyncio
async def test_bootstrap_status_preserves_valid_custom_assignments() -> None:
    assignments = {
        feature.feature_code: _assignment(
            feature,
            agent=_agent(feature, is_system=False),
        )
        for feature in SYSTEM_AGENT_FEATURES
    }
    service = _service(
        FakeSeedRepository(
            assignments=assignments,
            model=_model(),
            provider=_provider(),
        )
    )

    status = await service.get_bootstrap_status()

    assert status["bootstrap_state"] == "ready"
    assert status["system_agents_ready"] is True
    assert status["needs_seed"] is False
    assert {
        item["state"] for item in status["system_assignments"]
    } == {"custom_ready"}


@pytest.mark.asyncio
async def test_bootstrap_status_marks_custom_assignment_with_bad_model_repairable() -> None:
    first, second = SYSTEM_AGENT_FEATURES
    service = _service(
        FakeSeedRepository(
            assignments={
                first.feature_code: _assignment(
                    first,
                    agent=_agent(first, is_system=False, model_id=99),
                ),
                second.feature_code: _assignment(second, agent=_agent(second)),
            },
            model=_model(),
            provider=_provider(),
        )
    )

    status = await service.get_bootstrap_status()

    assert status["bootstrap_state"] == "seed_system"
    bad_assignment = status["system_assignments"][0]
    assert bad_assignment["state"] == "bad_agent"
    assert bad_assignment["repairable"] is True
    assert bad_assignment["preserve_custom_assignment"] is False


@pytest.mark.asyncio
async def test_bootstrap_status_marks_null_assignment_as_repairable() -> None:
    first, second = SYSTEM_AGENT_FEATURES
    service = _service(
        FakeSeedRepository(
            assignments={
                first.feature_code: _assignment(first, agent=None, agent_id=None),
                second.feature_code: _assignment(second, agent=_agent(second)),
            },
            model=_model(),
            provider=_provider(),
        )
    )

    status = await service.get_bootstrap_status()

    assert status["bootstrap_state"] == "seed_system"
    assert status["needs_seed"] is True
    null_assignment = status["system_assignments"][0]
    assert null_assignment["state"] == "missing_agent"
    assert null_assignment["repairable"] is True


@pytest.mark.asyncio
async def test_seed_system_agents_rejects_missing_provider() -> None:
    service = _service(FakeSeedRepository())

    with pytest.raises(BusinessException):
        await service.seed_system_agents()


@pytest.mark.asyncio
async def test_ensure_agent_reuses_system_agent_when_custom_agent_has_same_name() -> None:
    feature = SYSTEM_AGENT_FEATURES[0]
    model = _model()
    custom_agent = SimpleNamespace(
        id=90,
        is_deleted=False,
        is_system=False,
        name=feature.agent_name,
    )
    system_agent = SimpleNamespace(
        id=100,
        is_deleted=False,
        is_system=True,
        name=feature.agent_name,
    )

    class AgentRepo(FakeSeedRepository):
        def __init__(self) -> None:
            super().__init__(model=model, provider=_provider())
            self.custom_agent = custom_agent
            self.system_agent = system_agent
            self.created_payloads = []

        async def get_platform_agent_by_name(self, name, *, include_deleted=False):
            _ = name, include_deleted
            return self.custom_agent

        async def get_platform_system_agent_by_name(
            self,
            name,
            *,
            include_deleted=False,
        ):
            _ = name, include_deleted
            return self.system_agent

        async def create_agent(self, data):
            self.created_payloads.append(data)
            return SimpleNamespace(id=101, **data)

    repo = AgentRepo()
    service = _service(repo)

    agent = await service._ensure_agent(feature, model=model)

    assert agent.id == system_agent.id
    assert agent.is_system is True
    assert agent.model_id == model.id
    assert repo.created_payloads == []


@pytest.mark.asyncio
async def test_ensure_skill_rejects_non_system_key_conflict() -> None:
    class SkillRepo(FakeSeedRepository):
        async def get_platform_system_skill_by_key(
            self,
            key,
            *,
            include_deleted=False,
        ):
            _ = key, include_deleted
            return None

        async def get_any_skill_by_key(
            self,
            key,
            *,
            include_deleted=False,
        ):
            _ = key, include_deleted
            return SimpleNamespace(id=7, is_system=False, key="internal_operations")

        async def create_skill(self, data):
            raise AssertionError(f"create_skill should not be called: {data}")

    service = _service(SkillRepo(model=_model(), provider=_provider()))

    with pytest.raises(BusinessException):
        await service._ensure_skill(SimpleNamespace(id=1))
