"""
Conversation persistence helpers for ConversationService facade.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.ai.types import ChatMessage
from app.models.ai.agent import Agent
from app.models.ai.agent_conversation import AgentConversation
from app.services.ai.conversation_message_persistence_service import (
    ConversationMessagePersistenceService,
)

if TYPE_CHECKING:
    from app.ai.engine.types import ExecutionResult
    from app.services.ai.conversation_service import ConversationService


async def persist_chat_messages(
    service: ConversationService,
    conversation: AgentConversation,
    result: ExecutionResult,
    history_count: int,
    history_messages: list[ChatMessage] | None = None,
    agent_id: int | None = None,
    route_source: str | None = None,
    *,
    context_diagnostics: dict[str, Any] | None = None,
    last_run_summary: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], int]:
    return await ConversationMessagePersistenceService.persist_chat_messages(
        service,
        conversation=conversation,
        result=result,
        history_count=history_count,
        history_messages=history_messages,
        agent_id=agent_id,
        route_source=route_source,
        context_diagnostics=context_diagnostics,
        last_run_summary=last_run_summary,
    )


async def persist_user_messages(
    service: ConversationService,
    *,
    conversation: AgentConversation,
    messages: list[ChatMessage],
) -> int:
    return await ConversationMessagePersistenceService.persist_user_messages(
        service,
        conversation=conversation,
        messages=messages,
    )


async def mark_memory_updated(
    service: ConversationService, conversation_id: int
) -> None:
    await ConversationMessagePersistenceService.mark_memory_updated(
        service,
        conversation_id,
    )


async def get_context_compaction_snapshot(
    service: ConversationService,
    conversation_id: int,
    *,
    metadata_key: str,
) -> dict[str, Any] | None:
    return await ConversationMessagePersistenceService.get_context_compaction_snapshot(
        service,
        conversation_id,
        metadata_key=metadata_key,
    )


async def upsert_context_compaction_snapshot(
    service: ConversationService,
    conversation_id: int,
    *,
    metadata_key: str,
    summary: str,
    source_message_count: int,
    source_token_estimate: int,
) -> dict[str, Any] | None:
    return (
        await ConversationMessagePersistenceService.upsert_context_compaction_snapshot(
            service,
            conversation_id,
            metadata_key=metadata_key,
            summary=summary,
            source_message_count=source_message_count,
            source_token_estimate=source_token_estimate,
        )
    )


async def update_stats(
    service: ConversationService,
    conversation: AgentConversation,
    result: ExecutionResult,
    current_agent: Agent | None = None,
) -> None:
    await service.stats_service.update_stats(
        conversation=conversation,
        result=result,
        current_agent=current_agent,
    )


async def persist_stream_completion(
    service: ConversationService,
    *,
    conversation_id: int,
    result: ExecutionResult,
    history_count: int,
    history_messages: list[ChatMessage] | None = None,
    agent_id: int | None = None,
    route_source: str | None = None,
    context_diagnostics: dict[str, Any] | None = None,
    last_run_summary: dict[str, Any] | None = None,
    current_agent: Agent | None = None,
) -> int:
    return await service.stream_persistence_service.persist_stream_completion(
        conversation_id=conversation_id,
        result=result,
        history_count=history_count,
        history_messages=history_messages,
        agent_id=agent_id,
        route_source=route_source,
        context_diagnostics=context_diagnostics,
        last_run_summary=last_run_summary,
        current_agent=current_agent,
    )


async def persist_stream_last_error_marker(
    service: ConversationService,
    *,
    conversation_id: int,
    error_type: str,
    error_message: str,
    friendly_message: str,
    partial: bool,
    extra_payload: dict[str, Any] | None = None,
    memory_runtime_policy: dict[str, Any] | None = None,
) -> bool:
    return await service.stream_persistence_service.persist_stream_last_error_marker(
        conversation_id=conversation_id,
        error_type=error_type,
        error_message=error_message,
        friendly_message=friendly_message,
        partial=partial,
        extra_payload=extra_payload,
        memory_runtime_policy=memory_runtime_policy,
    )


async def save_stream_error_message(
    service: ConversationService,
    *,
    conversation_id: int,
    error_text: str,
    user_message: str,
    result: ExecutionResult,
    context_diagnostics_payload: dict[str, Any],
    last_run_summary_payload: dict[str, Any],
    persist_user_message: bool,
    agent_id: int,
    build_stream_error_display: Any,
) -> int:
    return await service.stream_persistence_service.save_stream_error_message(
        conversation_id=conversation_id,
        tenant_id=service.tenant_id,
        agent_id=agent_id,
        error_text=error_text,
        user_message=user_message,
        result=result,
        context_diagnostics_payload=context_diagnostics_payload,
        last_run_summary_payload=last_run_summary_payload,
        persist_user_message=persist_user_message,
        build_stream_error_display=build_stream_error_display,
    )
