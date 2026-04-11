"""Dependency resolution helpers for monitoring conversation queries."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Any

from app.repositories.ai.agent_conversation_repository import (
    AdminAgentConversationRepository,
    AgentConversationRepository,
)
from app.services.ai.conversation_service import ConversationService


@dataclass(slots=True, frozen=True)
class MonitoringConversationQueryDependencies:
    """Resolved factories/classes used by monitoring conversation query helpers."""

    tenant_conversation_service_factory: Any
    conversation_service_cls: type[ConversationService]
    admin_conversation_repo_factory: Any
    tenant_conversation_repo_factory: Any


def _resolve_override(service: Any, name: str, default: Any) -> Any:
    """Resolve explicit overrides while keeping old monkeypatch seams alive."""

    explicit_override = getattr(service, name, None)
    resolved = (
        explicit_override
        if explicit_override is not None
        else getattr(type(service), name, None) or default
    )
    module = sys.modules.get(type(service).__module__)
    module_override = getattr(module, name, None) if module is not None else None
    if (
        module_override is not None
        and module_override is not default
        and module_override is not resolved
    ):
        return module_override
    return resolved


def _resolve_conversation_service_class(
    service: Any,
) -> type[ConversationService]:
    candidate = getattr(service, "ConversationService", None)
    if isinstance(candidate, type) and hasattr(
        candidate,
        "get_service_for_conversation",
    ):
        return candidate

    candidate = getattr(type(service), "ConversationService", None)
    if isinstance(candidate, type) and hasattr(
        candidate,
        "get_service_for_conversation",
    ):
        return candidate

    return ConversationService


def resolve_monitoring_conversation_query_dependencies(
    service: Any,
) -> MonitoringConversationQueryDependencies:
    return MonitoringConversationQueryDependencies(
        tenant_conversation_service_factory=_resolve_override(
            service,
            "ConversationService",
            ConversationService,
        ),
        conversation_service_cls=_resolve_conversation_service_class(service),
        admin_conversation_repo_factory=_resolve_override(
            service,
            "AdminAgentConversationRepository",
            AdminAgentConversationRepository,
        ),
        tenant_conversation_repo_factory=_resolve_override(
            service,
            "AgentConversationRepository",
            AgentConversationRepository,
        ),
    )


__all__ = [
    "MonitoringConversationQueryDependencies",
    "resolve_monitoring_conversation_query_dependencies",
]
