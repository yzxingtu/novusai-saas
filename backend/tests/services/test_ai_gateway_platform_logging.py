from __future__ import annotations

import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.ai.types import ChatMessage, ChatResponse
from app.ai.utils.token_estimator import estimate_tokens
from app.configs.service import PLATFORM_TENANT_ID
from app.core.config import settings
from app.enums.log import UserTypeEnum as LogUserTypeEnum
from app.middleware.trace import trace_id_var


@pytest.mark.asyncio
async def test_chat_logs_platform_admin_calls_when_tenant_id_is_zero(mock_db):
    from app.ai.gateway import AIGateway

    gateway = AIGateway.__new__(AIGateway)
    gateway.db = mock_db
    gateway.provider_repo = MagicMock()
    gateway.api_key_repo = MagicMock()
    gateway.model_repo = MagicMock()
    gateway.failover = MagicMock()
    gateway.get_provider_and_key = AsyncMock(
        return_value=(
            SimpleNamespace(id=11),
            SimpleNamespace(id=22),
        )
    )
    gateway._get_model = AsyncMock(return_value=SimpleNamespace(id=33))
    gateway.retry_service = MagicMock()
    used_api_key = SimpleNamespace(increment_usage=MagicMock())
    response = ChatResponse(
        message=ChatMessage(role="assistant", content="ok"),
        input_tokens=12,
        output_tokens=8,
        total_tokens=20,
    )
    gateway.retry_service.execute_with_retry = AsyncMock(
        return_value=(response, 0, used_api_key)
    )
    gateway.usage_recorder = MagicMock()
    gateway.usage_recorder.check_rate_and_quota = AsyncMock()
    gateway.usage_recorder.record_usage_and_adjust = AsyncMock()
    gateway.usage_recorder.log_call_failure = AsyncMock()
    gateway.usage_recorder.call_log_service = MagicMock()
    gateway.usage_recorder.call_log_service.log_call_async = AsyncMock()

    with (
        patch("app.ai.gateway.CostCalculator.calculate_cost", return_value=0.123),
        patch(
            "app.ai.gateway.UsageRecorder.serialize_response",
            return_value={"content": "ok"},
        ),
    ):
        result = await gateway.chat(
            provider_code="openai_compatible",
            messages=[ChatMessage(role="user", content="hello")],
            model="gpt-test",
            tenant_id=PLATFORM_TENANT_ID,
            user_id=7,
        )

    assert result is response
    gateway.usage_recorder.check_rate_and_quota.assert_not_awaited()
    gateway.usage_recorder.record_usage_and_adjust.assert_not_awaited()
    gateway.usage_recorder.call_log_service.log_call_async.assert_awaited_once()
    kwargs = gateway.usage_recorder.call_log_service.log_call_async.await_args.kwargs
    assert kwargs["tenant_id"] == PLATFORM_TENANT_ID
    assert kwargs["user_id"] == 7
    assert kwargs["user_type"] == LogUserTypeEnum.ADMIN.value
    used_api_key.increment_usage.assert_called_once()


