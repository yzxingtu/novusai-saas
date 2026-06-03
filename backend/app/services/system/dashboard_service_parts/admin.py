"""
Admin dashboard service parts / 平台端仪表盘拆分模块
"""

from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import Any

from sqlalchemy import case, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_model import utc_now
from app.core.logging import LogManager
from app.models.ai.call_log import AICallLog
from app.models.system.operation_log import OperationLog
from app.models.system.plugin import Plugin
from app.models.tenant.attachment import Attachment
from app.models.tenant.tenant import Tenant
from app.models.tenant.tenant_admin import TenantAdmin

from .base import DashboardFormatMixin

logger = LogManager.get_logger("dashboard")


class AdminDashboardServicePart(DashboardFormatMixin):
    db: AsyncSession

    async def get_overview(
        self,
        *,
        activity_limit: int = 12,
        growth_days: int = 30,
    ) -> dict[str, Any]:
        """聚合平台仪表盘快照 / Aggregate platform dashboard snapshot."""
        (
            stats,
            health,
            ai_overview,
            storage_overview,
            plugin_overview,
            tenant_growth,
            recent_activities,
        ) = await asyncio.gather(
            self.get_stats(),
            self.get_system_health(),
            self.get_ai_overview(),
            self.get_storage_overview(),
            self.get_plugin_overview(),
            self.get_tenant_growth(days=growth_days),
            self.get_recent_activities(limit=activity_limit),
        )

        return {
            "generated_at": self._format_dt(utc_now()),
            "stats": stats,
            "health": health,
            "ai_overview": ai_overview,
            "storage_overview": storage_overview,
            "plugin_overview": plugin_overview,
            "tenant_growth": tenant_growth,
            "recent_activities": recent_activities,
        }

    async def get_stats(self) -> dict[str, Any]:
        """
        获取平台管理端仪表盘统计（基础）/ Get platform dashboard stats (basic).

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

    # ── A1: 系统健康状态 / System health ──

    async def get_system_health(self) -> dict[str, Any]:
        """
        系统健康状态：Redis/Celery/DB 连通性 + 内存 + 运行时间 / System health: Redis/Celery/DB + memory + uptime.

        Returns:
            {"status", "redis", "database", "celery", "memory_mb", "uptime_seconds"}
        """
        import os
        import time

        redis_ok = await self._check_redis()
        db_ok = await self._check_database()
        celery_ok = await self._check_celery()

        overall = "healthy"
        if not redis_ok or not db_ok:
            overall = "degraded"
        if not db_ok:
            overall = "unhealthy"

        # 内存使用 + 进程运行时间（复用同一个 Process 对象）/ Memory usage + process uptime (reuse Process)
        memory_mb = 0.0
        uptime_seconds = 0
        try:
            import psutil

            process = psutil.Process(os.getpid())
            memory_mb = round(process.memory_info().rss / 1024 / 1024, 1)
            uptime_seconds = int(time.time() - process.create_time())
        except Exception:
            logger.debug("psutil unavailable, skipping memory/uptime metrics")

        return {
            "status": overall,
            "redis": {"connected": redis_ok},
            "database": {"connected": db_ok},
            "celery": {"connected": celery_ok},
            "memory_mb": memory_mb,
            "uptime_seconds": uptime_seconds,
        }

    async def _check_redis(self) -> bool:
        try:
            from app.core.redis import RedisManager

            return await RedisManager.health_check()
        except Exception:
            return False

    async def _check_database(self) -> bool:
        try:
            await self.db.execute(text("SELECT 1"))
            return True
        except Exception:
            return False

    async def _check_celery(self) -> bool:
        try:
            import anyio

            def _sync_ping() -> bool:
                from app.celery_app import celery_app

                insp = celery_app.control.inspect(timeout=2.0)
                return bool(insp.ping())

            return await anyio.to_thread.run_sync(_sync_ping)
        except Exception:
            return False

    # ── A2: AI 使用概览 / AI usage overview ──

    async def get_ai_overview(self) -> dict[str, Any]:
        """
        AI 使用概览：总调用/Token/活跃供应商/今日调用 / AI usage overview: calls/tokens/providers/today.

        Returns:
            {"total_calls", "total_tokens", "total_cost", "active_providers",
             "today_calls", "today_tokens", "success_rate"}
        """
        from app.enums.ai import CallStatusEnum

        # 总体统计 / Overall stats
        total_row = await self.db.execute(
            select(
                func.count(AICallLog.id).label("total_calls"),
                func.coalesce(func.sum(AICallLog.total_tokens), 0).label(
                    "total_tokens"
                ),
                func.coalesce(func.sum(AICallLog.cost), 0).label("total_cost"),
                func.count(func.distinct(AICallLog.provider_id)).label(
                    "active_providers"
                ),
                func.sum(
                    case((AICallLog.status == CallStatusEnum.SUCCESS.value, 1), else_=0)
                ).label("success_calls"),
            )
        )
        row = total_row.one()

        # 今日统计 / Today stats
        today_start = utc_now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_row = await self.db.execute(
            select(
                func.count(AICallLog.id).label("today_calls"),
                func.coalesce(func.sum(AICallLog.total_tokens), 0).label(
                    "today_tokens"
                ),
            ).where(AICallLog.created_at >= today_start)
        )
        today = today_row.one()

        total_calls = row.total_calls or 0
        success_calls = row.success_calls or 0
        success_rate = (
            round(success_calls / total_calls * 100, 1) if total_calls > 0 else 100.0
        )

        return {
            "total_calls": total_calls,
            "total_tokens": int(row.total_tokens),
            "total_cost": float(row.total_cost),
            "active_providers": row.active_providers or 0,
            "today_calls": today.today_calls or 0,
            "today_tokens": int(today.today_tokens),
            "success_rate": success_rate,
        }

    # ── A3: 存储使用概览 / Storage usage overview ──

    async def get_storage_overview(self) -> dict[str, Any]:
        """
        存储使用概览：总文件数/总大小/驱动分布 / Storage overview: file count, size, driver distribution.

        Returns:
            {"total_files", "total_size_bytes", "total_size_mb", "driver_distribution"}
        """
        # 总体统计 / Overall stats
        total_row = await self.db.execute(
            select(
                func.count(Attachment.id).label("total_files"),
                func.coalesce(func.sum(Attachment.size), 0).label("total_size"),
            ).where(Attachment.is_deleted.is_(False))
        )
        row = total_row.one()
        total_size = int(row.total_size)

        # 驱动分布 / Driver distribution
        driver_rows = await self.db.execute(
            select(
                Attachment.driver,
                func.count(Attachment.id).label("file_count"),
                func.coalesce(func.sum(Attachment.size), 0).label("size"),
            )
            .where(
                Attachment.is_deleted.is_(False),
            )
            .group_by(Attachment.driver)
        )
        driver_distribution = [
            {"driver": r.driver, "file_count": r.file_count, "size_bytes": int(r.size)}
            for r in driver_rows.all()
        ]

        return {
            "total_files": row.total_files or 0,
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / 1024 / 1024, 2),
            "driver_distribution": driver_distribution,
        }

    # ── A4: 插件状态概览 / Plugin status overview ──

    async def get_plugin_overview(self) -> dict[str, Any]:
        """
        插件状态概览：已安装/已启用/已禁用/错误数 / Plugin status overview: installed/enabled/disabled/errors.

        Returns:
            {"total", "enabled", "disabled", "error_count"}
        """
        from app.enums.plugin import PluginStatusEnum

        row = await self.db.execute(
            select(
                func.count(Plugin.id).label("total"),
                func.sum(
                    case((Plugin.status == PluginStatusEnum.ENABLED.value, 1), else_=0)
                ).label("enabled"),
                func.sum(
                    case((Plugin.status == PluginStatusEnum.DISABLED.value, 1), else_=0)
                ).label("disabled"),
                func.sum(case((Plugin.error_count > 0, 1), else_=0)).label(
                    "with_errors"
                ),
            ).where(Plugin.is_deleted.is_(False))
        )
        r = row.one()

        return {
            "total": r.total or 0,
            "enabled": int(r.enabled or 0),
            "disabled": int(r.disabled or 0),
            "error_count": int(r.with_errors or 0),
        }

    # ── A5: 企业增长趋势 / Tenant growth trend ──

    async def get_tenant_growth(self, days: int = 30) -> list[dict[str, Any]]:
        """
        企业增长趋势：近 N 天每日新增企业数 / Tenant growth trend: daily new tenants in last N days.

        Returns:
            [{"date": "2026-02-20", "count": 3}, ...]
        """
        cutoff = utc_now() - timedelta(days=days)
        rows = await self.db.execute(
            select(
                func.date(Tenant.created_at).label("date"),
                func.count(Tenant.id).label("count"),
            )
            .where(
                Tenant.created_at >= cutoff,
                Tenant.deleted_at.is_(None),
            )
            .group_by(func.date(Tenant.created_at))
            .order_by(func.date(Tenant.created_at))
        )

        return [{"date": str(r.date), "count": r.count} for r in rows.all()]

    # ── A6: 近期活动时间线 / Recent activity timeline ──

    async def get_recent_activities(self, limit: int = 20) -> list[dict[str, Any]]:
        """
        近期活动时间线：最近 N 条操作日志 / Recent activity timeline: last N operation logs.

        Returns:
            [{"id", "username", "action", "module", "path", "method", "ip", "created_at"}, ...]
        """
        from app.services.system import dashboard_service as dashboard_service_facade

        rows = await self.db.execute(
            select(OperationLog)
            .where(OperationLog.is_deleted.is_(False))
            .where(dashboard_service_facade._meaningful_activity_condition())
            .order_by(OperationLog.created_at.desc())
            .limit(limit)
        )
        items = rows.scalars().all()
        refs = {
            ref
            for log in items
            if (ref := dashboard_service_facade._operation_log_identity_ref(log))
            is not None
        }
        identity_meta_map = (
            await dashboard_service_facade._load_operation_log_identity_meta_map(
                self.db,
                refs,
            )
        )

        return [
            dashboard_service_facade._serialize_recent_activity(
                log,
                identity_meta_map.get(
                    dashboard_service_facade._operation_log_identity_ref(log)
                ),
                format_dt=self._format_dt,
            )
            for log in items
        ]

    # ── private helpers / 私有辅助 ──

    async def _count(self, model, *extra_filters) -> int:
        """通用计数查询（自动排除软删除）/ Generic count query (excludes soft-deleted)"""
        query = (
            select(func.count())
            .select_from(model)
            .where(
                model.deleted_at.is_(None),
                *extra_filters,
            )
        )
        return (await self.db.execute(query)).scalar() or 0

    async def _today_login_count(self) -> int:
        """今日登录数 / Today's login count"""
        today_start = utc_now().replace(hour=0, minute=0, second=0, microsecond=0)
        query = (
            select(func.count())
            .select_from(TenantAdmin)
            .where(
                TenantAdmin.deleted_at.is_(None),
                TenantAdmin.last_login_at >= today_start,
            )
        )
        return (await self.db.execute(query)).scalar() or 0
