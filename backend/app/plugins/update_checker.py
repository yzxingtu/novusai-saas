"""
Plugin update checker.
/ 插件更新检查器

Automatically checks daily whether installed plugins have new versions, caches results.
Notification only, no auto-update.
/ 每天自动检查新版本，仅通知不自动更新。
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from app.core.logging import get_logger

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)

# In-memory cache: last check result / 内存缓存：上次检查结果
_update_cache: dict[str, object] = {}
_CACHE_KEY = "plugin_updates"
_CACHE_TTL = 86400  # 24 hours / 24 小时


async def check_updates(db: AsyncSession) -> list[dict]:
    """
    Check available updates for installed plugins.
    / 检查已安装插件的可用更新。

    Results cached for 24 hours. / 结果缓存 24 小时。

    Returns:
        [{name, current_version, latest_version, slug, changelog?}, ...]
    """
    # Check cache / 检查缓存
    cached = _update_cache.get(_CACHE_KEY)
    if cached:
        cache_time, cache_data = cached  # type: ignore
        if time.time() - cache_time < _CACHE_TTL:
            return cache_data  # type: ignore

    from sqlalchemy import select

    from app.models.system.plugin import Plugin
    from app.plugins.marketplace import MarketplaceClient

    # Query installed plugins / 查询已安装插件
    result = await db.execute(
        select(Plugin.name, Plugin.version, Plugin.marketplace_slug).where(
            Plugin.is_deleted.is_(False),
        )
    )
    installed = [
        {
            "name": row[0],
            "version": row[1],
            "marketplace_slug": row[2],
        }
        for row in result.all()
    ]

    if not installed:
        _update_cache[_CACHE_KEY] = (time.time(), [])
        return []

    # Check updates from marketplace / 从市场检查更新
    client = MarketplaceClient(db)
    updates = await client.check_for_updates(installed)

    # Cache result / 缓存结果
    _update_cache[_CACHE_KEY] = (time.time(), updates)

    if updates:
        logger.info(
            "Found %d plugin update(s): %s",
            len(updates),
            ", ".join(f"{u['name']} {u['current_version']}→{u['latest_version']}" for u in updates),
        )

    return updates


def clear_update_cache() -> None:
    """Clear update cache (for manual refresh) / 清除更新缓存"""
    _update_cache.pop(_CACHE_KEY, None)


async def get_update_count(db: AsyncSession) -> int:
    """Get updatable plugin count (for menu badge) / 获取可更新插件数量"""
    updates = await check_updates(db)
    return len(updates)
