"""
CacheManagementService 单元测试

覆盖：缓存统计扫描、缓存清理、格式化工具函数、枚举/Schema 验证。
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.enums.cache import CacheCategoryEnum
from app.schemas.system.cache import (
    CacheCategorySummary,
    CacheClearRequest,
    CacheClearResponse,
    CacheSummaryResponse,
)
from app.services.system.cache_management_service import (
    CacheManagementService,
    _format_size,
)


# ── _format_size tests ──


class TestFormatSize:

    def test_bytes(self):
        assert _format_size(0) == "0 B"
        assert _format_size(512) == "512 B"
        assert _format_size(1023) == "1023 B"

    def test_kilobytes(self):
        assert _format_size(1024) == "1.0 KB"
        assert _format_size(1536) == "1.5 KB"

    def test_megabytes(self):
        assert _format_size(1024 * 1024) == "1.0 MB"
        assert _format_size(int(2.5 * 1024 * 1024)) == "2.5 MB"

    def test_gigabytes(self):
        assert _format_size(1024 * 1024 * 1024) == "1.0 GB"


# ── CacheCategoryEnum tests ──


class TestCacheCategoryEnum:

    def test_all_values_present(self):
        expected = {
            "ai_response",
            "ai_schema",
            "ai_sql_result",
            "ai_action_rate",
            "ai_action_confirm",
            "kb_search",
            "ws_config",
            "marketplace",
            "ai_provider_health",
            "image_cache",
            "config_memory",
        }
        assert set(CacheCategoryEnum.values()) == expected

    def test_from_value(self):
        result = CacheCategoryEnum.from_value("ai_response")
        assert result == CacheCategoryEnum.AI_RESPONSE

    def test_from_value_invalid(self):
        result = CacheCategoryEnum.from_value("nonexistent")
        assert result is None

    def test_label_key_format(self):
        for member in CacheCategoryEnum:
            assert member.label.startswith("enum.cache.category.")


# ── Schema validation tests ──


class TestCacheClearRequestValidation:

    def test_valid_categories(self):
        req = CacheClearRequest(categories=["ai_response", "image_cache"])
        assert len(req.categories) == 2

    def test_invalid_category_raises(self):
        with pytest.raises(Exception):
            CacheClearRequest(categories=["invalid_category"])

    def test_empty_categories_raises(self):
        with pytest.raises(Exception):
            CacheClearRequest(categories=[])

    def test_all_categories_valid(self):
        req = CacheClearRequest(categories=CacheCategoryEnum.values())
        assert len(req.categories) == len(CacheCategoryEnum)


class TestCacheSummaryResponse:

    def test_defaults(self):
        resp = CacheSummaryResponse()
        assert resp.categories == []
        assert resp.total_size_bytes == 0
        assert resp.total_size_human == "0 B"


class TestCacheClearResponse:

    def test_defaults(self):
        resp = CacheClearResponse()
        assert resp.cleared_categories == []
        assert resp.cleared_keys == 0
        assert resp.cleared_size_bytes == 0
        assert resp.duration_ms == 0


# ── Service scan tests ──


class TestGetCacheSummary:

    @pytest.mark.asyncio
    async def test_returns_all_categories(self):
        mock_redis = AsyncMock()
        mock_redis.scan_iter = AsyncMock(return_value=AsyncIterator([]))
        mock_redis.memory_usage = AsyncMock(return_value=0)

        with (
            patch(
                "app.services.system.cache_management_service.get_redis_client",
                return_value=mock_redis,
            ),
            patch(
                "app.services.system.cache_management_service.LOCAL_IMAGE_CACHE_ROOT",
                MagicMock(exists=MagicMock(return_value=False)),
            ),
            patch(
                "app.services.system.cache_management_service.CacheManagementService._scan_config_memory_cache",
                return_value=MagicMock(key_count=0, size_bytes=0),
            ),
        ):
            summary = await CacheManagementService.get_cache_summary()

        assert isinstance(summary, CacheSummaryResponse)
        assert len(summary.categories) == len(CacheCategoryEnum)

    @pytest.mark.asyncio
    async def test_aggregates_total_size(self):
        mock_redis = AsyncMock()
        mock_redis.scan_iter = AsyncMock(return_value=AsyncIterator([]))

        with (
            patch(
                "app.services.system.cache_management_service.get_redis_client",
                return_value=mock_redis,
            ),
            patch(
                "app.services.system.cache_management_service.LOCAL_IMAGE_CACHE_ROOT",
                MagicMock(exists=MagicMock(return_value=False)),
            ),
            patch(
                "app.services.system.cache_management_service.CacheManagementService._scan_config_memory_cache",
                return_value=MagicMock(key_count=0, size_bytes=0),
            ),
        ):
            summary = await CacheManagementService.get_cache_summary()

        assert summary.total_size_bytes == 0
        assert summary.total_size_human == "0 B"


# ── Service clear tests ──


class TestClearCache:

    @pytest.mark.asyncio
    async def test_clear_single_redis_category(self):
        mock_redis = AsyncMock()
        mock_redis.scan_iter = AsyncMock(
            return_value=AsyncIterator(["ai:response:key1", "ai:response:key2"])
        )
        mock_redis.memory_usage = AsyncMock(return_value=100)
        mock_redis.delete = AsyncMock(return_value=2)

        with patch(
            "app.services.system.cache_management_service.get_redis_client",
            return_value=mock_redis,
        ):
            result = await CacheManagementService.clear_cache(
                [CacheCategoryEnum.AI_RESPONSE]
            )

        assert isinstance(result, CacheClearResponse)
        assert "ai_response" in result.cleared_categories
        assert result.cleared_keys == 2
        assert result.duration_ms >= 0

    @pytest.mark.asyncio
    async def test_clear_config_memory(self):
        with patch(
            "app.services.system.cache_management_service.CacheManagementService._clear_config_memory_cache",
            return_value=MagicMock(key_count=5, size_bytes=0),
        ):
            result = await CacheManagementService.clear_cache(
                [CacheCategoryEnum.CONFIG_MEMORY]
            )

        assert "config_memory" in result.cleared_categories
        assert result.cleared_keys == 5

    @pytest.mark.asyncio
    async def test_clear_multiple_categories(self):
        mock_redis = AsyncMock()
        mock_redis.scan_iter = AsyncMock(
            return_value=AsyncIterator(["key1"])
        )
        mock_redis.memory_usage = AsyncMock(return_value=50)
        mock_redis.delete = AsyncMock(return_value=1)

        with (
            patch(
                "app.services.system.cache_management_service.get_redis_client",
                return_value=mock_redis,
            ),
            patch(
                "app.services.system.cache_management_service.CacheManagementService._clear_config_memory_cache",
                return_value=MagicMock(key_count=3, size_bytes=0),
            ),
        ):
            result = await CacheManagementService.clear_cache(
                [CacheCategoryEnum.AI_RESPONSE, CacheCategoryEnum.CONFIG_MEMORY]
            )

        assert len(result.cleared_categories) == 2
        assert result.cleared_keys == 4  # 1 redis + 3 memory

    @pytest.mark.asyncio
    async def test_clear_empty_list(self):
        result = await CacheManagementService.clear_cache([])
        assert result.cleared_categories == []
        assert result.cleared_keys == 0


# ── Async iterator helper ──


class AsyncIterator:
    """Helper to create async iterator from a list for mock scan_iter."""

    def __init__(self, items: list):
        self._items = items
        self._index = 0

    def __aiter__(self):
        self._index = 0
        return self

    async def __anext__(self):
        if self._index >= len(self._items):
            raise StopAsyncIteration
        item = self._items[self._index]
        self._index += 1
        return item