@pytest.mark.asyncio
async def test_chat_no_key_increment_when_metering_fails(mock_db):
    """企业租户计量失败时不应增加 Key、不应 commit。"""
    from app.ai.gateway import AIGateway

    tenant_id = PLATFORM_TENANT_ID + 1

    gateway = AIGateway.__new__(AIGateway)
    gateway.db = mock_db
    gateway.provider_repo = MagicMock()
    gateway.api_key_repo = MagicMock()
    gateway.model_repo = MagicMock()
    gateway.failover = MagicMock()
    gateway.get_provider_and_key = AsyncMock(
        return_value=(
            SimpleNamespace(id=11),
            SimpleNamespace(id=22),
        )
    )
    gateway._get_model = AsyncMock(return_value=SimpleNamespace(id=33))
    gateway.retry_service = MagicMock()
    used_api_key = SimpleNamespace(increment_usage=MagicMock())
    response = ChatResponse(
        message=ChatMessage(role="assistant", content="ok"),
        input_tokens=12,
        output_tokens=8,
        total_tokens=20,
    )
    gateway.retry_service.execute_with_retry = AsyncMock(
        return_value=(response, 0, used_api_key)
    )
    gateway.usage_recorder = MagicMock()
    gateway.usage_recorder.check_rate_and_quota = AsyncMock()
    gateway.usage_recorder.record_usage_and_adjust = AsyncMock(
        side_effect=RuntimeError("metering failed"),
    )
    gateway.usage_recorder.log_call_failure = AsyncMock()
    gateway.usage_recorder.call_log_service = MagicMock()
    gateway.usage_recorder.call_log_service.log_call_async = AsyncMock()

    with (
        patch("app.ai.gateway.CostCalculator.calculate_cost", return_value=0.123),
        patch(
            "app.ai.gateway.UsageRecorder.serialize_response",
            return_value={"content": "ok"},
        ),
        pytest.raises(RuntimeError, match="metering failed"),
    ):
        await gateway.chat(
            provider_code="openai_compatible",
            messages=[ChatMessage(role="user", content="hello")],
            model="gpt-test",
            tenant_id=tenant_id,
            user_id=7,
        )

    used_api_key.increment_usage.assert_not_called()
    gateway.usage_recorder.call_log_service.log_call_async.assert_not_awaited()
    mock_db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_on_stream_complete_logs_platform_admin_calls_without_metering(mock_db):
    from app.ai.usage_recorder import UsageRecorder

    recorder = UsageRecorder.__new__(UsageRecorder)
    recorder.db = mock_db
    recorder.call_log_service = MagicMock()
    recorder.call_log_service.log_call_async = AsyncMock()
    recorder.record_usage_and_adjust = AsyncMock()

    api_key = SimpleNamespace(increment_usage=MagicMock())
    provider = SimpleNamespace(id=11)

    await recorder.on_stream_complete(
        provider=provider,
        api_key=api_key,
        model="gpt-test",
        input_tokens=5,
        output_tokens=9,
        total_tokens=14,
        cost=0.12,
        tenant_id=PLATFORM_TENANT_ID,
        user_id=8,
    )

    recorder.record_usage_and_adjust.assert_not_awaited()
    recorder.call_log_service.log_call_async.assert_awaited_once()
    kwargs = recorder.call_log_service.log_call_async.await_args.kwargs
    assert kwargs["tenant_id"] == PLATFORM_TENANT_ID
    assert kwargs["user_id"] == 8
    assert kwargs["user_type"] == LogUserTypeEnum.ADMIN.value
    mock_db.commit.assert_awaited()
    api_key.increment_usage.assert_called_once()


