"""
Legacy conversation-session memory shim.
"""

from __future__ import annotations

from typing import Any

from app.core.logging import LogManager
from app.services.ai.conversation_memory_state_service import (
    ConversationMemoryStateService,
)

logger = LogManager.get_logger("ai.conversation_service")


class SessionMemoryService:
    """Legacy shim kept for conversation-service patch compatibility."""

    def __init__(self, memory_tenant_id: int):
        self._service = ConversationMemoryStateService(memory_tenant_id=memory_tenant_id)

    async def get_conversation_memory_state(self, conversation_id: int) -> dict[str, Any]:
        return await self._service.get_state(conversation_id)

    async def clear_conversation_memory(self, conversation_id: int) -> int:
        return await self._service.clear_state(conversation_id)

    async def clear_conversation_memory_safe(self, conversation_id: int) -> None:
        try:
            await self._service.clear_state(conversation_id)
        except Exception as exc:  # pragma: no cover - best effort cleanup path
            logger.warning(
                "Conversation memory cleanup failed: conversation={} err={}",
                conversation_id,
                exc,
            )
