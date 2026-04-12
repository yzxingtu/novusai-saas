"""
Conversation memory state helpers.
"""

from __future__ import annotations

from typing import Any

from app.services.ai.session_memory_service import SessionMemoryService


class ConversationMemoryStateService:
    """Command helpers for conversation memory state."""

    def __init__(self, *, memory_tenant_id: int) -> None:
        self._memory_tenant_id = memory_tenant_id

    def _memory_service(self) -> SessionMemoryService:
        if not hasattr(self, "_memory_service_instance"):
            self._memory_service_instance = SessionMemoryService(self._memory_tenant_id)
        return self._memory_service_instance

    async def get_state(self, conversation_id: int) -> dict[str, Any]:
        return await self._memory_service().get_conversation_memory_state(
            conversation_id
        )

    async def clear_state(self, conversation_id: int) -> int:
        return await self._memory_service().clear_conversation_memory(conversation_id)

    async def clear_state_safe(
        self,
        *,
        conversation_id: int,
        tenant_id: int | None,
        logger: Any,
        log_message: str,
    ) -> None:
        try:
            await self.clear_state(conversation_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                log_message,
                conversation_id,
                tenant_id,
                str(exc),
            )


__all__ = ["ConversationMemoryStateService"]
