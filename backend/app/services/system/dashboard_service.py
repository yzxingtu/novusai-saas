"""
仪表盘统计服务

提供平台端和租户端 Dashboard 统计数据查询。
将 Controller 中的直接 DB 查询下沉到 Service 层。

A1-A6: Admin Dashboard 统计
B1-B4: Tenant Dashboard 统计
"""

from __future__ import annotations

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

logger = LogManager.get_logger("dashboard")


class AdminDashboardService:
    """平台端仪表盘统计服务"""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_stats(self) -> dict[str, Any]:
        """
        获取平台管理端仪表盘统计（基础）

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

    # ── A1: 系统健康状态 ──

    async def get_system_health(self) -> dict[str, Any]:
        """
        系统健康状态：Redis/Celery/DB 连通性 + 内存 + 运行时间

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

        # 内存使用 + 进程运行时间（复用同一个 Process 对象）
        memory_mb = 0.0
        uptime_seconds = 0
        try:
            import psutil
            process = psutil.Process(os.getpid())
            memory_mb = round(process.memory_info().rss / 1024 / 1024, 1)
            uptime_seconds = int(time.time() - process.create_time())
        except Exception:
            pass

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

    # ── A2: AI 使用概览 ──

    async def get_ai_overview(self) -> dict[str, Any]:
        """
        AI 使用概览：总调用/Token/活跃供应商/今日调用

        Returns:
            {"total_calls", "total_tokens", "total_cost", "active_providers",
             "today_calls", "today_tokens", "success_rate"}
        """
        from app.enums.ai import CallStatusEnum

        # 总体统计
        total_row = await self.db.execute(
            select(
                func.count(AICallLog.id).label("total_calls"),
                func.coalesce(func.sum(AICallLog.total_tokens), 0).label("total_tokens"),
                func.coalesce(func.sum(AICallLog.cost), 0).label("total_cost"),
                func.count(func.distinct(AICallLog.provider_id)).label("active_providers"),
                func.sum(case(
                    (AICallLog.status == CallStatusEnum.SUCCESS.value, 1), else_=0
                )).label("success_calls"),
            )
        )
        row = total_row.one()

        # 今日统计
        today_start = utc_now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_row = await self.db.execute(
            select(
                func.count(AICallLog.id).label("today_calls"),
                func.coalesce(func.sum(AICallLog.total_tokens), 0).label("today_tokens"),
            ).where(AICallLog.created_at >= today_start)
        )
        today = today_row.one()

        total_calls = row.total_calls or 0
        success_calls = row.success_calls or 0
        success_rate = round(success_calls / total_calls * 100, 1) if total_calls > 0 else 100.0

        return {
            "total_calls": total_calls,
            "total_tokens": int(row.total_tokens),
            "total_cost": float(row.total_cost),
            "active_providers": row.active_providers or 0,
            "today_calls": today.today_calls or 0,
            "today_tokens": int(today.today_tokens),
            "success_rate": success_rate,
        }

    # ── A3: 存储使用概览 ──

    async def get_storage_overview(self) -> dict[str, Any]:
        """
        存储使用概览：总文件数/总大小/驱动分布

        Returns:
            {"total_files", "total_size_bytes", "total_size_mb", "driver_distribution"}
        """
        # 总体统计
        total_row = await self.db.execute(
            select(
                func.count(Attachment.id).label("total_files"),
                func.coalesce(func.sum(Attachment.size), 0).label("total_size"),
            ).where(Attachment.is_deleted.is_(False))
        )
        row = total_row.one()
        total_size = int(row.total_size)

        # 驱动分布
        driver_rows = await self.db.execute(
            select(
                Attachment.driver,
                func.count(Attachment.id).label("file_count"),
                func.coalesce(func.sum(Attachment.size), 0).label("size"),
            ).where(
                Attachment.is_deleted.is_(False),
            ).group_by(Attachment.driver)
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

    # ── A4: 插件状态概览 ──

    async def get_plugin_overview(self) -> dict[str, Any]:
        """
        插件状态概览：已安装/已启用/已禁用/错误数

        Returns:
            {"total", "enabled", "disabled", "error_count"}
        """
        from app.enums.plugin import PluginStatusEnum

        row = await self.db.execute(
            select(
                func.count(Plugin.id).label("total"),
                func.sum(case(
                    (Plugin.status == PluginStatusEnum.ENABLED.value, 1), else_=0
                )).label("enabled"),
                func.sum(case(
                    (Plugin.status == PluginStatusEnum.DISABLED.value, 1), else_=0
                )).label("disabled"),
                func.sum(case(
                    (Plugin.error_count > 0, 1), else_=0
                )).label("with_errors"),
            ).where(Plugin.is_deleted.is_(False))
        )
        r = row.one()

        return {
            "total": r.total or 0,
            "enabled": int(r.enabled or 0),
            "disabled": int(r.disabled or 0),
            "error_count": int(r.with_errors or 0),
        }

    # ── A5: 租户增长趋势 ──

    async def get_tenant_growth(self, days: int = 30) -> list[dict[str, Any]]:
        """
        租户增长趋势：近 N 天每日新增租户数

        Returns:
            [{"date": "2026-02-20", "count": 3}, ...]
        """
        cutoff = utc_now() - timedelta(days=days)
        rows = await self.db.execute(
            select(
                func.date(Tenant.created_at).label("date"),
                func.count(Tenant.id).label("count"),
            ).where(
                Tenant.created_at >= cutoff,
                Tenant.deleted_at.is_(None),
            ).group_by(func.date(Tenant.created_at))
            .order_by(func.date(Tenant.created_at))
        )

        return [
            {"date": str(r.date), "count": r.count}
            for r in rows.all()
        ]

    # ── A6: 近期活动时间线 ──

    async def get_recent_activities(self, limit: int = 20) -> list[dict[str, Any]]:
        """
        近期活动时间线：最近 N 条操作日志

        Returns:
            [{"id", "username", "action", "module", "path", "method", "ip", "created_at"}, ...]
        """
        rows = await self.db.execute(
            select(OperationLog)
            .where(OperationLog.is_deleted.is_(False))
            .order_by(OperationLog.created_at.desc())
            .limit(limit)
        )
        items = rows.scalars().all()

        return [
            {
                "id": log.id,
                "username": log.username,
                "nickname": log.nickname,
                "user_type": log.user_type,
                "action": log.action,
                "module": log.module,
                "resource": log.resource,
                "path": log.path,
                "method": log.method,
                "status_code": log.status_code,
                "ip": log.ip,
                "duration_ms": log.duration_ms,
                "created_at": str(log.created_at) if log.created_at else None,
            }
            for log in items
        ]

    # ── private helpers ──

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
        获取租户端仪表盘统计（增强版）

        Returns:
            {"total_users", "active_users", "api_calls", "total_tokens",
             "storage_used_bytes", "storage_used_mb"}
        """
        total_users = await self._count_admins()
        thirty_days_ago = utc_now().replace(
            hour=0, minute=0, second=0, microsecond=0
        ) - timedelta(days=30)
        active_users = await self._count_admins(
            TenantAdmin.last_login_at >= thirty_days_ago,
        )

        # B1: 真实 AI 调用统计（替换硬编码 0）
        ai_stats = await self._get_ai_stats()

        # 存储使用量
        storage_used = await self._get_storage_used()

        return {
            "total_users": total_users,
            "active_users": active_users,
            "api_calls": ai_stats["total_calls"],
            "total_tokens": ai_stats["total_tokens"],
            "total_cost": ai_stats["total_cost"],
            "storage_used_bytes": storage_used,
            "storage_used_mb": round(storage_used / 1024 / 1024, 2) if storage_used else 0,
        }

    # ── B1: 真实 AI 调用统计 ──

    async def _get_ai_stats(self) -> dict[str, Any]:
        """租户级 AI 调用汇总"""
        row = await self.db.execute(
            select(
                func.count(AICallLog.id).label("total_calls"),
                func.coalesce(func.sum(AICallLog.total_tokens), 0).label("total_tokens"),
                func.coalesce(func.sum(AICallLog.cost), 0).label("total_cost"),
            ).where(AICallLog.tenant_id == self.tenant_id)
        )
        r = row.one()
        return {
            "total_calls": r.total_calls or 0,
            "total_tokens": int(r.total_tokens),
            "total_cost": float(r.total_cost),
        }

    # ── B2: AI 使用趋势 ──

    async def get_ai_trend(self, days: int = 7) -> list[dict[str, Any]]:
        """
        近 N 天每日 AI 调用量 + Token 量

        Returns:
            [{"date": "2026-02-20", "calls": 10, "tokens": 5000}, ...]
        """
        cutoff = utc_now() - timedelta(days=days)
        rows = await self.db.execute(
            select(
                func.date(AICallLog.created_at).label("date"),
                func.count(AICallLog.id).label("calls"),
                func.coalesce(func.sum(AICallLog.total_tokens), 0).label("tokens"),
            ).where(
                AICallLog.tenant_id == self.tenant_id,
                AICallLog.created_at >= cutoff,
            ).group_by(func.date(AICallLog.created_at))
            .order_by(func.date(AICallLog.created_at))
        )

        return [
            {"date": str(r.date), "calls": r.calls, "tokens": int(r.tokens)}
            for r in rows.all()
        ]

    # ── B3: 存储使用详情 ──

    async def get_storage_detail(self) -> dict[str, Any]:
        """
        存储使用详情：已用大小/文件数/分类分布

        Returns:
            {"total_files", "total_size_bytes", "total_size_mb",
             "type_distribution": [{"mime_type", "count", "size"}]}
        """
        total_row = await self.db.execute(
            select(
                func.count(Attachment.id).label("total_files"),
                func.coalesce(func.sum(Attachment.size), 0).label("total_size"),
            ).where(
                Attachment.tenant_id == self.tenant_id,
                Attachment.is_deleted.is_(False),
            )
        )
        row = total_row.one()
        total_size = int(row.total_size)

        # 按 MIME 类型分布
        type_rows = await self.db.execute(
            select(
                Attachment.mime_type,
                func.count(Attachment.id).label("count"),
                func.coalesce(func.sum(Attachment.size), 0).label("size"),
            ).where(
                Attachment.tenant_id == self.tenant_id,
                Attachment.is_deleted.is_(False),
            ).group_by(Attachment.mime_type)
            .order_by(func.sum(Attachment.size).desc())
            .limit(10)
        )

        return {
            "total_files": row.total_files or 0,
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / 1024 / 1024, 2),
            "type_distribution": [
                {"mime_type": r.mime_type or "unknown", "count": r.count, "size_bytes": int(r.size)}
                for r in type_rows.all()
            ],
        }

    # ── B4: 近期活动 ──

    async def get_recent_activities(self, limit: int = 20) -> list[dict[str, Any]]:
        """租户级近期操作日志"""
        rows = await self.db.execute(
            select(OperationLog)
            .where(
                OperationLog.tenant_id == self.tenant_id,
                OperationLog.is_deleted.is_(False),
            )
            .order_by(OperationLog.created_at.desc())
            .limit(limit)
        )
        items = rows.scalars().all()

        return [
            {
                "id": log.id,
                "username": log.username,
                "action": log.action,
                "module": log.module,
                "path": log.path,
                "method": log.method,
                "status_code": log.status_code,
                "duration_ms": log.duration_ms,
                "created_at": str(log.created_at) if log.created_at else None,
            }
            for log in items
        ]

    async def _get_storage_used(self) -> int:
        """租户存储总占用"""
        result = await self.db.execute(
            select(func.coalesce(func.sum(Attachment.size), 0)).where(
                Attachment.tenant_id == self.tenant_id,
                Attachment.is_deleted.is_(False),
            )
        )
        return int(result.scalar() or 0)

    async def _count_admins(self, *extra_filters) -> int:
        """租户下管理员计数"""
        query = select(func.count()).select_from(TenantAdmin).where(
            TenantAdmin.deleted_at.is_(None),
            TenantAdmin.tenant_id == self.tenant_id,
            *extra_filters,
        )
        return (await self.db.execute(query)).scalar() or 0


__all__ = ["AdminDashboardService", "TenantDashboardService"]
