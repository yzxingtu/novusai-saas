"""
Test type: behavioral
Scope: ConversationEngine exception passthrough and retry policy boundaries.
Mocked dependencies: Redis module import seam and LLM adapter calls via focused AsyncMock.
"""

# Redis import stubs must be installed before importing app modules under test.
# ruff: noqa: E402

import sys
import types
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

redis_module = types.ModuleType("redis")
redis_asyncio_module = types.ModuleType("redis.asyncio")
redis_asyncio_client_module = types.ModuleType("redis.asyncio.client")
redis_exceptions_module = types.ModuleType("redis.exceptions")


class _RedisConnectionPool:
    @classmethod
    def from_url(cls, *_args, **_kwargs):
        return cls()

    async def aclose(self) -> None:
        return None


class _RedisClient:
    def __init__(self, *_args, **_kwargs) -> None:
        return None


class _RedisPipeline:
    pass


redis_exceptions_module.RedisError = type("RedisError", (Exception,), {})
redis_asyncio_module.ConnectionPool = _RedisConnectionPool
redis_asyncio_module.Redis = _RedisClient
redis_asyncio_client_module.Pipeline = _RedisPipeline
redis_module.Redis = _RedisClient
redis_module.from_url = lambda *_args, **_kwargs: MagicMock()
redis_module.asyncio = redis_asyncio_module
redis_module.exceptions = redis_exceptions_module
sys.modules.setdefault("redis", redis_module)
sys.modules.setdefault("redis.asyncio", redis_asyncio_module)
sys.modules.setdefault("redis.asyncio.client", redis_asyncio_client_module)
sys.modules.setdefault("redis.exceptions", redis_exceptions_module)

from app.ai.engine.conversation import ConversationEngine
from app.ai.engine.types import (
    ExecutionRequest,
    PreparedExecution,
)
from app.ai.quota import QuotaExceeded
from app.ai.rate_limiter import RateLimitExceeded
from app.ai.types import ChatMessage, ChatResponse
from app.core.config import settings
from app.middleware.trace import trace_id_var


@pytest.mark.asyncio
async def test_conversation_engine_execute_reraises_business_exception() -> None:
    engine = ConversationEngine(
        db=MagicMock(), gateway=MagicMock(), sandbox=MagicMock()
    )
    engine._prepare_execution = AsyncMock(
        return_value=PreparedExecution(
            messages=[ChatMessage(role="user", content="hello")],
            tools=[],
            rag_sources=None,
            tool_consent_modes={},
            optimize_event=None,
            route_result=None,
        )
    )
    engine._call_llm = AsyncMock(
        side_effect=QuotaExceeded("AI quota exceeded for passthrough test")
    )

    request = ExecutionRequest(
        agent_id=1,
        tenant_id=1,
        user_id=1,
        messages=[ChatMessage(role="user", content="hello")],
    )
    agent = SimpleNamespace(id=1)

    with pytest.raises(QuotaExceeded) as exc_info:
        await engine.execute(agent, request)

    assert exc_info.value.status_code == 429
    assert exc_info.value.code == 4291


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("exc_factory", "expected_code"),
    [
        (lambda: QuotaExceeded("quota preflight blocked"), 4291),
        (lambda: RateLimitExceeded("rate limit preflight blocked"), 4292),
    ],
)
async def test_conversation_engine_stream_execute_preflight_reraises_business_exception(
    exc_factory,
    expected_code: int,
) -> None:
    engine = ConversationEngine(
        db=MagicMock(), gateway=MagicMock(), sandbox=MagicMock()
    )
    engine._prepare_execution = AsyncMock(
        return_value=PreparedExecution(
            messages=[ChatMessage(role="user", content="hello")],
            tools=[],
            rag_sources=None,
            tool_consent_modes={},
            optimize_event=None,
            route_result=None,
        )
    )
    engine._prepare_stream_runtime = AsyncMock(side_effect=exc_factory())

    request = ExecutionRequest(
        agent_id=1,
        tenant_id=1,
        user_id=1,
        messages=[ChatMessage(role="user", content="hello")],
        stream=True,
    )
    agent = SimpleNamespace(id=1)

    with pytest.raises((QuotaExceeded, RateLimitExceeded)) as exc_info:
        await engine.stream_execute(agent, request)

    assert exc_info.value.status_code == 429
    assert exc_info.value.code == expected_code


@pytest.mark.asyncio
async def test_conversation_engine_execute_hides_generic_exception_in_production() -> (
    None
):
    engine = ConversationEngine(
        db=MagicMock(), gateway=MagicMock(), sandbox=MagicMock()
    )
    engine._prepare_execution = AsyncMock(
        side_effect=RuntimeError("secret provider stack")
    )

    request = ExecutionRequest(
        agent_id=1,
        tenant_id=1,
        user_id=1,
        messages=[ChatMessage(role="user", content="hello")],
    )
    agent = SimpleNamespace(id=1)
    original_debug = settings.DEBUG
    token = trace_id_var.set("trace-conversation-prod")
    settings.DEBUG = False
    try:
        result = await engine.execute(agent, request)
    finally:
        settings.DEBUG = original_debug
        trace_id_var.reset(token)

    assert result.success is False
    assert "secret provider stack" not in (result.error or "")
    assert result.error == "服务器内部错误 [trace_id=trace-conversation-prod]"
    assert result.diagnostics is not None


@pytest.mark.asyncio
async def test_conversation_engine_execute_calls_context_engine_after_turn() -> None:
    engine = ConversationEngine(
        db=MagicMock(), gateway=MagicMock(), sandbox=MagicMock()
    )
    context_engine = AsyncMock()
    prep = PreparedExecution(
        messages=[ChatMessage(role="user", content="hello")],
        tools=[],
        rag_sources=None,
        tool_consent_modes={},
        optimize_event=None,
        route_result=None,
        context_engine=context_engine,
    )
    engine._prepare_execution = AsyncMock(return_value=prep)
    engine._call_llm = AsyncMock(
        return_value=ChatResponse(
            message=ChatMessage(role="assistant", content="world"),
            total_tokens=8,
        )
    )

    request = ExecutionRequest(
        agent_id=1,
        tenant_id=1,
        user_id=1,
        messages=[ChatMessage(role="user", content="hello")],
    )
    agent = SimpleNamespace(id=1)

    result = await engine.execute(agent, request)

    assert result.success is True
    context_engine.after_turn.assert_awaited_once()