@pytest.mark.asyncio
async def test_on_stream_complete_no_key_increment_when_metering_fails(mock_db):
    """租户计量失败时不应增加 Key、不应 commit（与 gateway.chat 一致）。"""
    from app.ai.usage_recorder import UsageRecorder

    tenant_id = PLATFORM_TENANT_ID + 1

    recorder = UsageRecorder.__new__(UsageRecorder)
    recorder.db = mock_db
    recorder.call_log_service = MagicMock()
    recorder.call_log_service.log_call_async = AsyncMock()
    recorder.record_usage_and_adjust = AsyncMock(
        side_effect=RuntimeError("metering db error"),
    )

    api_key = SimpleNamespace(increment_usage=MagicMock())
    provider = SimpleNamespace(id=11)

    with pytest.raises(RuntimeError, match="metering db error"):
        await recorder.on_stream_complete(
            provider=provider,
            api_key=api_key,
            model="gpt-test",
            input_tokens=5,
            output_tokens=9,
            total_tokens=14,
            cost=0.12,
            tenant_id=tenant_id,
            user_id=8,
            model_id=99,
            estimated_input=10,
        )

    api_key.increment_usage.assert_not_called()
    recorder.call_log_service.log_call_async.assert_not_awaited()
    mock_db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_log_call_failure_logs_platform_admin_calls(mock_db):
    from app.ai.usage_recorder import UsageRecorder

    recorder = UsageRecorder.__new__(UsageRecorder)
    recorder.db = mock_db
    recorder.call_log_service = MagicMock()
    recorder.call_log_service.log_call_async = AsyncMock()

    await recorder.log_call_failure(
        error=RuntimeError("boom"),
        start_time=time.time() - 1,
        provider=SimpleNamespace(id=44),
        model="gpt-test",
        model_id=55,
        messages=[ChatMessage(role="user", content="hello")],
        temperature=0.7,
        max_tokens=256,
        top_p=1.0,
        tools=None,
        request_type="chat",
        tenant_id=PLATFORM_TENANT_ID,
        user_id=9,
    )

    recorder.call_log_service.log_call_async.assert_awaited_once()
    kwargs = recorder.call_log_service.log_call_async.await_args.kwargs
    assert kwargs["tenant_id"] == PLATFORM_TENANT_ID
    assert kwargs["user_id"] == 9
    assert kwargs["user_type"] == LogUserTypeEnum.ADMIN.value


