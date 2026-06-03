"""
仪表盘统计服务 / Dashboard Service

提供平台端和企业端 Dashboard 统计数据查询。
Provides platform and tenant Dashboard statistics data queries.
将 Controller 中的直接 DB 查询下沉到 Service 层。

A1-A6: Admin Dashboard 统计
B1-B4: Tenant Dashboard 统计

本模块为 facade，具体逻辑拆分到 dashboard_service_parts/*。
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from .dashboard_service_parts.activity import (
    _load_operation_log_identity_meta_map,
    _meaningful_activity_condition,
    _operation_log_identity_ref,
    _serialize_recent_activity,
)
from .dashboard_service_parts.admin import AdminDashboardServicePart
from .dashboard_service_parts.tenant import TenantDashboardServicePart
from .dashboard_service_parts.visibility import (
    _visible_agent_condition,
    _visible_kb_condition,
)


class AdminDashboardService(AdminDashboardServicePart):
    """平台端仪表盘统计服务 / Platform dashboard statistics service"""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db


class TenantDashboardService(TenantDashboardServicePart):
    """企业端仪表盘统计服务 / Tenant dashboard statistics service"""

    def __init__(self, db: AsyncSession, tenant_id: int) -> None:
        self.db = db
        self.tenant_id = tenant_id


__all__ = [
    "AdminDashboardService",
    "TenantDashboardService",
    "_load_operation_log_identity_meta_map",
    "_meaningful_activity_condition",
    "_operation_log_identity_ref",
    "_serialize_recent_activity",
    "_visible_agent_condition",
    "_visible_kb_condition",
]
