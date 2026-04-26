"""
Test type: behavioral
Regression for: BUG-2026-04-26-002
Original symptom: canonical user `/ai-chat` remained page-visible, but the
backend stream request still arrived without a top-level `page_session_id`, so
page-runtime tools could not join the same retained-route session identity.
Scope: user `/ai-chat` stream request assembly for canonical page-session
enrollment.
Real dependencies: PageContext normalization and
AgentChatStreamBootstrapService.build_conversation_stream_request.
Mocked dependencies: none; the test uses a lightweight agent namespace only to
provide `quota_config` to the real bootstrap service.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.ai.types import ChatMessage
from app.schemas.ai.agent_chat import PageContext
from app.services.ai.agent_chat_stream_bootstrap_service import (
    AgentChatStreamBootstrapService,
)


def _canonical_user_page_context(
    *,
    page_session_id: str | None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "page_key": "user.ai.chat",
        "ui_epoch": 4,
    }
    if page_session_id is not None:
        payload["page_session_id"] = page_session_id
    return payload


async def _build_user_stream_request(
    *,
    page_context_session_id: str | None,
    top_level_page_session_id: str | None,
):
    service = AgentChatStreamBootstrapService(
        db=None,
        tenant_id=7,
    )
    variables = PageContext.normalize_variables(
        None,
        _canonical_user_page_context(page_session_id=page_context_session_id),
    )

    bundle = await service.build_conversation_stream_request(
        agent=SimpleNamespace(quota_config={}),
        agent_id=11,
        conversation_id=22,
        all_messages=[ChatMessage(role="user", content="read the current page")],
        variables=variables,
        knowledge_base_ids=None,
        dropped_knowledge_base_ids=[],
        consented_actions=None,
        user_role="tenant_user",
        user_role_id=101,
        permissions={"ai.chat"},
        billing_context={"user_id": 303},
        normalized_scene="conversation",
        normalized_channel="chat",
        normalized_source="ai.chat",
        memory_enabled=False,
        trust_policy_ref=None,
        interaction_mode="trusted_auto",
        page_session_id=top_level_page_session_id,
        interaction_updates=None,
        long_term_memory_enabled=False,
        session_memory_text="",
    )
    return variables, bundle.request


@pytest.mark.asyncio
async def test_user_ai_chat_stream_request_keeps_explicit_top_level_page_session_id() -> (
    None
):
    variables, request = await _build_user_stream_request(
        page_context_session_id="user-page-session-1",
        top_level_page_session_id="user-page-session-1",
    )

    assert variables == {
        "page_context": {
            "page_key": "user.ai.chat",
            "page_session_id": "user-page-session-1",
            "surface_stack": [],
            "ui_epoch": 4,
        }
    }
    assert request.page_session_id == "user-page-session-1"


@pytest.mark.asyncio
async def test_user_ai_chat_stream_request_promotes_page_context_session_id_to_request() -> (
    None
):
    variables, request = await _build_user_stream_request(
        page_context_session_id="user-page-session-1",
        top_level_page_session_id=None,
    )

    assert variables == {
        "page_context": {
            "page_key": "user.ai.chat",
            "page_session_id": "user-page-session-1",
            "surface_stack": [],
            "ui_epoch": 4,
        }
    }
    assert request.input_variables == variables
    assert request.page_session_id == "user-page-session-1"


@pytest.mark.asyncio
async def test_user_ai_chat_stream_request_trims_page_context_session_id_before_promotion() -> (
    None
):
    variables, request = await _build_user_stream_request(
        page_context_session_id="  user-page-session-typed  ",
        top_level_page_session_id=None,
    )

    assert variables == {
        "page_context": {
            "page_key": "user.ai.chat",
            "page_session_id": "user-page-session-typed",
            "surface_stack": [],
            "ui_epoch": 4,
        }
    }
    assert request.input_variables == variables
    assert request.page_session_id == "user-page-session-typed"
