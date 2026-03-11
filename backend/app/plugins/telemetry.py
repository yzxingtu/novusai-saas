"""
Plugin telemetry usage statistics.
/ 插件 Telemetry 使用统计

Uses Redis Hash + HINCRBY atomic operations to aggregate plugin extension point
call data per day. Counts are never lost under high concurrency.
/ 使用 Redis Hash + HINCRBY 原子操作按天聚合，高并发不丢失。
"""

from __future__ import annotations

from datetime import timedelta

from app.core.base_model import utc_now
from app.core.logging import get_logger

logger = get_logger(__name__)

_TTL_SECONDS = 86400 * 35  # 35 days / 35 天


def _day_key(plugin_name: str, date_str: str | None = None) -> str:
    """Generate Redis Hash key for a given day / 生成某日 Redis Hash key"""
    if date_str is None:
        date_str = utc_now().strftime("%Y-%m-%d")
    return f"plugin:{plugin_name}:stats:{date_str}"


async def record_call(
    plugin_name: str,
    ext_type: str,
    duration_ms: int = 0,
    success: bool = True,
) -> None:
    """
    Record one extension point call (atomic operation).
    / 记录一次扩展点调用（原子操作）。

    Uses Redis Hash + HINCRBY for concurrency safety, aggregated per day.
    / 使用 Redis Hash + HINCRBY 保证并发安全。
    Hash fields:
      total_calls, success_calls, error_calls, total_duration_ms,
      type:{ext_type}:calls, type:{ext_type}:errors, type:{ext_type}:duration_ms
    """
    try:
        from app.core.redis import get_redis_client

        client = get_redis_client()
        key = _day_key(plugin_name)

        async with client.pipeline(transaction=False) as pipe:
            pipe.hincrby(key, "total_calls", 1)
            if success:
                pipe.hincrby(key, "success_calls", 1)
            else:
                pipe.hincrby(key, "error_calls", 1)
            pipe.hincrby(key, "total_duration_ms", duration_ms)
            pipe.hincrby(key, f"type:{ext_type}:calls", 1)
            if not success:
                pipe.hincrby(key, f"type:{ext_type}:errors", 1)
            pipe.hincrby(key, f"type:{ext_type}:duration_ms", duration_ms)
            pipe.expire(key, 86400 * 35)  # Retain 35 days / 保留 35 天
            await pipe.execute()

    except Exception as exc:
        # Telemetry should not affect main logic / 不应影响主逻辑
        logger.debug("Telemetry record failed for %s: %s", plugin_name, exc)


def _parse_hash(raw: dict[bytes | str, bytes | str]) -> dict[str, int]:
    """Convert Redis Hash raw result to {str: int} dict / 将 Redis Hash 原始结果转为字典"""
    result: dict[str, int] = {}
    for k, v in raw.items():
        field = k.decode() if isinstance(k, bytes) else k
        try:
            result[field] = int(v)
        except (ValueError, TypeError):
            result[field] = 0
    return result


async def get_stats(plugin_name: str, days: int = 30) -> dict:
    """
    Get plugin statistics data.
    / 获取插件统计数据。

    Returns:
        {
            "total_calls": N, "success_calls": N, "error_calls": N,
            "avg_duration_ms": N, "by_type": {...},
            "daily": [{"date": "2026-02-23", "calls": N, "errors": N}, ...]
        }
    """
    try:
        from app.core.redis import get_redis_client

        client = get_redis_client()

        total_calls = 0
        success_calls = 0
        error_calls = 0
        total_duration_ms = 0
        by_type_agg: dict[str, dict] = {}
        daily: list[dict] = []

        today = utc_now()
        for i in range(days):
            date = today - timedelta(days=i)
            date_str = date.strftime("%Y-%m-%d")
            key = _day_key(plugin_name, date_str)

            raw = await client.hgetall(key)
            if not raw:
                daily.append({"date": date_str, "calls": 0, "errors": 0})
                continue

            fields = _parse_hash(raw)

            day_calls = fields.get("total_calls", 0)
            day_success = fields.get("success_calls", 0)
            day_errors = fields.get("error_calls", 0)
            day_duration = fields.get("total_duration_ms", 0)

            total_calls += day_calls
            success_calls += day_success
            error_calls += day_errors
            total_duration_ms += day_duration

            daily.append({
                "date": date_str,
                "calls": day_calls,
                "errors": day_errors,
            })

            # Aggregate by_type — from type:{ext}:calls / type:{ext}:errors / type:{ext}:duration_ms
            # / 聚合 by_type
            seen_types: set[str] = set()
            for field_name in fields:
                if field_name.startswith("type:") and field_name.endswith(":calls"):
                    ext = field_name[5:-6]  # strip "type:" and ":calls"
                    seen_types.add(ext)

            for ext in seen_types:
                if ext not in by_type_agg:
                    by_type_agg[ext] = {"calls": 0, "errors": 0, "duration_ms": 0}
                by_type_agg[ext]["calls"] += fields.get(f"type:{ext}:calls", 0)
                by_type_agg[ext]["errors"] += fields.get(f"type:{ext}:errors", 0)
                by_type_agg[ext]["duration_ms"] += fields.get(f"type:{ext}:duration_ms", 0)

        avg_ms = round(total_duration_ms / total_calls) if total_calls > 0 else 0

        return {
            "total_calls": total_calls,
            "success_calls": success_calls,
            "error_calls": error_calls,
            "avg_duration_ms": avg_ms,
            "error_rate": round(error_calls / total_calls * 100, 1) if total_calls > 0 else 0,
            "by_type": by_type_agg,
            "daily": list(reversed(daily)),  # Chronological order / 按时间正序
        }

    except Exception as exc:
        logger.debug("Telemetry get_stats failed for %s: %s", plugin_name, exc)
        return {
            "total_calls": 0, "success_calls": 0, "error_calls": 0,
            "avg_duration_ms": 0, "error_rate": 0, "by_type": {}, "daily": [],
        }
