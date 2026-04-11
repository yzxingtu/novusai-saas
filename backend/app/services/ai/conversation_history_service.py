"""History loading helpers for ConversationService."""

from __future__ import annotations

from app.ai.types import ChatMessage
from app.repositories.ai.conversation_message_repository import (
    ConversationMessageRepository,
)
from app.services.ai.conversation_message_persistence_service import (
    ConversationMessagePersistenceService,
)
from app.services.ai.conversation_read_model_service import (
    ConversationReadModelService,
)


class ConversationHistoryService:
    """Loads and normalizes persisted conversation history for runtime use."""

    def __init__(
        self,
        *,
        message_repo: ConversationMessageRepository,
        read_model_service: ConversationReadModelService,
        default_max_messages: int,
    ) -> None:
        self.message_repo = message_repo
        self.read_model_service = read_model_service
        self.default_max_messages = default_max_messages

    async def load_chat_history(
        self,
        *,
        conversation_id: int,
        max_messages: int = 0,
        max_tokens: int = 0,
    ) -> list[ChatMessage]:
        effective_limit = (
            max_messages if max_messages > 0 else self.default_max_messages
        )
        db_messages = await self.message_repo.get_last_n_messages(
            conversation_id=conversation_id,
            n=effective_limit,
        )
        chat_messages = self.read_model_service.build_chat_history_messages(
            db_messages,
            max_tokens=max_tokens,
        )
        return ConversationMessagePersistenceService.sanitize_tool_messages(
            chat_messages
        )


__all__ = ["ConversationHistoryService"]
