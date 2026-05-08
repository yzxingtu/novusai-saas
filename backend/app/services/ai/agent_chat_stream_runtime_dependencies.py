"""Typed runtime dependencies for agent chat stream persistence."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.agent_quota_concurrency import AgentConcurrencyLimiter
from app.ai.agent_quota_manager import AgentQuotaManager
from app.ai.agent_stats import AgentStatsManager
from app.ai.engine.base import BaseEngine
from app.ai.engine.types import ExecutionRequest, ExecutionResult
from app.core.database import async_session_factory
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
    publish_execution_failed: Callable[[ExecutionRequest, Any, str], Awaitable[None]]

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


def default_agent_chat_stream_persistence_dependencies() -> (
    AgentChatStreamPersistenceDependencies
):
    """Build the default stream persistence runtime dependencies."""
    return AgentChatStreamPersistenceDependencies(
        session_factory=async_session_factory,
        conversation_service_cls=ConversationService,
        adjust_usage=AgentQuotaManager.adjust_usage,
        record_user_usage=AgentQuotaManager.record_user_usage,
        record_chat_stats=AgentStatsManager.record_chat,
        release_concurrency=AgentConcurrencyLimiter.release,
        publish_execution_completed=BaseEngine._publish_execution_completed,
        publish_execution_failed=BaseEngine._publish_execution_failed,
    )


__all__ = [
    "AgentChatStreamPersistenceDependencies",
    "default_agent_chat_stream_persistence_dependencies",
]
