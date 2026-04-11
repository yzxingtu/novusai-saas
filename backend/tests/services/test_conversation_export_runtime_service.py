from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.ai.conversation_export_runtime_service import (
    ConversationExportRuntimeService,
)
from app.services.ai.conversation_service import ConversationService


@pytest.mark.asyncio
async def test_conversation_service_export_delegates_to_export_runtime_service(mock_db):
    service = ConversationService.__new__(ConversationService)
    service.db = mock_db
    service.tenant_id = 1
    conversation = SimpleNamespace(id=10, title="demo")
    service.repo = AsyncMock()
    service.repo.get_by_id = AsyncMock(return_value=conversation)
    service._export_runtime_service = MagicMock()
    service._export_runtime_service.export_conversation = AsyncMock(
        return_value={"content": "{}", "filename": "demo.json", "format": "json"}
    )

    result = await service.export_conversation(10, export_format="json")

    assert result["filename"] == "demo.json"
    service._export_runtime_service.export_conversation.assert_awaited_once_with(
        conversation=conversation,
        export_format="json",
    )


@pytest.mark.asyncio
async def test_conversation_export_runtime_service_loads_all_batches_and_serializes(
    mock_db,
):
    message_repo = MagicMock()
    first_batch = [SimpleNamespace(id=1)] * 1000
    second_batch = [SimpleNamespace(id=1001)]
    message_repo.get_by_conversation = AsyncMock(
        side_effect=[first_batch, second_batch]
    )
    message_repo.count_by_conversation = AsyncMock(return_value=1001)

    read_model_service = MagicMock()
    read_model_service.serialize_export_messages = AsyncMock(
        return_value=[
            {
                "role": "assistant",
                "content": "done",
                "token_count": 12,
                "tool_calls": None,
                "tool_call_id": None,
                "agent_id": 5,
                "agent_name": "router",
                "agent_avatar": None,
                "created_at": None,
                "metadata": None,
            }
        ]
    )

    service = ConversationExportRuntimeService(
        message_repo=message_repo,
        read_model_service=read_model_service,
    )

    result = await service.export_conversation(
        conversation=SimpleNamespace(
            id=22,
            title="Case 22",
            status="active",
            token_count=77,
            created_at=None,
        ),
        export_format="json",
    )

    payload = json.loads(result["content"])

    assert result["filename"] == "Case 22.json"
    assert result["total_message_count"] == 1001
    assert payload["messages"][0]["agent_name"] == "router"
    assert message_repo.get_by_conversation.await_args_list[0].kwargs == {
        "conversation_id": 22,
        "skip": 0,
        "limit": 1000,
    }
    assert message_repo.get_by_conversation.await_args_list[1].kwargs == {
        "conversation_id": 22,
        "skip": 1000,
        "limit": 1000,
    }

