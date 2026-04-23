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
    assert kwargs["call_type"] == "main_chat"
    request_data = kwargs["request_data"]
    assert request_data["selected_tool_names"] == []
    assert request_data["all_tool_names"] == []
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
    assert kwargs["call_type"] == "main_chat"
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
    assert kwargs["call_type"] == "main_chat"
    assert kwargs["error_message"] == "boom"


def test_build_request_log_data_records_selected_and_all_tool_names(mock_db):
    from app.ai.gateway import AIGateway

    gateway = AIGateway.__new__(AIGateway)
    gateway.db = mock_db

    payload = gateway._build_request_log_data(
        messages=[ChatMessage(role="user", content="hello")],
        temperature=0.7,
        max_tokens=256,
        top_p=1.0,
        tools=[
            {"type": "function", "function": {"name": "web_search"}},
            {"type": "function", "function": {"name": "fetch_url"}},
        ],
        tool_choice="auto",
        all_tool_names=[
            "ui_get_snapshot",
            "ui_click",
            "web_search",
            "fetch_url",
        ],
        tool_use_policy_family="web_research",
        tool_use_policy_mode="auto",
        allowed_tool_names=["ui_get_snapshot", "ui_click", "web_search", "fetch_url"],
    )

    assert payload["selected_tool_names"] == ["web_search", "fetch_url"]
    assert payload["all_tool_names"] == [
        "ui_get_snapshot",
        "ui_click",
        "web_search",
        "fetch_url",
    ]


def test_build_request_log_data_keeps_non_empty_selected_tools_with_mixed_inputs(
    mock_db,
):
    from app.ai.gateway import AIGateway

    gateway = AIGateway.__new__(AIGateway)
    gateway.db = mock_db

    payload = gateway._build_request_log_data(
        messages=[ChatMessage(role="user", content="hello")],
        temperature=0.7,
        max_tokens=128,
        top_p=1.0,
        tools=[
            {"type": "function", "function": {"name": "web_search"}},
            {"type": "function", "function": {}},
            {"type": "function"},
            "invalid-tool-entry",
        ],
        tool_choice="auto",
        all_tool_names=["web_search", "fetch_url", "ui_get_snapshot"],
    )

    assert payload["selected_tool_names"] == ["web_search"]
    assert len(payload["selected_tool_names"]) == 1
    assert payload["all_tool_names"] == ["web_search", "fetch_url", "ui_get_snapshot"]


def test_usage_recorder_turn_diagnostics_preserves_shadow_diff_payload() -> None:
    from app.ai.usage_recorder import UsageRecorder

    payload = UsageRecorder._inject_turn_diagnostics(
        {"selected_tool_names": []},
        status="success",
        default_termination_reason="completed",
        turn_record={
            "turn_outcome": "success",
            "termination_reason": "completed",
            "protocol_path": "shadow",
            "selected_tool_names": ["web_search", "fetch_url"],
            "selected_skill_names": ["Plugin Research Skill", "Plugin Research Skill"],
            "fallback_history": [
                {
                    "from_protocol": "responses",
                    "to_protocol": "chat_completions",
                    "reason": "stream_empty_no_output",
                    "recovered": True,
                    "metadata": {"recovery_path": "sync_chat_completions"},
                }
            ],
            "context_sources": [
                {
                    "kind": "page_context",
                    "name": "admin.runtime.records",
                    "active": True,
                    "metadata": {"page_key": "admin.runtime.records"},
                }
            ],
            "sync_rescue": True,
            "should_record_call_log": True,
            "metadata": {
                "shadow_diff": {
                    "selected_tool_names": {
                        "legacy": [],
                        "runtime_v2": ["web_search", "fetch_url"],
                    },
                    "protocol_path": {
                        "legacy": "chat_completions",
                        "runtime_v2": "responses",
                    },
                },
                "sync_rescue": True,
                "should_record_call_log": True,
            },
        },
        protocol_path="shadow",
        should_record_call_log=True,
    )

    diagnostics = payload["turn_diagnostics"]
    assert diagnostics["turn_outcome"] == "success"
    assert diagnostics["termination_reason"] == "completed"
    assert diagnostics["protocol_path"] == "shadow"
    assert diagnostics["selected_tool_names"] == ["web_search", "fetch_url"]
    assert diagnostics["selected_skill_names"] == ["Plugin Research Skill"]
    assert diagnostics["sync_rescue"] is True
    assert diagnostics["should_record_call_log"] is True
    assert diagnostics["fallback_history"] == [
        {
            "from_protocol": "responses",
            "to_protocol": "chat_completions",
            "reason": "stream_empty_no_output",
            "recovered": True,
            "metadata": {"recovery_path": "sync_chat_completions"},
        }
    ]
    assert payload["turn_record"]["metadata"]["shadow_diff"] == {
        "selected_tool_names": {
            "legacy": [],
            "runtime_v2": ["web_search", "fetch_url"],
        },
        "protocol_path": {
            "legacy": "chat_completions",
            "runtime_v2": "responses",
        },
    }
    assert payload["turn_record"]["metadata"]["sync_rescue"] is True
    assert payload["turn_record"]["metadata"]["should_record_call_log"] is True


