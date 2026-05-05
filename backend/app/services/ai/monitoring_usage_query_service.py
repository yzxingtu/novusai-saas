"""
Monitoring usage dashboard query service.
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Date, case, cast, func, select

from app.configs.service import PLATFORM_TENANT_ID
from app.enums.ai import CallStatusEnum
from app.models.ai import Agent, AICallLog, AIModel
from app.models.tenant.tenant import Tenant
from app.schemas.ai.monitoring import (
    MonitoringUsageBreakdownItem,
    MonitoringUsageDashboard,
    MonitoringUsageSeriesPoint,
    MonitoringUsageSummary,
)

if TYPE_CHECKING:
    from app.services.ai.monitoring_service import MonitoringScope, MonitoringService


class MonitoringUsageQueryService:
    def __init__(self, service: MonitoringService) -> None:
        self.service = service

    async def get_usage_dashboard(
        self,
        scope: MonitoringScope,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> MonitoringUsageDashboard:
        base = self.service
        filters = base._scope_usage_filters(
            scope,
            start_date=start_date,
            end_date=end_date,
        )
        stat_date = cast(AICallLog.created_at, Date)
        tenant_name_expr = base._effective_usage_tenant_name_expr()

        summary_stmt = select(
            func.count(AICallLog.id).label("total_calls"),
            func.coalesce(func.sum(AICallLog.total_tokens), 0).label("total_tokens"),
            func.coalesce(func.sum(AICallLog.input_tokens), 0).label("input_tokens"),
            func.coalesce(func.sum(AICallLog.output_tokens), 0).label("output_tokens"),
            func.coalesce(func.sum(AICallLog.cost), 0).label("total_cost"),
            func.sum(
                case((AICallLog.status == CallStatusEnum.SUCCESS.value, 1), else_=0)
            ).label("success_calls"),
            func.sum(
                case((AICallLog.status == CallStatusEnum.FAILED.value, 1), else_=0)
            ).label("failed_calls"),
        ).where(*filters)
        summary_row = (await base.db.execute(summary_stmt)).one()
        total_calls = base._safe_int(summary_row.total_calls)
        success_calls = base._safe_int(summary_row.success_calls)
        failed_calls = base._safe_int(summary_row.failed_calls)
        summary = MonitoringUsageSummary(
            total_calls=total_calls,
            total_tokens=base._safe_int(summary_row.total_tokens),
            input_tokens=base._safe_int(summary_row.input_tokens),
            output_tokens=base._safe_int(summary_row.output_tokens),
            total_cost=base._safe_float(summary_row.total_cost),
            success_calls=success_calls,
            failed_calls=failed_calls,
            success_rate=(
                round(success_calls / total_calls * 100, 1) if total_calls > 0 else 0.0
            ),
        )

        daily_stmt = (
            select(
                stat_date.label("date"),
                func.count(AICallLog.id).label("call_count"),
                func.coalesce(func.sum(AICallLog.input_tokens), 0).label(
                    "input_tokens"
                ),
                func.coalesce(func.sum(AICallLog.output_tokens), 0).label(
                    "output_tokens"
                ),
                func.coalesce(func.sum(AICallLog.total_tokens), 0).label(
                    "total_tokens"
                ),
                func.coalesce(func.sum(AICallLog.cost), 0).label("total_cost"),
                func.sum(
                    case((AICallLog.status == CallStatusEnum.SUCCESS.value, 1), else_=0)
                ).label("success_calls"),
                func.sum(
                    case((AICallLog.status == CallStatusEnum.FAILED.value, 1), else_=0)
                ).label("failed_calls"),
            )
            .where(*filters)
            .group_by(stat_date)
            .order_by(stat_date)
        )
        daily_rows = (await base.db.execute(daily_stmt)).all()
        daily_stats = [
            MonitoringUsageSeriesPoint(
                date=str(row.date),
                call_count=base._safe_int(row.call_count),
                input_tokens=base._safe_int(row.input_tokens),
                output_tokens=base._safe_int(row.output_tokens),
                total_tokens=base._safe_int(row.total_tokens),
                total_cost=base._safe_float(row.total_cost),
                success_calls=base._safe_int(row.success_calls),
                failed_calls=base._safe_int(row.failed_calls),
            )
            for row in daily_rows
        ]

        model_stmt = (
            select(
                AICallLog.model_id.label("key"),
                func.coalesce(AICallLog.model_name_snapshot, AIModel.name).label(
                    "label"
                ),
                func.count(AICallLog.id).label("call_count"),
                func.coalesce(func.sum(AICallLog.total_tokens), 0).label(
                    "total_tokens"
                ),
                func.coalesce(func.sum(AICallLog.cost), 0).label("total_cost"),
                func.sum(
                    case((AICallLog.status == CallStatusEnum.SUCCESS.value, 1), else_=0)
                ).label("success_calls"),
                func.sum(
                    case((AICallLog.status == CallStatusEnum.FAILED.value, 1), else_=0)
                ).label("failed_calls"),
            )
            .select_from(AICallLog)
            .join(AIModel, AIModel.id == AICallLog.model_id, isouter=True)
            .where(*filters)
            .group_by(
                AICallLog.model_id,
                func.coalesce(AICallLog.model_name_snapshot, AIModel.name),
            )
            .order_by(func.coalesce(func.sum(AICallLog.total_tokens), 0).desc())
            .limit(10)
        )
        model_rows = (await base.db.execute(model_stmt)).all()
        model_stats = [
            MonitoringUsageBreakdownItem(
                key=f"{row.key or 'unknown'}:{row.label or 'unknown'}",
                label=row.label or "Unknown",
                call_count=base._safe_int(row.call_count),
                total_tokens=base._safe_int(row.total_tokens),
                total_cost=base._safe_float(row.total_cost),
                success_calls=base._safe_int(row.success_calls),
                failed_calls=base._safe_int(row.failed_calls),
            )
            for row in model_rows
        ]

        channel_stmt = (
            select(
                AICallLog.access_channel.label("key"),
                AICallLog.access_channel.label("label"),
                func.count(AICallLog.id).label("call_count"),
                func.coalesce(func.sum(AICallLog.total_tokens), 0).label(
                    "total_tokens"
                ),
                func.coalesce(func.sum(AICallLog.cost), 0).label("total_cost"),
                func.sum(
                    case((AICallLog.status == CallStatusEnum.SUCCESS.value, 1), else_=0)
                ).label("success_calls"),
                func.sum(
                    case((AICallLog.status == CallStatusEnum.FAILED.value, 1), else_=0)
                ).label("failed_calls"),
            )
            .where(*filters)
            .group_by(AICallLog.access_channel)
            .order_by(func.coalesce(func.sum(AICallLog.total_tokens), 0).desc())
        )
        channel_rows = (await base.db.execute(channel_stmt)).all()
        access_channel_stats = [
            MonitoringUsageBreakdownItem(
                key=str(row.key or "unknown"),
                label=str(row.label or "unknown"),
                call_count=base._safe_int(row.call_count),
                total_tokens=base._safe_int(row.total_tokens),
                total_cost=base._safe_float(row.total_cost),
                success_calls=base._safe_int(row.success_calls),
                failed_calls=base._safe_int(row.failed_calls),
            )
            for row in channel_rows
        ]

        agent_stmt = (
            select(
                AICallLog.agent_id.label("key"),
                func.coalesce(AICallLog.agent_name_snapshot, Agent.name).label("label"),
                func.count(AICallLog.id).label("call_count"),
                func.coalesce(func.sum(AICallLog.total_tokens), 0).label(
                    "total_tokens"
                ),
                func.coalesce(func.sum(AICallLog.cost), 0).label("total_cost"),
                func.sum(
                    case((AICallLog.status == CallStatusEnum.SUCCESS.value, 1), else_=0)
                ).label("success_calls"),
                func.sum(
                    case((AICallLog.status == CallStatusEnum.FAILED.value, 1), else_=0)
                ).label("failed_calls"),
            )
            .select_from(AICallLog)
            .join(Agent, Agent.id == AICallLog.agent_id, isouter=True)
            .where(*filters, AICallLog.agent_id.is_not(None))
            .group_by(
                AICallLog.agent_id,
                func.coalesce(AICallLog.agent_name_snapshot, Agent.name),
            )
            .order_by(func.coalesce(func.sum(AICallLog.total_tokens), 0).desc())
            .limit(10)
        )
        agent_rows = (await base.db.execute(agent_stmt)).all()
        top_agents = [
            MonitoringUsageBreakdownItem(
                key=f"{row.key}:{row.label or row.key}",
                label=row.label or f"Agent #{row.key}",
                call_count=base._safe_int(row.call_count),
                total_tokens=base._safe_int(row.total_tokens),
                total_cost=base._safe_float(row.total_cost),
                success_calls=base._safe_int(row.success_calls),
                failed_calls=base._safe_int(row.failed_calls),
            )
            for row in agent_rows
        ]

        actor_stmt = (
            select(
                AICallLog.actor_user_type.label("actor_type"),
                AICallLog.actor_user_id.label("actor_id"),
                func.count(AICallLog.id).label("call_count"),
                func.coalesce(func.sum(AICallLog.total_tokens), 0).label(
                    "total_tokens"
                ),
                func.coalesce(func.sum(AICallLog.cost), 0).label("total_cost"),
                func.sum(
                    case((AICallLog.status == CallStatusEnum.SUCCESS.value, 1), else_=0)
                ).label("success_calls"),
                func.sum(
                    case((AICallLog.status == CallStatusEnum.FAILED.value, 1), else_=0)
                ).label("failed_calls"),
            )
            .where(*filters, AICallLog.actor_user_id.is_not(None))
            .group_by(AICallLog.actor_user_type, AICallLog.actor_user_id)
            .order_by(func.coalesce(func.sum(AICallLog.total_tokens), 0).desc())
            .limit(10)
        )
        actor_rows = (await base.db.execute(actor_stmt)).all()
        actor_refs = {
            (str(row.actor_type), int(row.actor_id))
            for row in actor_rows
            if row.actor_type and row.actor_id
        }
        actor_map = await base._load_actor_map(actor_refs)
        actor_snapshot_map = await base._load_actor_snapshot_map(
            scope,
            actor_refs,
            start_date=start_date,
            end_date=end_date,
        )
        top_users = [
            MonitoringUsageBreakdownItem(
                key=f"{row.actor_type}:{row.actor_id}",
                label=(
                    actor.display_name
                    if (
                        actor := base._build_actor_info_from_snapshot(
                            actor_snapshot_map.get(
                                (str(row.actor_type), int(row.actor_id))
                            ),
                            actor_id=int(row.actor_id),
                            actor_type=str(row.actor_type),
                            live_actor=actor_map.get(
                                (str(row.actor_type), int(row.actor_id))
                            ),
                        )
                    )
                    and actor.display_name
                    else f"{row.actor_type}:{row.actor_id}"
                ),
                actor=actor,
                call_count=base._safe_int(row.call_count),
                total_tokens=base._safe_int(row.total_tokens),
                total_cost=base._safe_float(row.total_cost),
                success_calls=base._safe_int(row.success_calls),
                failed_calls=base._safe_int(row.failed_calls),
            )
            for row in actor_rows
        ]

        top_tenants: list[MonitoringUsageBreakdownItem] = []
        if scope.is_admin:
            tenant_base = (
                select(
                    base._effective_usage_tenant_expr().label("tenant_id"),
                    tenant_name_expr.label("tenant_name"),
                    AICallLog.total_tokens.label("total_tokens"),
                    AICallLog.cost.label("cost"),
                    AICallLog.status.label("status"),
                )
                .select_from(AICallLog)
                .join(Tenant, Tenant.id == AICallLog.billing_tenant_id, isouter=True)
                .where(*filters)
            ).subquery("tenant_usage_base")
            tenant_stmt = (
                select(
                    tenant_base.c.tenant_id.label("key"),
                    tenant_base.c.tenant_name.label("label"),
                    func.count().label("call_count"),
                    func.coalesce(func.sum(tenant_base.c.total_tokens), 0).label(
                        "total_tokens"
                    ),
                    func.coalesce(func.sum(tenant_base.c.cost), 0).label("total_cost"),
                    func.sum(
                        case(
                            (tenant_base.c.status == CallStatusEnum.SUCCESS.value, 1),
                            else_=0,
                        )
                    ).label("success_calls"),
                    func.sum(
                        case(
                            (tenant_base.c.status == CallStatusEnum.FAILED.value, 1),
                            else_=0,
                        )
                    ).label("failed_calls"),
                )
                .group_by(tenant_base.c.tenant_id, tenant_base.c.tenant_name)
                .order_by(func.coalesce(func.sum(tenant_base.c.total_tokens), 0).desc())
                .limit(10)
            )
            tenant_rows = (await base.db.execute(tenant_stmt)).all()
            top_tenants = [
                MonitoringUsageBreakdownItem(
                    key=str(row.key),
                    label=row.label
                    or ("平台管理端" if row.key == PLATFORM_TENANT_ID else "-"),
                    call_count=base._safe_int(row.call_count),
                    total_tokens=base._safe_int(row.total_tokens),
                    total_cost=base._safe_float(row.total_cost),
                    success_calls=base._safe_int(row.success_calls),
                    failed_calls=base._safe_int(row.failed_calls),
                )
                for row in tenant_rows
            ]

        tenant_name = None
        if scope.is_tenant and scope.tenant_id is not None:
            tenant_name = (await base._load_tenant_names({scope.tenant_id})).get(
                scope.tenant_id
            )

        return MonitoringUsageDashboard(
            scope=scope.scope,
            tenant_id=scope.tenant_id,
            tenant_name=tenant_name,
            summary=summary,
            daily_stats=daily_stats,
            model_stats=model_stats,
            access_channel_stats=access_channel_stats,
            top_agents=top_agents,
            top_users=top_users,
            top_tenants=top_tenants,
        )
