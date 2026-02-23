"""
插件 Telemetry 使用统计

记录插件扩展点调用数据到 Redis，按天聚合。
提供统计查询 API。
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from app.core.logging import get_logger

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)


def _today_key(plugin_name: str) -> str:
    """生成当日 Redis key"""
    date_str = datetime.now().strftime("%Y-%m-%d")
    return f"plugin:{plugin_name}:stats:{date_str}"


async def record_call(
    plugin_name: str,
    ext_type: str,
    duration_ms: int = 0,
    success: bool = True,
) -> None:
    """
    记录一次扩展点调用。

    数据存储在 Redis Hash 中，按天聚合。
    """
    try:
        from app.core.redis import cache_get, cache_set

        key = _today_key(plugin_name)

        # 获取或初始化当日统计
        stats = await cache_get(key)
        if not stats:
            stats = {
                "total_calls": 0,
                "success_calls": 0,
                "error_calls": 0,
                "total_duration_ms": 0,
                "by_type": {},
            }

        stats["total_calls"] = stats.get("total_calls", 0) + 1
        if success:
            stats["success_calls"] = stats.get("success_calls", 0) + 1
        else:
            stats["error_calls"] = stats.get("error_calls", 0) + 1
        stats["total_duration_ms"] = stats.get("total_duration_ms", 0) + duration_ms

        # 按扩展类型统计
        by_type = stats.get("by_type", {})
        type_stats = by_type.get(ext_type, {"calls": 0, "errors": 0, "duration_ms": 0})
        type_stats["calls"] = type_stats.get("calls", 0) + 1
        if not success:
            type_stats["errors"] = type_stats.get("errors", 0) + 1
        type_stats["duration_ms"] = type_stats.get("duration_ms", 0) + duration_ms
        by_type[ext_type] = type_stats
        stats["by_type"] = by_type

        await cache_set(key, stats, ttl=86400 * 35)  # 保留 35 天

    except Exception as exc:
        # Telemetry 不应影响主逻辑
        logger.debug("Telemetry record failed for %s: %s", plugin_name, exc)


async def get_stats(plugin_name: str, days: int = 30) -> dict:
    """
    获取插件统计数据。

    Returns:
        {
            "total_calls": N, "success_calls": N, "error_calls": N,
            "avg_duration_ms": N, "by_type": {...},
            "daily": [{"date": "2026-02-23", "calls": N, "errors": N}, ...]
        }
    """
    try:
        from app.core.redis import cache_get

        total_calls = 0
        success_calls = 0
        error_calls = 0
        total_duration_ms = 0
        by_type_agg: dict[str, dict] = {}
        daily: list[dict] = []

        today = datetime.now()
        for i in range(days):
            date = today - timedelta(days=i)
            date_str = date.strftime("%Y-%m-%d")
            key = f"plugin:{plugin_name}:stats:{date_str}"

            stats = await cache_get(key)
            if not stats:
                daily.append({"date": date_str, "calls": 0, "errors": 0})
                continue

            day_calls = stats.get("total_calls", 0)
            day_success = stats.get("success_calls", 0)
            day_errors = stats.get("error_calls", 0)
            day_duration = stats.get("total_duration_ms", 0)

            total_calls += day_calls
            success_calls += day_success
            error_calls += day_errors
            total_duration_ms += day_duration

            daily.append({
                "date": date_str,
                "calls": day_calls,
                "errors": day_errors,
            })

            # 聚合 by_type
            for ext_type, type_stats in stats.get("by_type", {}).items():
                if ext_type not in by_type_agg:
                    by_type_agg[ext_type] = {"calls": 0, "errors": 0, "duration_ms": 0}
                by_type_agg[ext_type]["calls"] += type_stats.get("calls", 0)
                by_type_agg[ext_type]["errors"] += type_stats.get("errors", 0)
                by_type_agg[ext_type]["duration_ms"] += type_stats.get("duration_ms", 0)

        avg_ms = round(total_duration_ms / total_calls) if total_calls > 0 else 0

        return {
            "total_calls": total_calls,
            "success_calls": success_calls,
            "error_calls": error_calls,
            "avg_duration_ms": avg_ms,
            "error_rate": round(error_calls / total_calls * 100, 1) if total_calls > 0 else 0,
            "by_type": by_type_agg,
            "daily": list(reversed(daily)),  # 按时间正序
        }

    except Exception as exc:
        logger.debug("Telemetry get_stats failed for %s: %s", plugin_name, exc)
        return {
            "total_calls": 0, "success_calls": 0, "error_calls": 0,
            "avg_duration_ms": 0, "error_rate": 0, "by_type": {}, "daily": [],
        }
