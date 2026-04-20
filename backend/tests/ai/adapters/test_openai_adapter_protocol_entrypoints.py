from __future__ import annotations

from collections.abc import AsyncIterator
from unittest.mock import AsyncMock

import pytest

import app.ai.adapters.openai_compatible.support.protocol_entrypoints as protocol_entrypoints_module
from app.ai.adapters.openai_adapter import OpenAIAdapter
from app.ai.types import ChatChunk, ChatMessage, ChatResponse


async def _iterate(chunks: list[ChatChunk]) -> AsyncIterator[ChatChunk]:
    for chunk in chunks:
        yield chunk


def _make_adapter(*, provider_config: dict | None = None) -> OpenAIAdapter:
    return OpenAIAdapter(
        api_key="test-key",
        base_url="https://api.openai.com/v1",
        provider_config=provider_config or {},
    )


@pytest.mark.asyncio
async def test_execute_protocol_chat_chat_completions_plan_never_routes_back_to_responses() -> (
    None
):
    adapter = _make_adapter()
    adapter._convert_messages = AsyncMock(
        return_value=[{"role": "user", "content": "hi"}]
    )  # type: ignore[method-assign]
    adapter._chat_via_responses = AsyncMock()  # type: ignore[method-assign]
    adapter._chat_via_chat_completions = AsyncMock(  # type: ignore[method-assign]
        return_value=ChatResponse(
            message=ChatMessage(role="assistant", content="ok"),
            metadata={},
        )
    )

    response = await adapter.execute_protocol_chat(
        wire_api="chat_completions",
        messages=[ChatMessage(role="user", content="hello")],
        model="gpt-5.4",
        _runtime_disable_cross_protocol_fallback=True,
        _runtime_disable_sync_rescue=True,
    )

    adapter._chat_via_chat_completions.assert_awaited_once()
    assert (
        adapter._chat_via_chat_completions.await_args.kwargs["fallback_to_responses"]
        is False
    )
    request_params = adapter._chat_via_chat_completions.await_args.kwargs[
        "request_params"
    ]
    assert "_runtime_disable_cross_protocol_fallback" not in request_params
    assert "_runtime_disable_sync_rescue" not in request_params
    adapter._chat_via_responses.assert_not_awaited()
    assert response.metadata["protocol_path"] == "chat_completions"


@pytest.mark.asyncio
async def test_execute_protocol_stream_chat_completions_plan_never_routes_back_to_responses_or_sync_rescue() -> (
    None
):
    adapter = _make_adapter()
    adapter._convert_messages = AsyncMock(
        return_value=[{"role": "user", "content": "hi"}]
    )  # type: ignore[method-assign]
    adapter._stream_chat_via_responses = AsyncMock()  # type: ignore[method-assign]
    adapter._chat_via_chat_completions = AsyncMock()  # type: ignore[method-assign]

    async def _fake_stream_chat_completions(**kwargs):
        assert kwargs["fallback_to_responses"] is False
        assert (
            "_runtime_disable_cross_protocol_fallback" not in kwargs["request_params"]
        )
        assert "_runtime_disable_sync_rescue" not in kwargs["request_params"]
        async for chunk in _iterate(
            [
                ChatChunk(delta="hello"),
                ChatChunk(delta="", finish_reason="stop"),
            ]
        ):
            yield chunk

    adapter._stream_chat_via_chat_completions = _fake_stream_chat_completions  # type: ignore[method-assign]

    chunks = [
        chunk
        async for chunk in adapter.execute_protocol_stream(
            wire_api="chat_completions",
            messages=[ChatMessage(role="user", content="hello")],
            model="gpt-5.4",
            _runtime_disable_cross_protocol_fallback=True,
            _runtime_disable_sync_rescue=True,
        )
    ]

    assert [chunk.delta for chunk in chunks] == ["hello", ""]
    adapter._stream_chat_via_responses.assert_not_awaited()
    adapter._chat_via_chat_completions.assert_not_awaited()


