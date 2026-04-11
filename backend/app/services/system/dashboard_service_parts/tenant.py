"""
Tenant dashboard service parts / 企业端仪表盘拆分模块
"""

from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_model import utc_now
from app.models.ai.agent import Agent
from app.models.ai.agent_conversation import AgentConversation
from app.models.ai.call_log import AICallLog
from app.models.ai.knowledge_base import KnowledgeBase
from app.models.ai.knowledge_document import KnowledgeDocument
from app.models.system.operation_log import OperationLog
from app.models.tenant.attachment import Attachment
from app.models.tenant.tenant_admin import TenantAdmin

from .base import DashboardFormatMixin
from .visibility import _visible_agent_condition, _visible_kb_condition


class TenantDashboardServicePart(DashboardFormatMixin):
    db: AsyncSession
    tenant_id: int

    async def get_overview(
        self,
        *,
        activity_limit: int = 10,
        trend_days: int = 14,
    ) -> dict[str, Any]:
        """聚合企业仪表盘快照 / Aggregate tenant dashboard snapshot."""
        stats, ai_trend, storage_detail, recent_activities = await asyncio.gather(
            self.get_stats(),
            self.get_ai_trend(days=trend_days),
            self.get_storage_detail(),
            self.get_recent_activities(limit=activity_limit),
        )

        return {
            "generated_at": self._format_dt(utc_now()),
            "stats": stats,
            "ai_trend": ai_trend,
            "storage_detail": storage_detail,
            "recent_activities": recent_activities,
        }

    async def get_stats(self) -> dict[str, Any]:
        """
        获取企业端仪表盘统计（增强版）/ Get tenant dashboard stats (enhanced).

        Returns:
            {"total_users", "active_users", "api_calls", "total_tokens",
             "total_cost", "storage_used_bytes", "storage_used_mb",
             "total_agents", "total_knowledge_bases", "total_kb_documents",
             "monthly_conversations"}
        """
        thirty_days_ago = utc_now().replace(
            hour=0, minute=0, second=0, microsecond=0
        ) - timedelta(days=30)

        total_users = await self._count_admins()
        active_users = await self._count_admins(
            TenantAdmin.last_login_at >= thirty_days_ago,
        )

        # B1: 真实 AI 调用统计 / B1: Real AI call stats
        ai_stats = await self._get_ai_stats()

        # 存储使用量 / Storage usage
        storage_used = await self._get_storage_used()

        # B5: 智能体 & 知识库 & 对话统计 / B5: Agent & KB & conversation stats
        total_agents = await self._count_visible_agents()
        total_knowledge_bases = await self._count_visible_knowledge_bases()
        total_kb_documents = await self._count_visible_knowledge_documents()
        monthly_conversations = await self._count_tenant_model(
            AgentConversation,
            AgentConversation.created_at >= thirty_days_ago,
        )

        return {
            "total_users": total_users,
            "active_users": active_users,
            "api_calls": ai_stats["total_calls"],
            "total_tokens": ai_stats["total_tokens"],
            "total_cost": ai_stats["total_cost"],
            "storage_used_bytes": storage_used,
            "storage_used_mb": round(storage_used / 1024 / 1024, 2)
            if storage_used
            else 0,
            "total_agents": total_agents,
            "total_knowledge_bases": total_knowledge_bases,
            "total_kb_documents": total_kb_documents,
            "monthly_conversations": monthly_conversations,
        }

    # ── B1: 真实 AI 调用统计 / Real AI call stats ──

    async def _get_ai_stats(self) -> dict[str, Any]:
        """企业级 AI 调用汇总 / Tenant-level AI call summary"""
        row = await self.db.execute(
            select(
                func.count(AICallLog.id).label("total_calls"),
                func.coalesce(func.sum(AICallLog.total_tokens), 0).label(
                    "total_tokens"
                ),
                func.coalesce(func.sum(AICallLog.cost), 0).label("total_cost"),
            ).where(AICallLog.tenant_id == self.tenant_id)
        )
        r = row.one()
        return {
            "total_calls": r.total_calls or 0,
            "total_tokens": int(r.total_tokens),
            "total_cost": float(r.total_cost),
        }

    # ── B2: AI 使用趋势 / AI usage trend ──

    async def get_ai_trend(self, days: int = 7) -> list[dict[str, Any]]:
        """
        近 N 天每日 AI 调用量 + Token 量 / Daily AI calls + tokens for last N days.

        Returns:
            [{"date": "2026-02-20", "calls": 10, "tokens": 5000}, ...]
        """
        cutoff = utc_now() - timedelta(days=days)
        rows = await self.db.execute(
            select(
                func.date(AICallLog.created_at).label("date"),
                func.count(AICallLog.id).label("calls"),
                func.coalesce(func.sum(AICallLog.total_tokens), 0).label("tokens"),
            )
            .where(
                AICallLog.tenant_id == self.tenant_id,
                AICallLog.created_at >= cutoff,
            )
            .group_by(func.date(AICallLog.created_at))
            .order_by(func.date(AICallLog.created_at))
        )

        return [
            {"date": str(r.date), "calls": r.calls, "tokens": int(r.tokens)}
            for r in rows.all()
        ]

    # ── B3: 存储使用详情 / Storage usage detail ──

    async def get_storage_detail(self) -> dict[str, Any]:
        """
        存储使用详情：已用大小/文件数/分类分布 / Storage usage detail: size, count, category distribution.

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

        # 按 MIME 类型分布 / By MIME type distribution
        type_rows = await self.db.execute(
            select(
                Attachment.mime_type,
                func.count(Attachment.id).label("count"),
                func.coalesce(func.sum(Attachment.size), 0).label("size"),
            )
            .where(
                Attachment.tenant_id == self.tenant_id,
                Attachment.is_deleted.is_(False),
            )
            .group_by(Attachment.mime_type)
            .order_by(func.sum(Attachment.size).desc())
            .limit(10)
        )

        return {
            "total_files": row.total_files or 0,
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / 1024 / 1024, 2),
            "type_distribution": [
                {
                    "mime_type": r.mime_type or "unknown",
                    "count": r.count,
                    "size_bytes": int(r.size),
                }
                for r in type_rows.all()
            ],
        }

    # ── B4: 近期活动 / Recent activity ──

    async def get_recent_activities(self, limit: int = 20) -> list[dict[str, Any]]:
        """企业级近期操作日志 / Tenant recent operation logs"""
        from app.services.system import dashboard_service as dashboard_service_facade

        rows = await self.db.execute(
            select(OperationLog)
            .where(
                OperationLog.tenant_id == self.tenant_id,
                OperationLog.is_deleted.is_(False),
                dashboard_service_facade._meaningful_activity_condition(),
            )
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
                tenant_id=self.tenant_id,
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

    async def _get_storage_used(self) -> int:
        """企业存储总占用 / Tenant total storage usage"""
        result = await self.db.execute(
            select(func.coalesce(func.sum(Attachment.size), 0)).where(
                Attachment.tenant_id == self.tenant_id,
                Attachment.is_deleted.is_(False),
            )
        )
        return int(result.scalar() or 0)

    async def _count_admins(self, *extra_filters) -> int:
        """企业下管理员计数 / Tenant admin count"""
        query = (
            select(func.count())
            .select_from(TenantAdmin)
            .where(
                TenantAdmin.deleted_at.is_(None),
                TenantAdmin.tenant_id == self.tenant_id,
                *extra_filters,
            )
        )
        return (await self.db.execute(query)).scalar() or 0

    async def _count_visible_agents(self) -> int:
        """统计当前企业可见智能体数 / Count agents visible to current tenant."""
        query = (
            select(func.count())
            .select_from(Agent)
            .where(
                Agent.is_deleted.is_(False),
                _visible_agent_condition(self.tenant_id),
            )
        )
        return int((await self.db.execute(query)).scalar() or 0)

    async def _count_visible_knowledge_bases(self) -> int:
        """统计当前企业可见知识库数 / Count KBs visible to current tenant."""
        query = (
            select(func.count())
            .select_from(KnowledgeBase)
            .where(
                KnowledgeBase.is_deleted.is_(False),
                _visible_kb_condition(self.tenant_id),
            )
        )
        return int((await self.db.execute(query)).scalar() or 0)

    async def _count_visible_knowledge_documents(self) -> int:
        """统计当前企业可见知识库文档数 / Count KB documents visible to current tenant."""
        query = (
            select(func.count(KnowledgeDocument.id))
            .select_from(KnowledgeDocument)
            .join(
                KnowledgeBase,
                KnowledgeBase.id == KnowledgeDocument.knowledge_base_id,
            )
            .where(
                KnowledgeDocument.is_deleted.is_(False),
                KnowledgeBase.is_deleted.is_(False),
                _visible_kb_condition(self.tenant_id),
            )
        )
        return int((await self.db.execute(query)).scalar() or 0)

    async def _count_tenant_model(self, model, *extra_filters) -> int:
        """统计 tenant_id 隔离模型 / Count tenant-backed models with tenant_id."""
        query = (
            select(func.count())
            .select_from(model)
            .where(
                model.deleted_at.is_(None),
                model.tenant_id == self.tenant_id,
                *extra_filters,
            )
        )
        return int((await self.db.execute(query)).scalar() or 0)
