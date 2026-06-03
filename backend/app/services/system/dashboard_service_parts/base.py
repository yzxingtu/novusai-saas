"""
Dashboard shared helpers / 仪表盘共享辅助
"""

from __future__ import annotations

from datetime import datetime, timezone


class DashboardFormatMixin:
    @staticmethod
    def _format_dt(dt: datetime | None) -> str | None:
        if dt is None:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.isoformat()
