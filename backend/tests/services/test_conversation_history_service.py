from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.ai.types import ChatMessage
from app.services.ai.conversation_history_service import ConversationHistoryService


@pytest.mark.asyncio
async def test_load_chat_history_uses_default_limit_and_sanitizes_tool_messages():
    message_repo = MagicMock()
    message_repo.get_last_n_messages = AsyncMock(return_value=["db-message"])

    read_model_service = MagicMock()
    read_model_service.build_chat_history_messages.return_value = [
        ChatMessage(role="assistant", content="hello"),
    ]

    service = ConversationHistoryService(
        message_repo=message_repo,
        read_model_service=read_model_service,
        default_max_messages=50,
    )

    messages = await service.load_chat_history(
        conversation_id=123,
        max_messages=0,
        max_tokens=120,
    )

    assert len(messages) == 1
    assert messages[0].role == "assistant"
    message_repo.get_last_n_messages.assert_awaited_once_with(
        conversation_id=123,
        n=50,
    )
    read_model_service.build_chat_history_messages.assert_called_once_with(
        ["db-message"],
        max_tokens=120,
    )