@pytest.mark.asyncio
async def test_conversation_engine_stream_logs_platform_admin_calls_without_metering(
    mock_db,
):
    from app.ai.engine.conversation import ConversationEngine
    from app.ai.types import ChatChunk

    provider = SimpleNamespace(
        id=11,
        code="provider_1",
        type="openai_compatible",
        base_url="https://example.com/v1",
        config={},
    )
    api_key = SimpleNamespace(
        decrypt_key=MagicMock(return_value="sk-test"),
        increment_usage=MagicMock(),
    )
    model = SimpleNamespace(
        id=33,
        provider=provider,
        code="gpt-5.4-xhigh",
        supports_vision=False,
        supports_audio=False,
        supports_video=False,
        supports_streaming=True,
    )
    agent = SimpleNamespace(
        model=model,
        temperature=0.7,
        max_tokens=256,
        top_p=1.0,
    )

    async def fake_stream_chat(**kwargs):
        _ = kwargs
        yield ChatChunk(delta="hi")
        yield ChatChunk(
            delta="",
            finish_reason="stop",
            input_tokens=12,
            output_tokens=8,
            total_tokens=20,
        )

    gateway = MagicMock()
    gateway.get_provider_and_key = AsyncMock(return_value=(provider, api_key))
    gateway.usage_recorder = MagicMock()
    gateway.usage_recorder.check_rate_and_quota = AsyncMock()
    gateway.usage_recorder.record_usage_and_adjust = AsyncMock()
    gateway.usage_recorder.call_log_service = MagicMock()
    gateway.usage_recorder.call_log_service.log_call_async = AsyncMock()

    engine = ConversationEngine(db=mock_db, gateway=gateway, sandbox=MagicMock())

    with (
        patch(
            "app.ai.engine.conversation.AdapterRegistry.create_adapter",
            return_value=SimpleNamespace(stream_chat=fake_stream_chat),
        ),
        patch(
            "app.ai.engine.conversation.CostCalculator.calculate_cost",
            return_value=0.123,
        ),
    ):
        chunks = [
            chunk
            async for chunk in engine._stream_llm_chunks(
                agent=agent,
                messages=[ChatMessage(role="user", content="hello")],
                tenant_id=PLATFORM_TENANT_ID,
                user_id=7,
            )
        ]

    assert [chunk.delta for chunk in chunks] == ["hi", ""]
    gateway.usage_recorder.check_rate_and_quota.assert_not_awaited()
    gateway.usage_recorder.record_usage_and_adjust.assert_not_awaited()
    gateway.usage_recorder.call_log_service.log_call_async.assert_awaited_once()
    kwargs = gateway.usage_recorder.call_log_service.log_call_async.await_args.kwargs
    assert kwargs["tenant_id"] == PLATFORM_TENANT_ID
    assert kwargs["model_id"] == 33
    assert kwargs["provider_id"] == 11
    assert kwargs["user_id"] == 7
    assert kwargs["user_type"] == LogUserTypeEnum.ADMIN.value
    assert kwargs["response_data"]["model"] == "gpt-5.4-xhigh"
    api_key.increment_usage.assert_called_once()
    mock_db.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_conversation_engine_stream_estimates_usage_when_provider_omits_tokens(
    mock_db,
):
    from app.ai.engine.conversation import ConversationEngine
    from app.ai.types import ChatChunk

    provider = SimpleNamespace(
        id=11,
        code="provider_1",
        type="openai_compatible",
        base_url="https://example.com/v1",
        config={},
        name="响应云",
    )
    api_key = SimpleNamespace(
        decrypt_key=MagicMock(return_value="sk-test"),
        increment_usage=MagicMock(),
    )
    model = SimpleNamespace(
        id=33,
        provider=provider,
        code="gpt-5.4-xhigh",
        name="gpt-5.4-xhigh",
        input_price_per_1k=0.02,
        output_price_per_1k=0.06,
        supports_vision=False,
        supports_audio=False,
        supports_video=False,
        supports_streaming=True,
    )
    agent = SimpleNamespace(
        id=59,
        model=model,
        temperature=0.7,
        max_tokens=256,
        top_p=1.0,
    )

    async def fake_stream_chat(**kwargs):
        _ = kwargs
        yield ChatChunk(delta="你好")
        yield ChatChunk(delta="", finish_reason="stop", metadata={"usage_mode": "estimated"})

    gateway = MagicMock()
    gateway.get_provider_and_key = AsyncMock(return_value=(provider, api_key))
    gateway.usage_recorder = MagicMock()
    gateway.usage_recorder.check_rate_and_quota = AsyncMock()
    gateway.usage_recorder.record_usage_and_adjust = AsyncMock()
    gateway.usage_recorder.call_log_service = MagicMock()
    gateway.usage_recorder.call_log_service.log_call_async = AsyncMock()
    gateway._merge_model_provider_snapshots = MagicMock(side_effect=lambda billing_context, **_: billing_context)

    engine = ConversationEngine(db=mock_db, gateway=gateway, sandbox=MagicMock())

    with patch(
        "app.ai.engine.conversation.AdapterRegistry.create_adapter",
        return_value=SimpleNamespace(stream_chat=fake_stream_chat),
    ):
        chunks = [
            chunk
            async for chunk in engine._stream_llm_chunks(
                agent=agent,
                messages=[ChatMessage(role="user", content="测试输入")],
                tenant_id=PLATFORM_TENANT_ID,
                user_id=7,
                conversation_id=454,
            )
        ]

    assert "".join(chunk.delta for chunk in chunks) == "你好"
    gateway.usage_recorder.call_log_service.log_call_async.assert_awaited_once()
    kwargs = gateway.usage_recorder.call_log_service.log_call_async.await_args.kwargs
    expected_output = estimate_tokens("你好")
    assert kwargs["input_tokens"] > 0
    assert kwargs["output_tokens"] == expected_output
    assert kwargs["total_tokens"] == kwargs["input_tokens"] + expected_output
    assert kwargs["response_data"]["usage_mode"] == "estimated"


