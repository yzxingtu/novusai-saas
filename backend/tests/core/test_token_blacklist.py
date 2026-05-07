"""
Token 黑名单单元测试 / Token blacklist unit tests.

覆盖：revoke_token 写入 Redis、is_token_revoked 检测、TTL 行为、Redis 不可用时的降级。
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.core.security import TOKEN_BLACKLIST_PREFIX, is_token_revoked, revoke_token

pytest.importorskip("redis", reason="redis required for token blacklist tests")


class TestRevokeToken:
    """revoke_token 测试 / revoke_token tests."""

    @pytest.mark.asyncio
    async def test_revoke_token_sets_redis_key_with_ttl(self, mock_redis):
        """revoke_token 应调用 setex 写入黑名单键 / revoke_token should call setex."""
        with patch("app.core.redis.get_redis_client", return_value=mock_redis):
            await revoke_token("jti-abc123", ttl_seconds=3600)
        mock_redis.setex.assert_called_once()
        call_args = mock_redis.setex.call_args
        assert call_args[0][0] == f"{TOKEN_BLACKLIST_PREFIX}jti-abc123"
        assert call_args[0][1] == 3600
        assert call_args[0][2] == "1"

    @pytest.mark.asyncio
    async def test_revoke_token_silent_on_redis_failure(self):
        """Redis 异常时 revoke_token 应静默失败 / revoke_token should not raise on Redis failure."""
        mock_redis = AsyncMock()
        mock_redis.setex.side_effect = Exception("Redis unavailable")
        with patch("app.core.redis.get_redis_client", return_value=mock_redis):
            await revoke_token("jti-xyz", ttl_seconds=1800)  # should not raise


class TestIsTokenRevoked:
    """is_token_revoked 测试 / is_token_revoked tests."""

    @pytest.mark.asyncio
    async def test_not_revoked_when_key_missing(self, mock_redis):
        """键不存在时返回 False / Returns False when key does not exist."""
        mock_redis.exists.return_value = 0
        with patch("app.core.redis.get_redis_client", return_value=mock_redis):
            result = await is_token_revoked("jti-new")
        assert result is False
        mock_redis.exists.assert_called_once_with(f"{TOKEN_BLACKLIST_PREFIX}jti-new")

    @pytest.mark.asyncio
    async def test_revoked_when_key_exists(self, mock_redis):
        """键存在时返回 True / Returns True when key exists."""
        mock_redis.exists.return_value = 1
        with patch("app.core.redis.get_redis_client", return_value=mock_redis):
            result = await is_token_revoked("jti-revoked")
        assert result is True

    @pytest.mark.asyncio
    async def test_none_jti_returns_false(self, mock_redis):
        """jti 为 None 时返回 False（兼容旧 Token）/ None jti returns False."""
        with patch("app.core.redis.get_redis_client", return_value=mock_redis):
            result = await is_token_revoked(None)
        assert result is False
        mock_redis.exists.assert_not_called()

    @pytest.mark.asyncio
    async def test_empty_jti_returns_false(self, mock_redis):
        """空字符串 jti 应视为未吊销 / Empty jti treated as not revoked."""
        with patch("app.core.redis.get_redis_client", return_value=mock_redis):
            result = await is_token_revoked("")
        assert result is False

    @pytest.mark.asyncio
    async def test_redis_failure_returns_false(self, mock_redis):
        """Redis 异常时返回 False，避免误杀 / Redis failure returns False to avoid false positives."""
        mock_redis.exists.side_effect = Exception("Redis unavailable")
        with patch("app.core.redis.get_redis_client", return_value=mock_redis):
            result = await is_token_revoked("jti-any")
        assert result is False
