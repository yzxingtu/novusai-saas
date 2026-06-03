"""Dependency resolution helpers for monitoring conversation queries."""

from __future__ import annotations

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
    """Resolve explicit service/class overrides from the monitoring owner chain."""

    explicit_override = getattr(service, name, None)
    if explicit_override is not None:
        return explicit_override

    class_override = getattr(type(service), name, None)
    if class_override is not None:
        return class_override

    return default


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
