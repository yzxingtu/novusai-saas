from __future__ import annotations

from unittest.mock import AsyncMock

import pytest


@pytest.mark.asyncio
async def test_sanitize_client_knowledge_base_ids_drops_unbound_cross_tenant_kb():
    from app.services.ai.agent_chat_query_service import AgentChatQueryService

    service = AgentChatQueryService(db=AsyncMock(), tenant_id=7)

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "app.ai.rag_injector.load_agent_kb_bindings",
            AsyncMock(return_value=([101], {101: 1.0})),
        )
        filtered, dropped = await service.sanitize_client_knowledge_base_ids(
            agent_id=59,
            knowledge_base_ids=[101, 202],
        )

    assert filtered == [101]
    assert dropped == [202]
