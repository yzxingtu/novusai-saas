"""
Conversation search query service.
"""

from __future__ import annotations

from typing import Any

from app.core.i18n import _
from app.exceptions import BusinessException
from app.repositories.ai.conversation_message_repository import (
    ConversationMessageRepository,
)
from app.services.ai.conversation_read_model_service import (
    ConversationReadModelService,
)


class ConversationSearchQueryService:
    """Query-only helper for conversation message search."""

    def __init__(
        self,
        *,
        message_repo: ConversationMessageRepository,
        read_model_service: ConversationReadModelService,
    ) -> None:
        self._message_repo = message_repo
        self._read_model_service = read_model_service

    async def search_messages(
        self,
        *,
        keyword: str,
        page: int = 1,
        page_size: int = 20,
    ) -> dict[str, Any]:
        if not keyword or not keyword.strip():
            raise BusinessException(
                message=_("conversation.search_keyword_required"),
            )

        skip = (page - 1) * page_size
        messages, total = await self._message_repo.search_by_content(
            keyword=keyword.strip(),
            skip=skip,
            limit=page_size,
        )
        items = await self._read_model_service.serialize_search_messages(messages)

        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
        }


__all__ = ["ConversationSearchQueryService"]
