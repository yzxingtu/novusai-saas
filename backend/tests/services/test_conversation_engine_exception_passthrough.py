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
    def from_url(cls, *args, **kwargs):
        return cls()

    async def aclose(self) -> None:
        return None


class _RedisClient:
    def __init__(self, *args, **kwargs) -> None:
        return None


class _RedisPipeline:
    pass


redis_exceptions_module.RedisError = type("RedisError", (Exception,), {})
redis_asyncio_module.ConnectionPool = _RedisConnectionPool
redis_asyncio_module.Redis = _RedisClient
redis_asyncio_client_module.Pipeline = _RedisPipeline
redis_module.Redis = _RedisClient
redis_module.from_url = lambda *a, **kw: MagicMock()
redis_module.asyncio = redis_asyncio_module
redis_module.exceptions = redis_exceptions_module
sys.modules.setdefault("redis", redis_module)
sys.modules.setdefault("redis.asyncio", redis_asyncio_module)
sys.modules.setdefault("redis.asyncio.client", redis_asyncio_client_module)
sys.modules.setdefault("redis.exceptions", redis_exceptions_module)

from app.ai.engine.conversation import ConversationEngine
from app.ai.engine.types import ExecutionRequest, PreparedExecution
from app.ai.quota import QuotaExceeded
from app.ai.rate_limiter import RateLimitExceeded
from app.ai.types import ChatMessage


@pytest.mark.asyncio
async def test_conversation_engine_execute_reraises_business_exception() -> None:
    engine = ConversationEngine(db=MagicMock(), gateway=MagicMock(), sandbox=MagicMock())
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
    engine = ConversationEngine(db=MagicMock(), gateway=MagicMock(), sandbox=MagicMock())
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
