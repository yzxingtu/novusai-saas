from __future__ import annotations

from collections.abc import AsyncIterator
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.ai.gateway import AIGateway
from app.ai.types import ChatChunk, ChatMessage, ChatResponse


class _ProtocolCapabilities:
    @staticmethod
    def resolve_runtime_wire_api(wire_api: str | None) -> str:
        return wire_api or "responses"


class _OpenAIProtocolSafeAdapterStub:
    def __init__(self) -> None:
        self.protocol_capabilities = _ProtocolCapabilities()
        self.chat_calls: list[dict[str, object]] = []
        self.stream_calls: list[dict[str, object]] = []

    def resolve_protocol_safe_wire_api(self, *, wire_api=None) -> str:
        return self.protocol_capabilities.resolve_runtime_wire_api(wire_api)

    async def chat_protocol_safe(self, **kwargs) -> ChatResponse:
        self.chat_calls.append(kwargs)
        return ChatResponse(
            message=ChatMessage(role="assistant", content="ok"),
            metadata={},
        )

    async def stream_chat_protocol_safe(self, **kwargs) -> AsyncIterator[ChatChunk]:
        self.stream_calls.append(kwargs)
        yield ChatChunk(delta="chunk")

    async def chat(self, **kwargs) -> ChatResponse:
        _ = kwargs
        raise AssertionError("gateway should prefer chat_protocol_safe()")

    async def stream_chat(self, **kwargs) -> AsyncIterator[ChatChunk]:
        _ = kwargs
        raise AssertionError("gateway should prefer stream_chat_protocol_safe()")
        yield ChatChunk(delta="")


class _LegacyOnlyAdapterStub:
    def __init__(self) -> None:
        self.chat_calls: list[dict[str, object]] = []

    async def chat(self, **kwargs) -> ChatResponse:
        self.chat_calls.append(kwargs)
        return ChatResponse(
            message=ChatMessage(role="assistant", content="legacy"),
            metadata={},
        )


@pytest.mark.asyncio
async def test_gateway_call_chat_adapter_prefers_protocol_safe_openai_facade() -> None:
    gateway = AIGateway.__new__(AIGateway)
    adapter = _OpenAIProtocolSafeAdapterStub()
    provider = SimpleNamespace(
        type="openai_compatible", config={"wire_api": "responses"}
    )

    response = await gateway._call_chat_adapter(
        adapter=adapter,
        provider=provider,
        messages=[ChatMessage(role="user", content="hello")],
        model="gpt-5.4",
        temperature=0.2,
        max_tokens=128,
        top_p=0.9,
        stream=False,
        tools=None,
        tool_choice=None,
    )

    assert response.message.content == "ok"
    assert adapter.chat_calls
    assert adapter.chat_calls[0]["wire_api"] == "responses"


@pytest.mark.asyncio
async def test_gateway_stream_chat_adapter_prefers_protocol_safe_openai_facade() -> (
    None
):
    gateway = AIGateway.__new__(AIGateway)
    adapter = _OpenAIProtocolSafeAdapterStub()
    provider = SimpleNamespace(
        type="openai_compatible", config={"wire_api": "responses"}
    )

    chunks = [
        chunk
        async for chunk in gateway._stream_chat_adapter(
            adapter=adapter,
            provider=provider,
            messages=[ChatMessage(role="user", content="hello")],
            model="gpt-5.4",
            temperature=0.2,
            max_tokens=128,
            top_p=0.9,
            tools=None,
            tool_choice=None,
        )
    ]

    assert [chunk.delta for chunk in chunks] == ["chunk"]
    assert adapter.stream_calls
    assert adapter.stream_calls[0]["wire_api"] == "responses"


@pytest.mark.asyncio
async def test_gateway_call_chat_adapter_keeps_legacy_path_for_non_openai_provider() -> (
    None
):
    gateway = AIGateway.__new__(AIGateway)
    adapter = _LegacyOnlyAdapterStub()
    provider = SimpleNamespace(type="anthropic", config={})

    response = await gateway._call_chat_adapter(
        adapter=adapter,
        provider=provider,
        messages=[ChatMessage(role="user", content="hello")],
        model="claude-test",
        temperature=0.2,
        max_tokens=128,
        top_p=0.9,
        stream=False,
        tools=None,
        tool_choice=None,
    )

    assert response.message.content == "legacy"
    assert adapter.chat_calls
    assert adapter.chat_calls[0]["stream"] is False


@pytest.mark.asyncio
async def test_gateway_test_model_prefers_protocol_safe_openai_facade() -> None:
    gateway = AIGateway.__new__(AIGateway)
    gateway.db = MagicMock()
    gateway.provider_repo = MagicMock()
    gateway.api_key_repo = MagicMock()
    gateway.model_repo = MagicMock()

    provider = SimpleNamespace(
        id=11,
        code="provider_1",
        type="openai_compatible",
        base_url="https://example.com/v1",
        config={"wire_api": "responses"},
        is_active=True,
    )
    api_key = SimpleNamespace(
        id=22,
        decrypt_key=MagicMock(return_value="sk-test"),
        is_available=MagicMock(return_value=True),
    )
    adapter = _OpenAIProtocolSafeAdapterStub()

    gateway.provider_repo.get_by_id = AsyncMock(return_value=provider)
    gateway.api_key_repo.get_available_key = AsyncMock(return_value=api_key)
    gateway._get_model = AsyncMock(return_value=None)

    with patch(
        "app.ai.gateway.AdapterRegistry.create_adapter",
        return_value=adapter,
    ):
        result = await gateway.test_model(
            provider_id=provider.id,
            model_code="gpt-5.4",
        )

    assert result.connected is True
    assert result.response_text == "ok"
    assert adapter.chat_calls
    assert adapter.chat_calls[0]["wire_api"] == "responses"


@pytest.mark.asyncio
async def test_gateway_protocol_safe_bridge_preserves_runtime_force_wire_api_without_compat_strategy_flags() -> (
    None
):
    gateway = AIGateway.__new__(AIGateway)
    adapter = _OpenAIProtocolSafeAdapterStub()
    provider = SimpleNamespace(
        type="openai_compatible",
        config={"wire_api": "chat_completions"},
    )

    response = await gateway._call_chat_adapter(
        adapter=adapter,
        provider=provider,
        messages=[ChatMessage(role="user", content="hello")],
        model="gpt-5.4",
        temperature=0.2,
        max_tokens=128,
        top_p=0.9,
        stream=False,
        tools=None,
        tool_choice=None,
        extra_kwargs={
            "_runtime_force_wire_api": "responses",
            "_runtime_disable_cross_protocol_fallback": True,
            "_runtime_disable_sync_rescue": True,
        },
    )

    assert response.message.content == "ok"
    assert adapter.chat_calls
    call = adapter.chat_calls[0]
    assert call["wire_api"] == "responses"
    assert call["_runtime_disable_cross_protocol_fallback"] is True
    assert call["_runtime_disable_sync_rescue"] is True
    assert "fallback_to_responses" not in call
    assert "use_responses_api" not in call
    assert "fallback_switch_enabled" not in call
