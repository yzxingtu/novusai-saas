"""
Tests for OpenAI adapter stream rescue mechanism.
测试 OpenAI 适配器的流式 rescue 机制。
"""

from unittest.mock import AsyncMock, patch

import pytest

from app.ai.adapters.openai_adapter import OpenAIAdapter
from app.ai.adapters.openai_compatible.compat.legacy_protocol_execution import (
    stream_chat_completions_with_sync_rescue,
)
from app.ai.exceptions import ProviderConnectionError
from app.ai.types import ChatChunk, ChatMessage, ChatResponse


@pytest.fixture
def openai_adapter():
    """Create OpenAI adapter instance for testing."""
    return OpenAIAdapter(
        api_key="test-key",
        base_url="https://api.openai.com/v1",
    )


@pytest.mark.asyncio
async def test_stream_rescue_success(openai_adapter):
    """
    Test stream failure followed by successful sync rescue.
    测试流式失败后同步 rescue 成功的场景。
    """
    messages = [ChatMessage(role="user", content="Hello")]

    # Mock stream failure
    stream_mock = AsyncMock()
    stream_mock.__aiter__.return_value = iter([])  # Empty stream

    # Mock successful sync response
    sync_response = ChatResponse(
        message=ChatMessage(role="assistant", content="Rescued response"),
        model="gpt-4",
        finish_reason="stop",
    )

    with patch.object(
        openai_adapter,
        "_stream_chat_via_chat_completions",
        return_value=stream_mock,
    ), patch.object(
        openai_adapter,
        "_chat_via_chat_completions",
        return_value=sync_response,
    ):
        chunks = []
        async for chunk in stream_chat_completions_with_sync_rescue(
            adapter=openai_adapter,
            request_params={},
            sync_request_params={},
            messages=messages,
            model="gpt-4",
            rescue_reason="test",
        ):
            chunks.append(chunk)

        assert len(chunks) == 1
        assert chunks[0].delta == "Rescued response"
        assert chunks[0].finish_reason == "stop"


@pytest.mark.asyncio
async def test_stream_rescue_both_fail(openai_adapter):
    """
    Test stream failure followed by sync rescue failure.
    测试流式失败后同步 rescue 也失败的场景。
    """
    messages = [ChatMessage(role="user", content="Hello")]

    # Mock stream failure
    stream_error = ProviderConnectionError(
        message="Stream connection failed",
        provider_code="openai",
    )

    async def failing_stream(*args, **kwargs):
        raise stream_error
        yield  # Make it a generator

    # Mock sync rescue failure
    rescue_error = ProviderConnectionError(
        message="Sync connection failed",
        provider_code="openai",
    )

    with patch.object(
        openai_adapter,
        "_stream_chat_via_chat_completions",
        side_effect=failing_stream,
    ), patch.object(
        openai_adapter,
        "_chat_via_chat_completions",
        side_effect=rescue_error,
    ) as sync_mock:
        with pytest.raises(ProviderConnectionError) as exc_info:
            async for _ in stream_chat_completions_with_sync_rescue(
                adapter=openai_adapter,
                request_params={},
                sync_request_params={},
                messages=messages,
                model="gpt-4",
                rescue_reason="test",
            ):
                pass

        # Should raise the original stream error, not the rescue error
        assert exc_info.value == stream_error
        assert "Stream connection failed" in str(exc_info.value)
        sync_mock.assert_not_called()


@pytest.mark.asyncio
async def test_stream_rescue_no_stream_error(openai_adapter):
    """
    Test empty stream (no error) followed by sync rescue failure.
    测试空流（无错误）后同步 rescue 失败的场景。
    """
    messages = [ChatMessage(role="user", content="Hello")]

    # Mock empty stream (no error, just no chunks)
    async def empty_stream(*args, **kwargs):
        return
        yield  # Make it a generator

    # Mock sync rescue failure
    rescue_error = ProviderConnectionError(
        message="Sync connection failed",
        provider_code="openai",
    )

    with patch.object(
        openai_adapter,
        "_stream_chat_via_chat_completions",
        side_effect=empty_stream,
    ), patch.object(
        openai_adapter,
        "_chat_via_chat_completions",
        side_effect=rescue_error,
    ):
        with pytest.raises(ProviderConnectionError) as exc_info:
            async for _ in stream_chat_completions_with_sync_rescue(
                adapter=openai_adapter,
                request_params={},
                sync_request_params={},
                messages=messages,
                model="gpt-4",
                rescue_reason="test",
            ):
                pass

        # Should raise the rescue error since there was no stream error
        assert exc_info.value == rescue_error
        assert "Sync connection failed" in str(exc_info.value)


