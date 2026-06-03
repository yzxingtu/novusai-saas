"""Conversation export orchestration service."""

from __future__ import annotations

from typing import Any

from app.models.ai.agent_conversation import AgentConversation
from app.repositories.ai.conversation_message_repository import (
    ConversationMessageRepository,
)
from app.services.ai.conversation_export_service import ConversationExportService
from app.services.ai.conversation_read_model_service import (
    ConversationReadModelService,
)


class ConversationExportRuntimeService:
    """Loads all persisted messages and assembles export payloads."""

    def __init__(
        self,
        *,
        message_repo: ConversationMessageRepository,
        read_model_service: ConversationReadModelService,
    ) -> None:
        self._message_repo = message_repo
        self._read_model_service = read_model_service

    async def export_conversation(
        self,
        *,
        conversation: AgentConversation,
        export_format: str = "json",
    ) -> dict[str, Any]:
        messages = await self._load_all_messages(conversation.id)
        total_message_count = await self._message_repo.count_by_conversation(
            conversation.id,
        )
        serialized_messages = await self._read_model_service.serialize_export_messages(
            messages
        )

        title = conversation.title or f"conversation_{conversation.id}"
        if export_format == "markdown":
            content = ConversationExportService.to_markdown(
                conversation,
                serialized_messages,
            )
            filename = f"{title}.md"
        else:
            content = ConversationExportService.to_json(
                conversation,
                serialized_messages,
            )
            filename = f"{title}.json"

        return {
            "content": content,
            "filename": filename,
            "format": export_format,
            "total_message_count": total_message_count,
        }

    async def _load_all_messages(self, conversation_id: int) -> list[Any]:
        messages: list[Any] = []
        batch_size = 1000
        skip = 0
        while True:
            batch = await self._message_repo.get_by_conversation(
                conversation_id=conversation_id,
                skip=skip,
                limit=batch_size,
            )
            messages.extend(batch)
            if len(batch) < batch_size:
                break
            skip += batch_size
        return messages


__all__ = ["ConversationExportRuntimeService"]