def test_usage_recorder_should_record_call_log_for_platform_tenant() -> None:
    from app.ai.usage_recorder import UsageRecorder

    assert UsageRecorder._should_record_call_log(PLATFORM_TENANT_ID) is True
    assert UsageRecorder._should_record_call_log(PLATFORM_TENANT_ID + 1) is True
    assert UsageRecorder._should_record_call_log(None) is False


@pytest.mark.asyncio
async def test_call_log_service_log_call_async_injects_runtime_turn_fields(mock_db):
    from app.services.ai.call_log_service import CallLogService

    service = CallLogService(mock_db)

    with patch("app.tasks.ai.log_ai_call_task.delay") as delay_mock:
        await service.log_call_async(
            tenant_id=PLATFORM_TENANT_ID,
            model_id=33,
            provider_id=11,
            request_type="chat",
            request_data={"messages": [{"role": "user", "content": "hello"}]},
            response_data={"ok": True},
            input_tokens=10,
            output_tokens=5,
            total_tokens=15,
            cost=0.1,
            latency_ms=123,
            selected_tool_names=["web_search"],
            selected_skill_names=["Plugin Research Skill"],
            protocol_path="responses",
            context_sources=[
                {
                    "kind": "page_context",
                    "name": "admin.runtime.records",
                    "active": True,
                    "metadata": {"page_key": "admin.runtime.records"},
                }
            ],
            fallback_history=[
                {
                    "from_protocol": "responses",
                    "to_protocol": "chat_completions",
                    "reason": "stream_empty_no_output",
                    "recovered": True,
                    "metadata": {"recovery_path": "sync_chat_completions"},
                }
            ],
            sync_rescue=True,
            should_record_call_log=True,
        )

    delay_mock.assert_called_once()
    kwargs = delay_mock.call_args.kwargs
    request_payload = kwargs["request_data"]
    diagnostics = request_payload["turn_diagnostics"]

    assert kwargs["tenant_id"] == PLATFORM_TENANT_ID
    assert kwargs["call_type"] == "main_chat"
    assert "turn_record" not in kwargs
    assert "protocol_path" not in kwargs
    assert "context_sources" not in kwargs
    assert diagnostics["protocol_path"] == "responses"
    assert diagnostics["selected_tool_names"] == ["web_search"]
    assert diagnostics["selected_skill_names"] == ["Plugin Research Skill"]
    assert diagnostics["sync_rescue"] is True
    assert diagnostics["should_record_call_log"] is True
    assert diagnostics["fallback_history"] == [
        {
            "from_protocol": "responses",
            "to_protocol": "chat_completions",
            "reason": "stream_empty_no_output",
            "recovered": True,
            "metadata": {"recovery_path": "sync_chat_completions"},
        }
    ]
    assert request_payload["turn_record"]["protocol_path"] == "responses"


@pytest.mark.asyncio
async def test_call_log_service_log_call_async_normalizes_provider_connection_failure(
    mock_db,
):
    from app.enums.ai import CallStatusEnum
    from app.services.ai.call_log_service import CallLogService

    service = CallLogService(mock_db)

    with patch("app.tasks.ai.log_ai_call_task.delay") as delay_mock:
        await service.log_call_async(
            tenant_id=PLATFORM_TENANT_ID,
            model_id=33,
            provider_id=11,
            request_type="chat",
            request_data={"messages": [{"role": "user", "content": "hello"}]},
            response_data={"error": "Connection error."},
            input_tokens=0,
            output_tokens=0,
            total_tokens=0,
            cost=0.0,
            latency_ms=123,
            status=CallStatusEnum.FAILED.value,
            error_message="Connection error.",
            turn_record={
                "turn_outcome": "failed",
                "termination_reason": "error",
                "protocol_path": "responses",
                "metadata": {
                    "protocol_fallback_blocked_reason": "provider_connection_error",
                    "stream_failure_error_type": "ProviderConnectionError",
                },
            },
        )

    delay_mock.assert_called_once()
    request_payload = delay_mock.call_args.kwargs["request_data"]
    diagnostics = request_payload["turn_diagnostics"]

    assert diagnostics["turn_outcome"] == "failed"
    assert diagnostics["termination_reason"] == "provider_unavailable"
    assert diagnostics["failure_kind"] == "provider_unavailable"
    assert request_payload["turn_record"]["termination_reason"] == "provider_unavailable"
    assert request_payload["turn_record"]["failure_kind"] == "provider_unavailable"