@pytest.mark.asyncio
async def test_stream_rescue_partial_stream_success(openai_adapter):
    """
    Test partial stream followed by no rescue (stream already emitted chunks).
    测试部分流式输出后不需要 rescue 的场景。
    """
    messages = [ChatMessage(role="user", content="Hello")]

    # Mock partial stream with meaningful chunk
    async def partial_stream(*args, **kwargs):
        yield ChatChunk(delta="Partial ", role="assistant")
        yield ChatChunk(delta="response", role="assistant", finish_reason="stop")

    with patch.object(
        openai_adapter,
        "_stream_chat_via_chat_completions",
        side_effect=partial_stream,
    ), patch.object(
        openai_adapter,
        "_chat_via_chat_completions",
    ) as sync_mock:
        chunks = []
        async for chunk in stream_chat_completions_with_sync_rescue(
            adapter=openai_adapter,
            request_params={},
            sync_request_params={},
            messages=messages,
            model="gpt-4",
            rescue_reason="test",
        ):
            chunks.append(chunk)

        # Should have 2 chunks from stream
        assert len(chunks) == 2
        assert chunks[0].delta == "Partial "
        assert chunks[1].delta == "response"

        # Sync rescue should NOT be called
        sync_mock.assert_not_called()


@pytest.mark.asyncio
async def test_stream_rescue_network_error(openai_adapter):
    """
    Test network error (status_code=None) scenario.
    测试网络错误（status_code=None）场景。
    """
    messages = [ChatMessage(role="user", content="Hello")]

    # Mock network error (no status code)
    network_error = Exception("Network unreachable")

    async def failing_stream(*args, **kwargs):
        raise network_error
        yield

    # Mock sync rescue also fails with network error
    sync_network_error = Exception("Sync network unreachable")

    with patch.object(
        openai_adapter,
        "_stream_chat_via_chat_completions",
        side_effect=failing_stream,
    ), patch.object(
        openai_adapter,
        "_chat_via_chat_completions",
        side_effect=sync_network_error,
    ):
        with pytest.raises(Exception) as exc_info:
            async for _ in stream_chat_completions_with_sync_rescue(
                adapter=openai_adapter,
                request_params={},
                sync_request_params={},
                messages=messages,
                model="gpt-4",
                rescue_reason="test",
            ):
                pass

        # Should raise the original network error
        assert exc_info.value == network_error
        assert "Network unreachable" in str(exc_info.value)


@pytest.mark.asyncio
async def test_stream_rescue_invalid_string_response(openai_adapter):
    """
    Test invalid string response (HTML/JSON) from upstream.
    测试上游返回无效字符串响应（HTML/JSON）的场景。
    """
    messages = [ChatMessage(role="user", content="Hello")]

    # Mock empty stream
    async def empty_stream(*args, **kwargs):
        return
        yield

    # Mock _chat_via_chat_completions to raise ValueError for invalid string
    async def invalid_string_response(*args, **kwargs):
        raise ValueError("Upstream returned invalid string response: <html><body>502")

    with patch.object(
        openai_adapter,
        "_stream_chat_via_chat_completions",
        side_effect=empty_stream,
    ), patch.object(
        openai_adapter,
        "_chat_via_chat_completions",
        side_effect=invalid_string_response,
    ):
        with pytest.raises(ValueError) as exc_info:
            async for _ in stream_chat_completions_with_sync_rescue(
                adapter=openai_adapter,
                request_params={},
                sync_request_params={},
                messages=messages,
                model="gpt-4",
                rescue_reason="test",
            ):
                pass

        # Should raise ValueError for invalid string response
        assert "invalid string response" in str(exc_info.value).lower()
