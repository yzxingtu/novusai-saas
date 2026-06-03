"""
Dashboard service parts / 仪表盘服务拆分模块
"""

from .admin import AdminDashboardServicePart
from .base import DashboardFormatMixin
from .tenant import TenantDashboardServicePart

__all__ = [
    "AdminDashboardServicePart",
    "DashboardFormatMixin",
    "TenantDashboardServicePart",
]
