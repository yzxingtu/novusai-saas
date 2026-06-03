"""
Time helpers for builtin tools.
内置工具时间辅助函数。
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.core.config import settings


def get_current_time(
    timezone_name: str = settings.TIMEZONE,
    format: str = "%Y-%m-%d %H:%M:%S",
) -> str:
    """Get current time / 获取当前时间"""
    import zoneinfo

    try:
        tz = zoneinfo.ZoneInfo(timezone_name)
    except (KeyError, Exception):
        tz = timezone.utc

    now = datetime.now(tz)
    return now.strftime(format)


__all__ = ["get_current_time"]
