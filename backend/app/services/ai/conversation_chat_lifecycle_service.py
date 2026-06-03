"""Chat conversation lifecycle helpers."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from app.configs.service import PLATFORM_TENANT_ID
from app.core.i18n import _
from app.core.logging import LogManager
from app.enums.agent import ConversationStatusEnum
from app.exceptions import BusinessException

logger = LogManager.get_logger("ai.conversation_chat_lifecycle_service")


class ConversationChatLifecycleService:
    """Encapsulates resume-or-create rules for chat execution."""

    def __init__(
        self,
        *,
        repo: Any,
        tenant_id: int | None,
        get_accessible_conversation: Callable[..., Awaitable[Any]],
        max_title_length: int,
    ) -> None:
        self.repo = repo
        self.tenant_id = tenant_id
        self.get_accessible_conversation = get_accessible_conversation
        self.max_title_length = max_title_length

    async def get_or_create_for_chat(
        self,
        *,
        agent_id: int,
        conversation_id: int | None,
        user_id: int | None,
        owner_type: str,
        first_message: str,
    ) -> Any:
        """Returns a resumable conversation or creates a fresh one."""
        if conversation_id:
            conversation = await self.get_accessible_conversation(
                conversation_id,
                user_id=(user_id if self.tenant_id != PLATFORM_TENANT_ID else None),
                owner_type=owner_type,
            )

            if conversation.status == ConversationStatusEnum.ARCHIVED.value:
                raise BusinessException(
                    message=_("agent_chat.error.conversation_archived"),
                )

            if conversation.agent_id != agent_id:
                raise BusinessException(
                    message=_("agent_chat.error.conversation_agent_mismatch"),
                )

            return conversation

        title = first_message[: self.max_title_length].strip()
        conversation = await self.repo.create(
            {
                "tenant_id": self.tenant_id,
                "agent_id": agent_id,
                "user_id": user_id,
                "owner_type": owner_type,
                "title": title,
                "status": ConversationStatusEnum.ACTIVE.value,
                "token_count": 0,
                "cost": 0,
            }
        )

        logger.info(
            "Conversation created: id={} agent={} tenant={}",
            conversation.id,
            agent_id,
            self.tenant_id,
        )
        return conversation
