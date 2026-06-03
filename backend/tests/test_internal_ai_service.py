from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.ai.types import ChatMessage


@pytest.mark.asyncio
async def test_internal_ai_service_chat_routes_directly_to_gateway():
    from app.ai.internal_ai_service import InternalAIService

    response = SimpleNamespace(message="ok")
    db = MagicMock()

    with patch("app.ai.internal_ai_service.AIGateway") as gateway_cls:
        gateway = gateway_cls.return_value
        gateway.chat = AsyncMock(return_value=response)

        service = InternalAIService(db)
        result = await service.chat(
            provider_code="openai_compatible",
            messages=[ChatMessage(role="user", content="hello")],
            model="gpt-test",
            tenant_id=1,
            user_id=2,
            user_type="tenant_admin",
        )

    assert result is response
    gateway.chat.assert_awaited_once()


@pytest.mark.asyncio
async def test_internal_ai_service_embedding_routes_directly_to_gateway():
    from app.ai.internal_ai_service import InternalAIService

    response = SimpleNamespace(embeddings=[[0.1, 0.2]])
    db = MagicMock()

    with patch("app.ai.internal_ai_service.AIGateway") as gateway_cls:
        gateway = gateway_cls.return_value
        gateway.embedding = AsyncMock(return_value=response)

        service = InternalAIService(db)
        result = await service.embedding(
            provider_code="openai_compatible",
            texts=["hello"],
            model="text-embedding-test",
            tenant_id=0,
            user_id=7,
            user_type="admin",
        )

    assert result is response
    gateway.embedding.assert_awaited_once()
