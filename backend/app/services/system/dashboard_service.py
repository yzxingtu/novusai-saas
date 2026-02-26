"""
仪表盘统计服务

提供平台端和租户端 Dashboard 统计数据查询。
将 Controller 中的直接 DB 查询下沉到 Service 层。
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_model import utc_now
from app.models.tenant.tenant import Tenant
from app.models.tenant.tenant_admin import TenantAdmin


class AdminDashboardService:
    """平台端仪表盘统计服务"""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_stats(self) -> dict[str, Any]:
        """
        获取平台管理端仪表盘统计

        Returns:
            {"total_tenants", "active_tenants", "total_users", "today_login"}
        """
        total_tenants = await self._count(Tenant)
        active_tenants = await self._count(Tenant, Tenant.is_active.is_(True))
        total_users = await self._count(TenantAdmin)
        today_login = await self._today_login_count()

        return {
            "total_tenants": total_tenants,
            "active_tenants": active_tenants,
            "total_users": total_users,
            "today_login": today_login,
        }

    async def _count(self, model, *extra_filters) -> int:
        """通用计数查询（自动排除软删除）"""
        query = select(func.count()).select_from(model).where(
            model.deleted_at.is_(None),
            *extra_filters,
        )
        return (await self.db.execute(query)).scalar() or 0

    async def _today_login_count(self) -> int:
        """今日登录数"""
        today_start = utc_now().replace(hour=0, minute=0, second=0, microsecond=0)
        query = select(func.count()).select_from(TenantAdmin).where(
            TenantAdmin.deleted_at.is_(None),
            TenantAdmin.last_login_at >= today_start,
        )
        return (await self.db.execute(query)).scalar() or 0


class TenantDashboardService:
    """租户端仪表盘统计服务"""

    def __init__(self, db: AsyncSession, tenant_id: int) -> None:
        self.db = db
        self.tenant_id = tenant_id

    async def get_stats(self) -> dict[str, Any]:
        """
        获取租户端仪表盘统计

        Returns:
            {"total_users", "active_users", "api_calls", "resource_usage"}
        """
        from datetime import timedelta

        total_users = await self._count_admins()
        thirty_days_ago = utc_now().replace(
            hour=0, minute=0, second=0, microsecond=0
        ) - timedelta(days=30)
        active_users = await self._count_admins(
            TenantAdmin.last_login_at >= thirty_days_ago,
        )

        return {
            "total_users": total_users,
            "active_users": active_users,
            "api_calls": 0,
            "resource_usage": 0,
        }

    async def _count_admins(self, *extra_filters) -> int:
        """租户下管理员计数"""
        query = select(func.count()).select_from(TenantAdmin).where(
            TenantAdmin.deleted_at.is_(None),
            TenantAdmin.tenant_id == self.tenant_id,
            *extra_filters,
        )
        return (await self.db.execute(query)).scalar() or 0


__all__ = ["AdminDashboardService", "TenantDashboardService"]
