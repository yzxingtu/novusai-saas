"""中文: AI 测试模块分类标记。

EN: AI test module classification marker.

Test type: structural / behavioral
Scope: Existing AI tests in this module; no real-dialogue smoke acceptance is claimed.
"""

from __future__ import annotations

from types import SimpleNamespace

from app.ai.engine.llm_call_helpers import (
    LLMCallContext,
    apply_llm_response_metadata,
)
from app.ai.types import ChatMessage, ChatResponse


def _build_agent() -> SimpleNamespace:
    return SimpleNamespace(
        id=7,
        temperature=0.3,
        max_tokens=256,
        top_p=0.8,
        model=SimpleNamespace(
            code="gpt-5.4",
            provider=SimpleNamespace(code="openai"),
            supports_vision=False,
            supports_audio=False,
            supports_video=False,
        ),
    )


def test_apply_llm_response_metadata_merges_route_fields_without_losing_existing_metadata() -> (
    None
):
    response = ChatResponse(
        message=ChatMessage(role="assistant", content="done"),
        metadata={"protocol_path": "responses"},
    )

    enriched = apply_llm_response_metadata(
        response,
        llm_call_context=LLMCallContext(
            provider_code="openai",
            model_code="gpt-5.4",
            routed_model_id=42,
            route_reason="tenant_override",
            supports_vision=True,
            supports_audio=False,
            supports_video=False,
        ),
    )

    assert enriched.metadata == {
        "protocol_path": "responses",
        "routed_model_id": 42,
        "route_reason": "tenant_override",
    }