@pytest.mark.asyncio
async def test_conversation_engine_stream_logs_failure_before_done(
    mock_db,
):
    from app.ai.engine.conversation import ConversationEngine

    provider = SimpleNamespace(
        id=11,
        code="provider_1",
        type="openai_compatible",
        base_url="https://example.com/v1",
        config={},
    )
    api_key = SimpleNamespace(
        decrypt_key=MagicMock(return_value="sk-test"),
        increment_usage=MagicMock(),
    )
    model = SimpleNamespace(
        id=33,
        provider=provider,
        code="gpt-5.4-xhigh",
        supports_vision=False,
        supports_audio=False,
        supports_video=False,
        supports_streaming=True,
    )
    agent = SimpleNamespace(
        id=59,
        model=model,
        temperature=0.7,
        max_tokens=256,
        top_p=1.0,
    )

    async def fake_stream_chat(**kwargs):
        _ = kwargs
        if False:
            yield None
        raise RuntimeError("upstream boom")

    gateway = MagicMock()
    gateway.get_provider_and_key = AsyncMock(return_value=(provider, api_key))
    gateway.usage_recorder = MagicMock()
    gateway.usage_recorder.check_rate_and_quota = AsyncMock()
    gateway.usage_recorder.record_usage_and_adjust = AsyncMock()
    gateway.usage_recorder.log_call_failure = AsyncMock()
    gateway.usage_recorder.call_log_service = MagicMock()
    gateway.usage_recorder.call_log_service.log_call_async = AsyncMock()

    engine = ConversationEngine(db=mock_db, gateway=gateway, sandbox=MagicMock())

    with (
        patch(
            "app.ai.engine.conversation.AdapterRegistry.create_adapter",
            return_value=SimpleNamespace(stream_chat=fake_stream_chat),
        ),
        pytest.raises(RuntimeError, match="upstream boom"),
    ):
        _ = [
            chunk
            async for chunk in engine._stream_llm_chunks(
                agent=agent,
                messages=[ChatMessage(role="user", content="hello")],
                tenant_id=PLATFORM_TENANT_ID,
                user_id=7,
                conversation_id=386,
            )
        ]

    gateway.usage_recorder.log_call_failure.assert_awaited_once()
    kwargs = gateway.usage_recorder.log_call_failure.await_args.kwargs
    assert kwargs["tenant_id"] == PLATFORM_TENANT_ID
    assert kwargs["user_id"] == 7
    assert kwargs["agent_id"] == 59
    assert kwargs["conversation_id"] == 386
    assert kwargs["model_id"] == 33
    assert kwargs["provider"] is provider
    gateway.usage_recorder.call_log_service.log_call_async.assert_not_awaited()
    gateway.usage_recorder.record_usage_and_adjust.assert_not_awaited()
    api_key.increment_usage.assert_not_called()
    mock_db.flush.assert_not_awaited()


@pytest.mark.asyncio
async def test_test_model_hides_generic_exception_in_production(mock_db):
    from app.ai.gateway import AIGateway

    gateway = AIGateway.__new__(AIGateway)
    gateway.db = mock_db
    gateway.provider_repo = MagicMock()
    gateway.api_key_repo = MagicMock()
    gateway.model_repo = MagicMock()

    provider = SimpleNamespace(
        id=11,
        code="provider_1",
        type="openai_compatible",
        base_url="https://example.com/v1",
        config={},
        is_active=True,
    )
    api_key = SimpleNamespace(
        id=22,
        decrypt_key=MagicMock(return_value="sk-test"),
        is_available=MagicMock(return_value=True),
    )
    gateway.provider_repo.get_by_id = AsyncMock(return_value=provider)
    gateway.api_key_repo.get_available_key = AsyncMock(return_value=api_key)
    gateway._get_model = AsyncMock(return_value=None)

    adapter = SimpleNamespace(
        chat=AsyncMock(side_effect=RuntimeError("upstream provider boom")),
    )
    original_debug = settings.DEBUG
    token = trace_id_var.set("trace-test-model-prod")
    settings.DEBUG = False
    try:
        with patch(
            "app.ai.gateway.AdapterRegistry.create_adapter",
            return_value=adapter,
        ):
            result = await gateway.test_model(
                provider_id=provider.id,
                model_code="gpt-test",
            )
    finally:
        settings.DEBUG = original_debug
        trace_id_var.reset(token)

    assert result.connected is False
    assert "upstream provider boom" not in (result.error or "")
    assert "trace-test-model-prod" in (result.error or "")
