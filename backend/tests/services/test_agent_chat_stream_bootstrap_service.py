"""
Test type: behavioral
Scope: AgentChatStreamBootstrapService stream request ownership mapping.
Real dependencies: ExecutionRequest construction and quota bundle creation.
Mocked dependencies: none.
"""

from types import SimpleNamespace

import pytest

from app.ai.types import ChatMessage
from app.services.ai.agent_chat_stream_bootstrap_service import (
    AgentChatStreamBootstrapService,
)


@pytest.mark.asyncio
async def test_stream_request_uses_actor_user_id_for_memory_scope() -> None:
    """Regression: stream billing context stores caller id as actor_user_id."""

    service = AgentChatStreamBootstrapService(db=None, tenant_id=0)

    bundle = await service.build_conversation_stream_request(
        agent=SimpleNamespace(quota_config={}),
        agent_id=59,
        conversation_id=2242,
        all_messages=[ChatMessage(role="user", content="请记住 我叫我妻善逸")],
        variables=None,
        knowledge_base_ids=None,
        dropped_knowledge_base_ids=[],
        consented_actions=None,
        user_role="admin",
        user_role_id=None,
        permissions=None,
        billing_context={
            "actor_user_id": 88,
            "actor_user_type": "admin",
            "access_channel": "admin_internal",
        },
        normalized_scene="admin_chat",
        normalized_channel="system",
        normalized_source="admin_chat",
        memory_enabled=True,
        trust_policy_ref=None,
        interaction_mode="trusted_auto",
        interaction_updates=None,
        long_term_memory_enabled=True,
        session_memory_text="",
    )

    assert bundle.request.user_id == 88
    assert bundle.request.conversation_id == 2242
    assert bundle.request.memory_enabled is True
    assert bundle.request.billing_context["actor_user_id"] == 88
