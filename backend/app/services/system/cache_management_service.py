"""
缓存管理服务 / Cache Management Service

提供 Redis 缓存、本地文件缓存和内存配置缓存的扫描、统计和清理功能。
Provides cache scanning, statistics, and clearing for Redis-based caches,
local filesystem caches, and in-memory config caches.
"""

import os
import shutil
import time
from dataclasses import dataclass
from typing import Any

from app.core.logging import LogManager
from app.core.redis import get_redis_client
from app.enums.cache import CacheCategoryEnum
from app.schemas.system.cache import (
    CacheCategorySummary,
    CacheClearResponse,
    CacheSummaryResponse,
)
from app.storage import LOCAL_IMAGE_CACHE_ROOT

logger = LogManager.get_logger("app")

# Redis key pattern mapping for each cache category / Redis 键模式映射 / Redis key patterns
_REDIS_PATTERNS: dict[str, str] = {
    CacheCategoryEnum.AI_RESPONSE.value: "ai:response:*",
    CacheCategoryEnum.AI_SCHEMA.value: "ai:schema:*",
    CacheCategoryEnum.AI_SQL_RESULT.value: "ai:sql_result:*",
    CacheCategoryEnum.AI_ACTION_RATE.value: "ai:action_rate:*",
    CacheCategoryEnum.KB_SEARCH.value: "kb:search:*",
    CacheCategoryEnum.WS_CONFIG.value: "ws_cfg:*",
    CacheCategoryEnum.MARKETPLACE.value: "marketplace:*",
    CacheCategoryEnum.AI_PROVIDER_HEALTH.value: "ai:provider:*:health",
    CacheCategoryEnum.AI_RATE_LIMIT.value: "ai:rate_limit:*",
    CacheCategoryEnum.CELERY_RESULTS.value: "celery-task-meta-*",
}


