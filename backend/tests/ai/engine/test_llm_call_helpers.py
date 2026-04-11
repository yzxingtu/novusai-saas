from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.ai.engine.llm_call_helpers import (
    LLMCallContext,
    apply_llm_response_metadata,
    prepare_llm_gateway_call,
)
from app.ai.engine.types import ToolUsePolicy
from app.ai.tools.types import ToolDefinition
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


@pytest.mark.asyncio
async def test_prepare_llm_gateway_call_builds_gateway_payload_and_prunes_unsupported_attachments() -> None:
    messages = [
        ChatMessage(
            role="user",
            content="hello",
            attachments=[
                {"type": "image", "url": "https://example.com/image.png"},
                {"type": "audio", "url": "https://example.com/audio.mp3"},
                {"type": "file", "url": "https://example.com/file.txt"},
            ],
        )
    ]
    tools = [ToolDefinition(name="web_search", description="Search web")]

    prepared = await prepare_llm_gateway_call(
        db=SimpleNamespace(),
        agent=_build_agent(),
        messages=messages,
        tools=tools,
        all_tool_names=None,
        tool_use_policy=ToolUsePolicy(
            family="web_research",
            mode="required",
            allowed_tool_names=["web_search"],
            retry_on_contract_breach=False,
            reason="explicit",
        ),
        breach_retry_result="contract_retry",
        tenant_id=1,
        user_id=2,
        conversation_id=3,
        billing_context={"scene": "chat"},
        route_result=None,
        log_user_type="tenant_admin",
    )

    assert prepared.llm_call_context == LLMCallContext(
        provider_code="openai",
        model_code="gpt-5.4",
        routed_model_id=None,
        route_reason=None,
        supports_vision=False,
        supports_audio=False,
        supports_video=False,
    )
    assert prepared.gateway_kwargs["provider_code"] == "openai"
    assert prepared.gateway_kwargs["model"] == "gpt-5.4"
    assert prepared.gateway_kwargs["tool_choice"] == "required"
    assert prepared.gateway_kwargs["all_tool_names"] == ["web_search"]
    assert prepared.gateway_kwargs["tool_use_policy_family"] == "web_research"
    assert prepared.gateway_kwargs["tool_use_policy_mode"] == "required"
    assert prepared.gateway_kwargs["breach_retry_result"] == "contract_retry"
    assert prepared.gateway_kwargs["supports_vision"] is False
    assert prepared.gateway_kwargs["supports_audio"] is False
    assert prepared.gateway_kwargs["supports_video"] is False
    assert messages[0].attachments == [
        {"type": "image", "url": "https://example.com/image.png"},
        {"type": "audio", "url": "https://example.com/audio.mp3"},
        {"type": "file", "url": "https://example.com/file.txt"},
    ]
    sanitized_messages = prepared.gateway_kwargs["messages"]
    assert sanitized_messages[0].attachments == [
        {"type": "file", "url": "https://example.com/file.txt"}
    ]


def test_apply_llm_response_metadata_merges_route_fields_without_losing_existing_metadata() -> None:
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
