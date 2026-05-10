"""中文: AI gateway failover 能力约束测试。

EN: AI gateway failover capability requirement tests.

Test type: behavioral
Mock strategy: provider transport and failover service are mocked; gateway
request assembly and failover requirement calculation run real code.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.ai.exceptions import ProviderAuthError, ProviderConnectionError
from app.ai.gateway_support.chat_gateway import execute_chat
from app.ai.gateway_support.failover_orchestrator import (
    build_gateway_fallback_requirements,
    scrub_gateway_failover_runtime_kwargs,
)
from app.ai.gateway_support.stream_chat_gateway import execute_stream_chat
from app.ai.types import ChatMessage, ChatResponse


def _tool_payload(name: str) -> dict:
    return {"type": "function", "function": {"name": name, "parameters": {}}}


def test_build_gateway_fallback_requirements_detects_tools_media_and_context() -> None:
    messages = [
        ChatMessage(
            role="user",
            content="hello",
            attachments=[
                {"type": "image", "id": 1},
                {"type": "audio", "id": 2},
                {"type": "video", "id": 3},
            ],
        )
    ]

    requirements = build_gateway_fallback_requirements(
        messages=messages,
        tools=[_tool_payload("lookup_inventory")],
        estimated_input=128_000,
    )

    assert requirements == {
        "needs_audio": True,
        "needs_fc": True,
        "needs_video": True,
        "needs_vision": True,
        "min_context_window": 128_000,
    }


def test_failover_runtime_kwargs_drop_original_forced_protocol() -> None:
    """Test type: behavioral.

    中文: 模型 failover 不复用原模型的强制 wire_api，但保留 runtime guard。
    EN: Model failover does not reuse the original model's forced wire_api while
    preserving runtime guards.
    """

    sanitized = scrub_gateway_failover_runtime_kwargs(
        {
            "_runtime_force_protocol_path": "responses",
            "_runtime_force_wire_api": "responses",
            "_runtime_disable_cross_protocol_fallback": True,
            "_runtime_disable_sync_rescue": True,
            "timeout_seconds": 30,
        }
    )

    assert sanitized == {
        "_runtime_disable_cross_protocol_fallback": True,
        "_runtime_disable_sync_rescue": True,
        "timeout_seconds": 30,
    }


@pytest.mark.asyncio
async def test_chat_gateway_passes_tool_requirements_to_failover() -> None:
    provider = SimpleNamespace(
        id=10,
        code="provider_1",
        type="openai_compatible",
        base_url="https://example.test/v1",
        config={},
        name="Provider",
    )
    api_key = SimpleNamespace(id=20)
    ai_model = SimpleNamespace(id=30, code="gpt-primary", name="GPT Primary")
    failover = SimpleNamespace(
        record_provider_runtime_failure=AsyncMock(),
        get_fallback_model=AsyncMock(return_value=None),
    )
    gateway = SimpleNamespace(
        db=object(),
        get_provider_and_key=AsyncMock(return_value=(provider, api_key)),
        _get_model=AsyncMock(return_value=ai_model),
        _execute_with_retry=AsyncMock(side_effect=ProviderConnectionError("boom")),
        _call_chat_adapter=AsyncMock(),
        failover=failover,
        usage_recorder=SimpleNamespace(
            log_call_failure=AsyncMock(),
        ),
    )

    with pytest.raises(ProviderConnectionError):
        await execute_chat(
            gateway,
            provider_code="provider_1",
            messages=[
                ChatMessage(
                    role="user",
                    content="lookup this",
                    attachments=[{"type": "image", "id": 1}],
                )
            ],
            model="gpt-primary",
            tools=[_tool_payload("lookup_inventory")],
            adapter_registry=object(),
            token_counter=object(),
            cost_calculator=object(),
            usage_recorder_cls=object(),
            response_cache=object(),
            settings_obj=object(),
        )

    kwargs = failover.get_fallback_model.await_args.kwargs
    assert kwargs["needs_fc"] is True
    assert kwargs["needs_vision"] is True
    assert kwargs["needs_audio"] is False
    assert kwargs["needs_video"] is False
    assert kwargs["min_context_window"] > 0


@pytest.mark.asyncio
async def test_chat_gateway_scrubs_forced_protocol_when_calling_fallback_model() -> (
    None
):
    """Test type: behavioral.

    中文: fallback provider 必须用自身协议契约解析，不能继承原 turn 的 wire_api。
    EN: The fallback provider must resolve its own protocol contract instead of
    inheriting the original turn's wire_api.
    """

    provider = SimpleNamespace(
        id=10,
        code="provider_1",
        type="openai_compatible",
        base_url="https://example.test/v1",
        config={},
        name="Provider",
    )
    fallback_provider = SimpleNamespace(
        id=11,
        code="provider_2",
        type="openai_compatible",
        base_url="https://fallback.test/v1",
        config={},
        name="Fallback Provider",
    )
    api_key = SimpleNamespace(id=20)
    fallback_api_key = SimpleNamespace(id=21, increment_usage=MagicMock())
    ai_model = SimpleNamespace(
        id=30,
        code="gpt-primary",
        name="GPT Primary",
        config={},
    )
    fallback_model = SimpleNamespace(
        id=31,
        code="gpt-fallback",
        name="GPT Fallback",
        config={},
        provider=fallback_provider,
    )
    failover = SimpleNamespace(
        record_provider_runtime_failure=AsyncMock(),
        get_fallback_model=AsyncMock(return_value=fallback_model),
    )

    async def execute_with_retry(**kwargs):
        if kwargs["provider"].code == "provider_1":
            raise ProviderConnectionError("boom")
        response = await kwargs["call_fn"](object())
        return response, 0, kwargs["api_key"]

    gateway = SimpleNamespace(
        db=SimpleNamespace(commit=AsyncMock()),
        get_provider_and_key=AsyncMock(
            side_effect=[(provider, api_key), (fallback_provider, fallback_api_key)]
        ),
        _get_model=AsyncMock(return_value=ai_model),
        _execute_with_retry=execute_with_retry,
        _call_chat_adapter=AsyncMock(
            return_value=ChatResponse(
                message=ChatMessage(role="assistant", content="fallback ok"),
                metadata={},
            )
        ),
        failover=failover,
        usage_recorder=SimpleNamespace(
            log_call_failure=AsyncMock(),
        ),
    )

    response = await execute_chat(
        gateway,
        provider_code="provider_1",
        messages=[ChatMessage(role="user", content="hello")],
        model="gpt-primary",
        adapter_registry=object(),
        token_counter=object(),
        cost_calculator=SimpleNamespace(calculate_cost=MagicMock(return_value=0)),
        usage_recorder_cls=object(),
        response_cache=object(),
        settings_obj=object(),
        _runtime_force_wire_api="responses",
        _runtime_force_protocol_path="responses",
        _runtime_disable_cross_protocol_fallback=True,
        _runtime_disable_sync_rescue=True,
    )

    fallback_call = gateway._call_chat_adapter.await_args.kwargs
    assert response.message.content == "fallback ok"
    assert fallback_call["provider"].code == "provider_2"
    assert fallback_call["model"] == "gpt-fallback"
    assert fallback_call["extra_kwargs"] == {
        "_runtime_disable_cross_protocol_fallback": True,
        "_runtime_disable_sync_rescue": True,
    }


@pytest.mark.asyncio
async def test_stream_gateway_passes_tool_requirements_to_failover() -> None:
    provider = SimpleNamespace(
        id=10,
        code="provider_1",
        type="openai_compatible",
        base_url="https://example.test/v1",
        config={},
        name="Provider",
    )
    api_key = SimpleNamespace(id=20, decrypt_key=MagicMock(return_value="sk-test"))
    ai_model = SimpleNamespace(id=30, code="gpt-primary", name="GPT Primary")
    failover = SimpleNamespace(
        record_provider_runtime_failure=AsyncMock(),
        get_fallback_model=AsyncMock(return_value=None),
    )

    async def failing_stream(**_kwargs):
        if False:
            yield None
        raise ProviderAuthError("auth failed")

    gateway = SimpleNamespace(
        db=object(),
        get_provider_and_key=AsyncMock(return_value=(provider, api_key)),
        _get_model=AsyncMock(return_value=ai_model),
        _stream_chat_adapter=failing_stream,
        failover=failover,
        retry_service=SimpleNamespace(get_next_api_key=AsyncMock(return_value=None)),
        usage_recorder=SimpleNamespace(
            log_call_failure=AsyncMock(),
            on_stream_complete=AsyncMock(),
        ),
    )
    adapter_registry = SimpleNamespace(
        create_adapter=MagicMock(return_value=object()),
    )

    response = await execute_stream_chat(
        gateway,
        provider_code="provider_1",
        messages=[
            ChatMessage(
                role="user",
                content="lookup this",
                attachments=[
                    {"type": "audio", "id": 2},
                    {"type": "video", "id": 3},
                ],
            )
        ],
        model="gpt-primary",
        tools=[_tool_payload("lookup_inventory")],
        adapter_registry=adapter_registry,
        token_counter=object(),
        cost_calculator=object(),
    )
    chunks = []
    async for chunk in response.body_iterator:
        chunks.append(chunk)

    kwargs = failover.get_fallback_model.await_args.kwargs
    assert chunks
    assert kwargs["needs_fc"] is True
    assert kwargs["needs_vision"] is False
    assert kwargs["needs_audio"] is True
    assert kwargs["needs_video"] is True
    assert kwargs["min_context_window"] > 0