def test_cli_conversation_summary_renders_runtime_turn_and_call_log_diagnostics() -> None:
    from app.cli import _render_ai_conversation_text

    text = _render_ai_conversation_text(
        {
            "conversation": {
                "id": 42,
                "tenant_id": 0,
                "owner_type": "admin",
                "agent_id": 9,
                "user_id": 7,
                "status": "active",
                "message_count": 3,
                "token_count": 12,
                "cost": 0.0,
                "created_at": "2026-04-02T10:00:00+08:00",
                "updated_at": "2026-04-02T10:01:00+08:00",
            },
            "recent_messages": [],
            "keyword": None,
            "keyword_hits": [],
            "recent_call_logs": [
                {
                    "id": 1001,
                    "created_at": "2026-04-02T10:01:00+08:00",
                    "status": "success",
                    "call_type": "main_chat",
                    "provider_name": "响应云",
                    "model_name": "gpt-5.4-xhigh",
                    "total_tokens": 20,
                    "latency_ms": 321,
                    "turn_outcome": "success",
                    "termination_reason": "protocol_fallback",
                    "protocol_path": "chat_completions",
                    "selected_skill_names": ["Plugin Research Skill"],
                    "fallback_history": [
                        {
                            "from_protocol": "responses",
                            "to_protocol": "chat_completions",
                            "reason": "stream_empty_no_output",
                            "recovered": True,
                            "metadata": {"recovery_path": "sync_chat_completions"},
                        }
                    ],
                    "sync_rescue": True,
                }
            ],
            "diagnostics": {
                "turn_outcome": "success",
                "termination_reason": "protocol_fallback",
                "protocol_path": "chat_completions",
                "selected_tool_names": ["web_search"],
                "selected_skill_names": ["Plugin Research Skill"],
                "fallback_history": [
                    {
                        "from_protocol": "responses",
                        "to_protocol": "chat_completions",
                        "reason": "stream_empty_no_output",
                        "recovered": True,
                        "metadata": {"recovery_path": "sync_chat_completions"},
                    }
                ],
                "sync_rescue": True,
                "should_record_call_log": True,
                "context_sources": [
                    {
                        "kind": "page_context",
                        "name": "admin.runtime.records",
                        "active": True,
                        "metadata": {"page_key": "admin.runtime.records"},
                    }
                ],
                "source": "call_log",
            },
        }
    )

    assert "Turn selected skills: Plugin Research Skill" in text
    assert "Turn sync rescue: True" in text
    assert "Turn should_record_call_log: True" in text
    assert "Turn diagnostics source: call_log" in text
    assert "type=main_chat" in text
    assert "selected_skills: Plugin Research Skill" in text
    assert "fallback_history:" in text


@pytest.mark.asyncio
async def test_log_call_failure_accepts_perf_counter_start_time(mock_db):
    from app.ai.usage_recorder import UsageRecorder

    recorder = UsageRecorder.__new__(UsageRecorder)
    recorder.db = mock_db
    recorder.call_log_service = MagicMock()
    recorder.call_log_service.log_call_async = AsyncMock()

    await recorder.log_call_failure(
        error=RuntimeError("boom"),
        start_time=time.perf_counter() - 1,
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
    assert kwargs["latency_ms"] is not None
    assert 0 <= kwargs["latency_ms"] < 10_000


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
    assert kwargs["call_type"] == "main_chat"
    assert kwargs["cost"] == 0.123
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
    from app.ai.engine.types import ToolUsePolicy
    from app.ai.tools.types import ToolDefinition

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
                tools=[
                    ToolDefinition(name="ui_get_snapshot", description="Get UI snapshot"),
                    ToolDefinition(name="ui_click", description="Click UI element"),
                ],
                all_tool_names=["ui_get_snapshot", "ui_click"],
                tool_use_policy=ToolUsePolicy(
                    family="page_ops",
                    mode="required",
                    allowed_tool_names=["ui_get_snapshot", "ui_click"],
                ),
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
    assert kwargs["tool_choice"] == "required"
    assert kwargs["selected_tool_names"] == ["ui_get_snapshot", "ui_click"]
    assert kwargs["allowed_tool_names"] == ["ui_get_snapshot", "ui_click"]
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

