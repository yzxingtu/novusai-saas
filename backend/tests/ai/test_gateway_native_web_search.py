from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.ai.exceptions import ProviderTimeoutError
from app.ai.web_search.types import (
    PROVIDER_MODE_NATIVE,
    STATUS_SUCCESS,
    STATUS_TIMEOUT,
    SearchProviderRun,
    SearchResultItem,
)


def _make_item() -> SearchResultItem:
    return SearchResultItem(
        title="Example",
        url="https://example.com",
        snippet="summary",
        source="native:openai:gpt-5.4",
        provider="openai",
        provider_mode=PROVIDER_MODE_NATIVE,
        rank=1,
    )


@pytest.mark.asyncio
async def test_gateway_native_web_search_records_usage_and_logs_success() -> None:
    from app.ai.gateway import AIGateway

    mock_db = AsyncMock()
    gateway = AIGateway.__new__(AIGateway)
    gateway.db = mock_db
    gateway.provider_repo = MagicMock()
    gateway.api_key_repo = MagicMock()
    gateway.model_repo = MagicMock()
    gateway.failover = MagicMock()
    gateway.retry_service = MagicMock()
    gateway.usage_recorder = MagicMock()
    gateway.usage_recorder.check_rate_and_quota = AsyncMock(return_value=SimpleNamespace())
    gateway.usage_recorder.record_usage_and_adjust = AsyncMock()
    gateway.usage_recorder.call_log_service = MagicMock()
    gateway.usage_recorder.call_log_service.log_call_async = AsyncMock()

    provider = SimpleNamespace(
        id=11,
        code="openai",
        type="openai_compatible",
        base_url="https://example.com/v1",
        config={},
    )
    model = SimpleNamespace(
        id=33,
        code="gpt-5.4",
        config={},
    )
    api_key = SimpleNamespace(
        id=22,
        decrypt_key=MagicMock(return_value="sk-test"),
        increment_usage=MagicMock(),
    )
    gateway.get_provider_and_key = AsyncMock(return_value=(provider, api_key))
    gateway._get_model = AsyncMock(return_value=model)

    run = SearchProviderRun(
        provider="openai",
        provider_mode=PROVIDER_MODE_NATIVE,
        backend_key="native:openai:gpt-5.4",
        status=STATUS_SUCCESS,
        items=[_make_item()],
        attempted_backends=["native:openai:gpt-5.4"],
        input_tokens=21,
        output_tokens=5,
        total_tokens=26,
    )
    gateway.retry_service.execute_with_retry = AsyncMock(return_value=(run, 1, api_key))

    with patch(
        "app.ai.gateway.AdapterRegistry.get_adapter",
        return_value=object(),
    ), patch(
        "app.ai.gateway.AdapterRegistry.create_adapter",
        return_value=SimpleNamespace(supports_native_web_search=MagicMock(return_value=True)),
    ), patch(
        "app.ai.gateway.TokenCounter.count_messages_tokens",
        return_value=13,
    ), patch(
        "app.ai.gateway.CostCalculator.calculate_cost",
        return_value=0.123,
    ):
        result = await gateway.native_web_search(
            provider_code="openai",
            model="gpt-5.4",
            query="OpenAI",
            max_results=5,
            locale="zh_CN",
            timeout_seconds=20,
            tenant_id=101,
            user_id=7,
            agent_id=44,
            conversation_id=55,
        )

    assert result.status == STATUS_SUCCESS
    gateway.retry_service.execute_with_retry.assert_awaited_once()
    assert gateway.retry_service.execute_with_retry.await_args.kwargs["max_retries"] == 0
    gateway.usage_recorder.check_rate_and_quota.assert_awaited_once()
    gateway.usage_recorder.record_usage_and_adjust.assert_awaited_once()
    gateway.usage_recorder.call_log_service.log_call_async.assert_awaited_once()
    kwargs = gateway.usage_recorder.call_log_service.log_call_async.await_args.kwargs
    assert kwargs["tenant_id"] == 101
    assert kwargs["user_id"] == 7
    assert kwargs["agent_id"] == 44
    assert kwargs["conversation_id"] == 55
    assert kwargs["call_type"] == "internal_tool"
    assert kwargs["request_data"]["selected_tool_names"] == ["web_search"]
    assert kwargs["request_data"]["all_tool_names"] == ["web_search", "fetch_url"]
    assert kwargs["response_data"]["status"] == STATUS_SUCCESS
    assert kwargs["response_data"]["result_count"] == 1
    api_key.increment_usage.assert_called_once()
    mock_db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_gateway_native_web_search_logs_timeout_without_usage_commit() -> None:
    from app.ai.gateway import AIGateway

    mock_db = AsyncMock()
    gateway = AIGateway.__new__(AIGateway)
    gateway.db = mock_db
    gateway.provider_repo = MagicMock()
    gateway.api_key_repo = MagicMock()
    gateway.model_repo = MagicMock()
    gateway.failover = MagicMock()
    gateway.retry_service = MagicMock()
    gateway.usage_recorder = MagicMock()
    gateway.usage_recorder.check_rate_and_quota = AsyncMock(return_value=SimpleNamespace())
    gateway.usage_recorder.record_usage_and_adjust = AsyncMock()
    gateway.usage_recorder.call_log_service = MagicMock()
    gateway.usage_recorder.call_log_service.log_call_async = AsyncMock()

    provider = SimpleNamespace(
        id=11,
        code="openai",
        type="openai_compatible",
        base_url="https://example.com/v1",
        config={},
    )
    model = SimpleNamespace(id=33, code="gpt-5.4", config={})
    api_key = SimpleNamespace(
        id=22,
        decrypt_key=MagicMock(return_value="sk-test"),
        increment_usage=MagicMock(),
    )
    gateway.get_provider_and_key = AsyncMock(return_value=(provider, api_key))
    gateway._get_model = AsyncMock(return_value=model)
    gateway.retry_service.execute_with_retry = AsyncMock(
        side_effect=ProviderTimeoutError(
            message="provider timed out",
            provider_code="openai",
            model_code="gpt-5.4",
        )
    )

    with patch(
        "app.ai.gateway.AdapterRegistry.get_adapter",
        return_value=object(),
    ), patch(
        "app.ai.gateway.AdapterRegistry.create_adapter",
        return_value=SimpleNamespace(supports_native_web_search=MagicMock(return_value=True)),
    ), patch(
        "app.ai.gateway.TokenCounter.count_messages_tokens",
        return_value=13,
    ):
        result = await gateway.native_web_search(
            provider_code="openai",
            model="gpt-5.4",
            query="OpenAI",
            max_results=5,
            locale="zh_CN",
            timeout_seconds=20,
            tenant_id=101,
            user_id=7,
            agent_id=44,
            conversation_id=55,
        )

    assert result.status == STATUS_TIMEOUT
    gateway.usage_recorder.record_usage_and_adjust.assert_not_awaited()
    gateway.usage_recorder.call_log_service.log_call_async.assert_awaited_once()
    assert gateway.retry_service.execute_with_retry.await_args.kwargs["max_retries"] == 0
    kwargs = gateway.usage_recorder.call_log_service.log_call_async.await_args.kwargs
    assert kwargs["status"] == "timeout"
    assert kwargs["call_type"] == "internal_tool"
    assert kwargs["response_data"]["_retry_count"] == 0
    api_key.increment_usage.assert_not_called()
    mock_db.commit.assert_not_awaited()
