from __future__ import annotations

from app.repositories.ai.agent_conversation_repository import (
    AdminAgentConversationRepository,
    AgentConversationRepository,
)
from app.services.ai.conversation_service import ConversationService
from app.services.ai.monitoring_query_dependencies import (
    resolve_monitoring_conversation_query_dependencies,
)


class _CustomConversationService:
    @staticmethod
    async def get_service_for_conversation(_db, _conversation_id: int):
        raise NotImplementedError


class _CustomAdminConversationRepository:
    pass


class _CustomTenantConversationRepository:
    pass


def test_resolve_monitoring_query_dependencies_prefers_owner_chain_overrides() -> None:
    class _MonitoringServiceOwner:
        ConversationService = _CustomConversationService
        AdminAgentConversationRepository = _CustomAdminConversationRepository
        AgentConversationRepository = _CustomTenantConversationRepository

    dependencies = resolve_monitoring_conversation_query_dependencies(
        _MonitoringServiceOwner(),
    )

    assert (
        dependencies.tenant_conversation_service_factory is _CustomConversationService
    )
    assert dependencies.conversation_service_cls is _CustomConversationService
    assert (
        dependencies.admin_conversation_repo_factory
        is _CustomAdminConversationRepository
    )
    assert (
        dependencies.tenant_conversation_repo_factory
        is _CustomTenantConversationRepository
    )


def test_resolve_monitoring_query_dependencies_ignores_module_shadow_symbols() -> None:
    class _ModuleShadowConversationService:
        @staticmethod
        async def get_service_for_conversation(_db, _conversation_id: int):
            raise AssertionError("module shadow should not hijack live owner chain")

    class _MonitoringServiceWithoutOverrides:
        pass

    shadowed_symbols = {
        "ConversationService": _ModuleShadowConversationService,
        "AdminAgentConversationRepository": _CustomAdminConversationRepository,
        "AgentConversationRepository": _CustomTenantConversationRepository,
    }
    previous_symbols = {name: globals().get(name) for name in shadowed_symbols}
    globals().update(shadowed_symbols)
    try:
        dependencies = resolve_monitoring_conversation_query_dependencies(
            _MonitoringServiceWithoutOverrides(),
        )
    finally:
        for name, previous in previous_symbols.items():
            if previous is None:
                globals().pop(name, None)
            else:
                globals()[name] = previous

    assert dependencies.tenant_conversation_service_factory is ConversationService
    assert dependencies.conversation_service_cls is ConversationService
    assert (
        dependencies.admin_conversation_repo_factory is AdminAgentConversationRepository
    )
    assert dependencies.tenant_conversation_repo_factory is AgentConversationRepository
