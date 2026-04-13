"""Typed runtime dependencies for agent chat stream persistence."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from importlib import import_module
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.agent_quota import AgentConcurrencyLimiter, AgentQuotaManager
from app.ai.agent_stats import AgentStatsManager
from app.ai.engine.types import ExecutionRequest, ExecutionResult
from app.services.ai.conversation_service import ConversationService

SessionFactory = Callable[[], Awaitable[AsyncSession]]  # noqa: WPS111


@dataclass(frozen=True)
class AgentChatStreamPersistenceDependencies:
    session_factory: SessionFactory
    conversation_service_cls: type[ConversationService]
    adjust_usage: Callable[..., Awaitable[None]]
    record_user_usage: Callable[..., Awaitable[None]]
    record_chat_stats: Callable[..., Awaitable[None]]
    release_concurrency: Callable[..., Awaitable[None]]
    publish_execution_completed: Callable[
        [ExecutionRequest, Any, ExecutionResult], Awaitable[None]
    ]
    publish_execution_failed: Callable[
        [ExecutionRequest, Any, str], Awaitable[None]
    ]

    @classmethod
    def from_mapping(
        cls,
        mapping: Mapping[str, Any],
    ) -> AgentChatStreamPersistenceDependencies:
        return cls(
            session_factory=mapping["session_factory"],
            conversation_service_cls=mapping["conversation_service_cls"],
            adjust_usage=mapping["adjust_usage"],
            record_user_usage=mapping["record_user_usage"],
            record_chat_stats=mapping["record_chat_stats"],
            release_concurrency=mapping["release_concurrency"],
            publish_execution_completed=mapping["publish_execution_completed"],
            publish_execution_failed=mapping["publish_execution_failed"],
        )


def default_agent_chat_stream_persistence_dependencies() -> AgentChatStreamPersistenceDependencies:
    # Resolve these through the public AgentChatService facade at runtime so
    # existing tests and legacy patch points keep intercepting the actual
    # stream persistence collaborators after the split.
    agent_chat_service = import_module("app.services.ai.agent_chat_service")
    session_factory = getattr(agent_chat_service, "async_session_factory")
    conversation_service_cls = getattr(agent_chat_service, "ConversationService")
    base_engine = getattr(agent_chat_service, "BaseEngine")
    return AgentChatStreamPersistenceDependencies(
        session_factory=session_factory,
        conversation_service_cls=conversation_service_cls,
        adjust_usage=AgentQuotaManager.adjust_usage,
        record_user_usage=AgentQuotaManager.record_user_usage,
        record_chat_stats=AgentStatsManager.record_chat,
        release_concurrency=AgentConcurrencyLimiter.release,
        publish_execution_completed=base_engine._publish_execution_completed,
        publish_execution_failed=base_engine._publish_execution_failed,
    )


__all__ = [
    "AgentChatStreamPersistenceDependencies",
    "default_agent_chat_stream_persistence_dependencies",
]
