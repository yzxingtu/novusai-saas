"""
Conversation context compaction support.
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable

from app.ai.context.engine import ConversationContextEngine
from app.ai.types import ChatMessage
from app.ai.utils.token_estimator import estimate_tokens
from app.models.ai.agent_conversation import AgentConversation
from app.repositories.ai.conversation_message_repository import (
    ConversationMessageRepository,
)


class ConversationCompactionService:
    """Build compact context summaries for archived conversation history."""

    def __init__(
        self,
        *,
        message_repo: ConversationMessageRepository,
        load_chat_history: Callable[..., Awaitable[list[ChatMessage]]],
        upsert_snapshot: Callable[..., Awaitable[dict[str, Any] | None]],
    ) -> None:
        self._message_repo = message_repo
        self._load_chat_history = load_chat_history
        self._upsert_snapshot = upsert_snapshot

    async def rebuild_snapshot(
        self,
        *,
        conversation_id: int,
        conversation: AgentConversation,
    ) -> dict[str, Any] | None:
        context_config = (
            getattr(getattr(conversation, "agent", None), "context_config", None) or {}
        )
        max_chars = int(context_config.get("compact_max_summary_chars", 1600) or 1600)

        total_messages = await self._message_repo.count_by_conversation(conversation_id)
        messages = await self._load_chat_history(
            conversation_id=conversation_id,
            max_messages=max(total_messages, 1),
            max_tokens=0,
        )
        if not messages:
            return None

        summary = ConversationContextEngine._build_compact_summary(
            messages,
            max_chars=max_chars,
        )
        if not summary:
            return None

        source_messages = [
            message for message in messages if message.role in {"user", "assistant"}
        ]
        return await self._upsert_snapshot(
            conversation_id,
            summary=summary,
            source_message_count=len(source_messages),
            source_token_estimate=sum(
                estimate_tokens(message.content or "") for message in source_messages
            ),
        )


__all__ = ["ConversationCompactionService"]