def _format_size(size_bytes: int) -> str:
    """Convert bytes to human-readable string / 将字节转为可读字符串"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"


@dataclass
class _CategoryStats:
    """Internal stats container for a single category / 单分类统计容器"""

    key_count: int = 0
    size_bytes: int = 0


class CacheManagementService:
    """
    Cache management utility service. / 缓存管理工具服务。

    Not a standard CRUD service — no DB Model/Repository. Provides cache summary and clearing for admin panel.
    非标准 CRUD 服务，提供缓存统计与清理能力。
    """

    @staticmethod
    async def _iter_redis_keys(redis: Any, pattern: str):
        """Iterate Redis keys for a pattern. / 按模式迭代 Redis 键。

        Supports both async iterator and async function returning iterator (for tests).
        """
        scan_result = redis.scan_iter(match=pattern, count=200)

        if hasattr(scan_result, "__aiter__"):
            async for key in scan_result:
                yield key
            return

        scan_result = await scan_result
        async for key in scan_result:
            yield key

    @staticmethod
    async def _scan_redis_category(pattern: str) -> _CategoryStats:
        """Scan Redis keys matching pattern and calculate stats / 扫描 Redis 键并统计"""
        stats = _CategoryStats()
        try:
            redis = get_redis_client()
            async for key in CacheManagementService._iter_redis_keys(redis, pattern):
                stats.key_count += 1
                try:
                    mem = await redis.memory_usage(key)
                    if mem is not None:
                        stats.size_bytes += mem
                except Exception:
                    pass
        except Exception as exc:
            logger.warning("Failed to scan Redis pattern {}: {}", pattern, exc)
        return stats

    @staticmethod
    def _scan_local_image_cache() -> _CategoryStats:
        """Scan local image cache directory for file count and total size / 扫描本地图片缓存目录"""
        stats = _CategoryStats()
        cache_dir = LOCAL_IMAGE_CACHE_ROOT
        if not cache_dir.exists():
            return stats
        try:
            for entry in os.scandir(cache_dir):
                if entry.is_file(follow_symlinks=False):
                    stats.key_count += 1
                    stats.size_bytes += entry.stat().st_size
                elif entry.is_dir(follow_symlinks=False):
                    for sub_entry in os.scandir(entry.path):
                        if sub_entry.is_file(follow_symlinks=False):
                            stats.key_count += 1
                            stats.size_bytes += sub_entry.stat().st_size
        except Exception as exc:
            logger.warning("Failed to scan image cache directory: {}", exc)
        return stats

    @staticmethod
    def _scan_config_memory_cache() -> _CategoryStats:
        """Get in-memory config cache entry count / 获取内存配置缓存条目数"""
        from app.configs.service import _config_id_cache, _config_value_cache

        return _CategoryStats(
            key_count=len(_config_id_cache) + len(_config_value_cache),
            size_bytes=0,
        )

    @staticmethod
    def _scan_captcha_cache() -> _CategoryStats:
        """Get in-memory captcha service cache entry count / 获取验证码服务内存缓存条目数"""
        try:
            from app.captcha.service import captcha_service
            count = (
                len(captcha_service._store)
                + len(captcha_service._used)
                + len(captcha_service._fail_counts)
                + len(captcha_service._rate_limits)
            )
            return _CategoryStats(key_count=count, size_bytes=0)
        except Exception:
            return _CategoryStats()

    @staticmethod
    def _scan_plugin_update_cache() -> _CategoryStats:
        """Get in-memory plugin update check cache entry count / 获取插件更新检查缓存条目数"""
        try:
            from app.plugins.update_checker import _update_cache
            return _CategoryStats(key_count=len(_update_cache), size_bytes=0)
        except Exception:
            return _CategoryStats()

    @staticmethod
    def _build_summary_item(
        category: CacheCategoryEnum, stats: _CategoryStats
    ) -> CacheCategorySummary:
        """Build a CacheCategorySummary from raw stats / 从原始统计构建分类摘要"""
        return CacheCategorySummary(
            category=category.value,
            label=category.label,
            key_count=stats.key_count,
            size_bytes=stats.size_bytes,
            size_human=_format_size(stats.size_bytes),
        )

    @classmethod
    async def get_cache_summary(cls) -> CacheSummaryResponse:
        """
        Scan all cache categories and return summary statistics. / 扫描所有缓存分类并返回汇总。
        Returns: CacheSummaryResponse with per-category stats and totals.
        """
        categories: list[CacheCategorySummary] = []
        total_size = 0

        for member in CacheCategoryEnum:
            if member.value in _REDIS_PATTERNS:
                stats = await cls._scan_redis_category(
                    _REDIS_PATTERNS[member.value]
                )
            elif member == CacheCategoryEnum.IMAGE_CACHE:
                stats = cls._scan_local_image_cache()
            elif member == CacheCategoryEnum.CONFIG_MEMORY:
                stats = cls._scan_config_memory_cache()
            elif member == CacheCategoryEnum.CAPTCHA:
                stats = cls._scan_captcha_cache()
            elif member == CacheCategoryEnum.PLUGIN_UPDATE:
                stats = cls._scan_plugin_update_cache()
            else:
                stats = _CategoryStats()

            item = cls._build_summary_item(member, stats)
            categories.append(item)
            total_size += stats.size_bytes

        return CacheSummaryResponse(
            categories=categories,
            total_size_bytes=total_size,
            total_size_human=_format_size(total_size),
        )

    @staticmethod
    async def _clear_redis_pattern(pattern: str) -> _CategoryStats:
        """Clear all Redis keys matching pattern, return cleared stats / 按模式清理 Redis 键并返回统计"""
        stats = _CategoryStats()
        try:
            redis = get_redis_client()
            keys_to_delete: list[str] = []
            async for key in CacheManagementService._iter_redis_keys(redis, pattern):
                stats.key_count += 1
                try:
                    mem = await redis.memory_usage(key)
                    if mem is not None:
                        stats.size_bytes += mem
                except Exception:
                    pass
                keys_to_delete.append(key)

                if len(keys_to_delete) >= 500:
                    await redis.delete(*keys_to_delete)
                    keys_to_delete.clear()

            if keys_to_delete:
                await redis.delete(*keys_to_delete)
        except Exception as exc:
            logger.error("Failed to clear Redis pattern {}: {}", pattern, exc)
        return stats

    @staticmethod
    def _clear_local_image_cache() -> _CategoryStats:
        """Remove all files in image cache directory / 清空本地图片缓存目录"""
        stats = _CategoryStats()
        cache_dir = LOCAL_IMAGE_CACHE_ROOT
        if not cache_dir.exists():
            return stats

        try:
            for entry in os.scandir(cache_dir):
                if entry.is_file(follow_symlinks=False):
                    stats.key_count += 1
                    stats.size_bytes += entry.stat().st_size
                    os.unlink(entry.path)
                elif entry.is_dir(follow_symlinks=False):
                    dir_size = 0
                    dir_count = 0
                    for sub_entry in os.scandir(entry.path):
                        if sub_entry.is_file(follow_symlinks=False):
                            dir_count += 1
                            dir_size += sub_entry.stat().st_size
                    stats.key_count += dir_count
                    stats.size_bytes += dir_size
                    shutil.rmtree(entry.path, ignore_errors=True)
        except Exception as exc:
            logger.error("Failed to clear image cache directory: {}", exc)
        return stats

    @staticmethod
    def _clear_config_memory_cache() -> _CategoryStats:
        """Clear in-memory config caches / 清空内存配置缓存"""
        from app.configs.service import _config_id_cache, _config_value_cache

        count = len(_config_id_cache) + len(_config_value_cache)
        _config_id_cache.clear()
        _config_value_cache.clear()
        return _CategoryStats(key_count=count, size_bytes=0)

    @staticmethod
    def _clear_captcha_cache() -> _CategoryStats:
        """Clear in-memory captcha service caches / 清空验证码服务内存缓存"""
        try:
            from app.captcha.service import captcha_service
            count = (
                len(captcha_service._store)
                + len(captcha_service._used)
                + len(captcha_service._fail_counts)
                + len(captcha_service._rate_limits)
            )
            captcha_service._store.clear()
            captcha_service._used.clear()
            captcha_service._fail_counts.clear()
            captcha_service._rate_limits.clear()
            return _CategoryStats(key_count=count, size_bytes=0)
        except Exception as exc:
            logger.warning("Failed to clear captcha cache: {}", exc)
            return _CategoryStats()

    @staticmethod
    def _clear_plugin_update_cache() -> _CategoryStats:
        """Clear in-memory plugin update check cache / 清空插件更新检查缓存"""
        try:
            from app.plugins.update_checker import _update_cache, clear_update_cache
            count = len(_update_cache)
            clear_update_cache()
            return _CategoryStats(key_count=count, size_bytes=0)
        except Exception as exc:
            logger.warning("Failed to clear plugin update cache: {}", exc)
            return _CategoryStats()

    @classmethod
    async def clear_cache(
        cls, categories: list[CacheCategoryEnum]
    ) -> CacheClearResponse:
        """
        Clear specified cache categories. / 清理指定缓存分类。

        Args:
            categories: List of cache categories to clear. / 要清理的分类列表
        Returns:
            CacheClearResponse with cleared stats and duration.
        """
        start = time.monotonic()
        total_keys = 0
        total_size = 0
        cleared: list[str] = []

        for category in categories:
            if category.value in _REDIS_PATTERNS:
                stats = await cls._clear_redis_pattern(
                    _REDIS_PATTERNS[category.value]
                )
            elif category == CacheCategoryEnum.IMAGE_CACHE:
                stats = cls._clear_local_image_cache()
            elif category == CacheCategoryEnum.CONFIG_MEMORY:
                stats = cls._clear_config_memory_cache()
            elif category == CacheCategoryEnum.CAPTCHA:
                stats = cls._clear_captcha_cache()
            elif category == CacheCategoryEnum.PLUGIN_UPDATE:
                stats = cls._clear_plugin_update_cache()
            else:
                logger.warning("Unknown cache category: {}", category.value)
                continue

            total_keys += stats.key_count
            total_size += stats.size_bytes
            cleared.append(category.value)

            logger.info(
                "Cache cleared: category={} keys={} size={}",
                category.value,
                stats.key_count,
                _format_size(stats.size_bytes),
            )

        duration_ms = int((time.monotonic() - start) * 1000)

        logger.info(
            "Cache clear completed: categories={} total_keys={} total_size={} duration={}ms",
            len(cleared),
            total_keys,
            _format_size(total_size),
            duration_ms,
        )

        return CacheClearResponse(
            cleared_categories=cleared,
            cleared_keys=total_keys,
            cleared_size_bytes=total_size,
            cleared_size_human=_format_size(total_size),
            duration_ms=duration_ms,
        )
