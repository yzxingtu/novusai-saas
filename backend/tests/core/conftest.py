"""Core 测试共享 fixtures / Core tests shared fixtures."""

from unittest.mock import AsyncMock

import pytest


@pytest.fixture()
def mock_redis():
    """Mock Redis client with setex/exists for token blacklist. / Token 黑名单用 Redis mock"""
    redis = AsyncMock()
    redis.setex = AsyncMock(return_value=True)
    redis.exists = AsyncMock(return_value=0)
    redis.get = AsyncMock(return_value=None)
    redis.delete = AsyncMock(return_value=1)
    redis.ping = AsyncMock(return_value=True)
    return redis