@pytest.mark.asyncio
async def test_execute_protocol_chat_responses_strips_runtime_protocol_guard_flags_before_provider_call() -> (
    None
):
    adapter = _make_adapter(
        provider_config={
            "wire_api": "responses",
            "protocol_capabilities": {
                "allowed_wire_apis": ["responses", "chat_completions"]
            },
        }
    )
    captured: dict[str, object] = {}
    adapter._chat_via_chat_completions = AsyncMock()  # type: ignore[method-assign]

    async def _fake_responses(**kwargs):
        captured.update(kwargs)
        return ChatResponse(
            message=ChatMessage(role="assistant", content="ok"),
            metadata={},
        )

    adapter._chat_via_responses = _fake_responses  # type: ignore[method-assign]

    response = await adapter.execute_protocol_chat(
        wire_api="responses",
        messages=[ChatMessage(role="user", content="hello")],
        model="gpt-5.4",
        _runtime_disable_cross_protocol_fallback=True,
        _runtime_disable_sync_rescue=True,
    )

    assert "_runtime_disable_cross_protocol_fallback" not in captured
    assert "_runtime_disable_sync_rescue" not in captured
    adapter._chat_via_chat_completions.assert_not_awaited()
    assert response.metadata["protocol_path"] == "responses"


@pytest.mark.asyncio
async def test_execute_protocol_chat_responses_only_provider_never_hits_chat_completions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = _make_adapter(
        provider_config={
            "wire_api": "responses",
            "protocol_capabilities": {"allowed_wire_apis": ["responses"]},
        }
    )
    adapter._chat_via_chat_completions = AsyncMock()  # type: ignore[method-assign]

    async def _failing_responses(**kwargs):
        _ = kwargs
        raise RuntimeError("responses 502")

    adapter._chat_via_responses = _failing_responses  # type: ignore[method-assign]
    monkeypatch.setattr(
        protocol_entrypoints_module,
        "convert_openai_error",
        lambda error, **kwargs: ValueError(f"converted:{kwargs['model_code']}:{error}"),
    )

    with pytest.raises(ValueError, match="converted:gpt-5.4:responses 502"):
        await adapter.execute_protocol_chat(
            wire_api="responses",
            messages=[ChatMessage(role="user", content="hello")],
            model="gpt-5.4",
        )

    adapter._chat_via_chat_completions.assert_not_awaited()


@pytest.mark.asyncio
async def test_execute_protocol_stream_responses_only_provider_never_hits_chat_completions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = _make_adapter(
        provider_config={
            "wire_api": "responses",
            "protocol_capabilities": {"allowed_wire_apis": ["responses"]},
        }
    )
    adapter._stream_chat_via_chat_completions = AsyncMock()  # type: ignore[method-assign]

    async def _failing_stream(**kwargs):
        _ = kwargs
        raise RuntimeError("responses stream 502")
        yield

    adapter._stream_chat_via_responses = _failing_stream  # type: ignore[method-assign]
    monkeypatch.setattr(
        protocol_entrypoints_module,
        "convert_openai_error",
        lambda error, **kwargs: ValueError(f"converted:{kwargs['model_code']}:{error}"),
    )

    with pytest.raises(ValueError, match="converted:gpt-5.4:responses stream 502"):
        async for _ in adapter.execute_protocol_stream(
            wire_api="responses",
            messages=[ChatMessage(role="user", content="hello")],
            model="gpt-5.4",
        ):
            pass

    adapter._stream_chat_via_chat_completions.assert_not_awaited()


@pytest.mark.asyncio
async def test_chat_protocol_safe_resolves_wire_api_before_delegating() -> None:
    adapter = _make_adapter(
        provider_config={
            "wire_api": "responses",
            "protocol_capabilities": {"allowed_wire_apis": ["responses"]},
        }
    )
    adapter.execute_protocol_chat = AsyncMock(  # type: ignore[method-assign]
        return_value=ChatResponse(
            message=ChatMessage(role="assistant", content="ok"),
            metadata={},
        )
    )

    response = await adapter.chat_protocol_safe(
        messages=[ChatMessage(role="user", content="hello")],
        model="gpt-5.4",
    )

    assert response.message.content == "ok"
    kwargs = adapter.execute_protocol_chat.await_args.kwargs
    assert kwargs["wire_api"] == "responses"
    assert kwargs["model"] == "gpt-5.4"


