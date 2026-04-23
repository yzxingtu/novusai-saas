"""
Conversation history access helpers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.ai.types import ChatMessage
from app.services.ai.conversation_message_persistence_service import (
    ConversationMessagePersistenceService,
)

if TYPE_CHECKING:
    from app.services.ai.conversation_service import ConversationService


async def load_chat_history(
    service: "ConversationService",
    conversation_id: int,
    max_messages: int = 0,
    max_tokens: int | None = None,
) -> list[ChatMessage]:
    return await service.history_service.load_chat_history(
        conversation_id=conversation_id,
        max_messages=max_messages,
        max_tokens=max_tokens,
    )


def sanitize_tool_messages(messages: list[ChatMessage]) -> list[ChatMessage]:
    return ConversationMessagePersistenceService.sanitize_tool_messages(messages)


async def get_messages_for_conversation(
    service: "ConversationService",
    conversation_id: int,
) -> list[Any]:
    return await service.message_repo.get_by_conversation(conversation_id)