@pytest.mark.asyncio
async def test_stream_chat_protocol_safe_resolves_wire_api_before_delegating() -> None:
    adapter = _make_adapter(
        provider_config={
            "wire_api": "responses",
            "protocol_capabilities": {"allowed_wire_apis": ["responses"]},
        }
    )
    seen: list[dict[str, object]] = []

    async def _fake_protocol_stream(**kwargs):
        seen.append(kwargs)
        async for chunk in _iterate([ChatChunk(delta="hello")]):
            yield chunk

    adapter.execute_protocol_stream = _fake_protocol_stream  # type: ignore[method-assign]

    chunks = [
        chunk
        async for chunk in adapter.stream_chat_protocol_safe(
            messages=[ChatMessage(role="user", content="hello")],
            model="gpt-5.4",
        )
    ]

    assert [chunk.delta for chunk in chunks] == ["hello"]
    assert seen[0]["wire_api"] == "responses"
    assert seen[0]["model"] == "gpt-5.4"


@pytest.mark.asyncio
async def test_chat_public_entrypoint_defaults_to_protocol_safe_execution() -> None:
    adapter = _make_adapter()
    adapter.chat_protocol_safe = AsyncMock(  # type: ignore[method-assign]
        return_value=ChatResponse(
            message=ChatMessage(role="assistant", content="public ok"),
            metadata={},
        )
    )

    response = await adapter.chat(
        messages=[ChatMessage(role="user", content="hello")],
        model="gpt-5.4",
        stream=True,
        tools=[
            {"type": "function", "function": {"name": "fetch_url", "parameters": {}}}
        ],
        tool_choice="required",
    )

    assert response.message.content == "public ok"
    adapter.chat_protocol_safe.assert_awaited_once()
    kwargs = adapter.chat_protocol_safe.await_args.kwargs
    assert kwargs["model"] == "gpt-5.4"
    assert kwargs["tool_choice"] == "required"
    assert "stream" not in kwargs


@pytest.mark.asyncio
async def test_stream_chat_public_entrypoint_defaults_to_protocol_safe_execution() -> (
    None
):
    adapter = _make_adapter()
    seen: list[dict[str, object]] = []

    async def _fake_stream_chat_protocol_safe(**kwargs):
        seen.append(kwargs)
        async for chunk in _iterate([ChatChunk(delta="public stream")]):
            yield chunk

    adapter.stream_chat_protocol_safe = _fake_stream_chat_protocol_safe  # type: ignore[method-assign]

    chunks = [
        chunk
        async for chunk in adapter.stream_chat(
            messages=[ChatMessage(role="user", content="hello")],
            model="gpt-5.4",
            tools=[
                {
                    "type": "function",
                    "function": {"name": "fetch_url", "parameters": {}},
                }
            ],
            tool_choice="required",
        )
    ]

    assert [chunk.delta for chunk in chunks] == ["public stream"]
    assert seen[0]["model"] == "gpt-5.4"
    assert seen[0]["tool_choice"] == "required"


@pytest.mark.asyncio
async def test_chat_legacy_compat_entrypoint_remains_explicit() -> None:
    adapter = _make_adapter()
    captured: dict[str, object] = {}

    async def _fake_legacy_chat_entrypoint(**kwargs):
        captured.update(kwargs)
        return ChatResponse(
            message=ChatMessage(role="assistant", content="legacy ok"),
            metadata={},
        )

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(
        OpenAIAdapter,
        "_legacy_chat_entrypoint",
        staticmethod(lambda: _fake_legacy_chat_entrypoint),
    )
    try:
        response = await adapter.chat_legacy_compat(
            messages=[ChatMessage(role="user", content="hello")],
            model="gpt-5.4",
            stream=True,
        )
    finally:
        monkeypatch.undo()

    assert response.message.content == "legacy ok"
    assert captured["adapter"] is adapter
    assert captured["model"] == "gpt-5.4"


@pytest.mark.asyncio
async def test_stream_chat_legacy_compat_entrypoint_remains_explicit() -> None:
    adapter = _make_adapter()
    captured: dict[str, object] = {}

    async def _fake_legacy_stream_entrypoint(**kwargs):
        captured.update(kwargs)
        async for chunk in _iterate([ChatChunk(delta="legacy stream")]):
            yield chunk

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(
        OpenAIAdapter,
        "_legacy_stream_entrypoint",
        staticmethod(lambda: _fake_legacy_stream_entrypoint),
    )
    try:
        chunks = [
            chunk
            async for chunk in adapter.stream_chat_legacy_compat(
                messages=[ChatMessage(role="user", content="hello")],
                model="gpt-5.4",
            )
        ]
    finally:
        monkeypatch.undo()

    assert [chunk.delta for chunk in chunks] == ["legacy stream"]
    assert captured["adapter"] is adapter
    assert captured["model"] == "gpt-5.4"
