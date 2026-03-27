"""
AI monitoring read service / AI 监控读服务。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from datetime import timezone as dt_timezone
from typing import Any

from sqlalchemy import Date, case, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.configs.service import PLATFORM_TENANT_ID
from app.enums.ai import CallStatusEnum
from app.exceptions import NotFoundException
from app.models.ai import Agent, AgentConversation, AICallLog, AIModel, AIProvider
from app.models.system.admin import Admin
from app.models.tenant.tenant import Tenant
from app.models.tenant.tenant_admin import TenantAdmin
from app.models.tenant.tenant_user import TenantUser
from app.repositories.ai.agent_conversation_repository import (
    AdminAgentConversationRepository,
)
from app.schemas.ai.monitoring import (
    MonitoringActorInfo,
    MonitoringCallTraceItem,
    MonitoringConversationDetail,
    MonitoringConversationListItem,
    MonitoringUsageBreakdownItem,
    MonitoringUsageDashboard,
    MonitoringUsageSeriesPoint,
    MonitoringUsageSummary,
)
from app.schemas.common.query import QuerySpec
from app.services.ai.conversation_service import ConversationService


@dataclass(slots=True, frozen=True)
class MonitoringScope:
    scope: str
    tenant_id: int | None = None

    @property
    def is_admin(self) -> bool:
        return self.scope == "admin"

    @property
    def is_tenant(self) -> bool:
        return self.scope == "tenant"


class MonitoringService:
    PLATFORM_USAGE_TENANT_NAME = "平台管理端"

    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def admin_scope() -> MonitoringScope:
        return MonitoringScope(scope="admin")

    @staticmethod
    def tenant_scope(tenant_id: int) -> MonitoringScope:
        return MonitoringScope(scope="tenant", tenant_id=tenant_id)

    @staticmethod
    def _safe_int(value: Any) -> int:
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _safe_float(value: Any) -> float:
        try:
            return float(value or 0)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _date_filters(column, start_date: date | None, end_date: date | None) -> list:
        filters = []
        if start_date:
            filters.append(column >= start_date)
        if end_date:
            filters.append(column < end_date + timedelta(days=1))
        return filters

    @classmethod
    def _platform_usage_tenant_expr(cls):
        return case(
            (
                AICallLog.tenant_id == PLATFORM_TENANT_ID,
                PLATFORM_TENANT_ID,
            ),
            else_=None,
        )

    @classmethod
    def _effective_usage_tenant_expr(cls):
        return func.coalesce(
            AICallLog.billing_tenant_id,
            cls._platform_usage_tenant_expr(),
        )

    @classmethod
    def _effective_usage_tenant_name_expr(cls):
        return func.coalesce(
            AICallLog.billing_tenant_name_snapshot,
            Tenant.name,
            case(
                (
                    cls._effective_usage_tenant_expr() == PLATFORM_TENANT_ID,
                    cls.PLATFORM_USAGE_TENANT_NAME,
                ),
                else_=None,
            ),
        )

    @staticmethod
    def _format_dt(value: datetime | None) -> str | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=dt_timezone.utc).isoformat()
        return value.isoformat()

    def _scope_usage_filters(
        self,
        scope: MonitoringScope,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list:
        filters = [
            AICallLog.is_deleted.is_(False),
            self._effective_usage_tenant_expr().is_not(None),
        ]
        filters.extend(self._date_filters(AICallLog.created_at, start_date, end_date))
        if scope.is_tenant:
            filters.append(AICallLog.billing_tenant_id == scope.tenant_id)
        return filters

    def _scope_conversation_filters(self, scope: MonitoringScope) -> list:
        filters = [AgentConversation.is_deleted.is_(False)]
        if scope.is_tenant:
            filters.append(AgentConversation.tenant_id == scope.tenant_id)
        return filters

    async def _load_actor_map(
        self,
        refs: set[tuple[str, int]],
    ) -> dict[tuple[str, int], MonitoringActorInfo]:
        result: dict[tuple[str, int], MonitoringActorInfo] = {}
        if not refs:
            return result

        admin_ids = {uid for kind, uid in refs if kind == "platform_admin"}
        tenant_admin_ids = {uid for kind, uid in refs if kind == "tenant_admin"}
        tenant_user_ids = {uid for kind, uid in refs if kind == "tenant_user"}

        if admin_ids:
            rows = (
                await self.db.execute(
                    select(Admin.id, Admin.username, Admin.nickname, Admin.avatar).where(
                        Admin.id.in_(admin_ids),
                        Admin.is_deleted.is_(False),
                    )
                )
            ).all()
            for row in rows:
                result[("platform_admin", row.id)] = MonitoringActorInfo(
                    id=row.id,
                    type="platform_admin",
                    display_name=row.nickname or row.username,
                    username=row.username,
                    nickname=row.nickname,
                    avatar=row.avatar,
                )

        if tenant_admin_ids:
            rows = (
                await self.db.execute(
                    select(
                        TenantAdmin.id,
                        TenantAdmin.username,
                        TenantAdmin.nickname,
                        TenantAdmin.avatar,
                    ).where(
                        TenantAdmin.id.in_(tenant_admin_ids),
                        TenantAdmin.is_deleted.is_(False),
                    )
                )
            ).all()
            for row in rows:
                result[("tenant_admin", row.id)] = MonitoringActorInfo(
                    id=row.id,
                    type="tenant_admin",
                    display_name=row.nickname or row.username,
                    username=row.username,
                    nickname=row.nickname,
                    avatar=row.avatar,
                )

        if tenant_user_ids:
            rows = (
                await self.db.execute(
                    select(
                        TenantUser.id,
                        TenantUser.username,
                        TenantUser.nickname,
                        TenantUser.avatar,
                    ).where(
                        TenantUser.id.in_(tenant_user_ids),
                        TenantUser.is_deleted.is_(False),
                    )
                )
            ).all()
            for row in rows:
                result[("tenant_user", row.id)] = MonitoringActorInfo(
                    id=row.id,
                    type="tenant_user",
                    display_name=row.nickname or row.username,
                    username=row.username,
                    nickname=row.nickname,
                    avatar=row.avatar,
                )

        return result

    async def _load_conversation_usage_map(
        self,
        scope: MonitoringScope,
        conversation_ids: set[int],
    ) -> dict[int, dict[str, Any]]:
        if not conversation_ids:
            return {}

        filters = [
            AICallLog.is_deleted.is_(False),
            AICallLog.conversation_id.in_(conversation_ids),
        ]
        if scope.is_tenant:
            filters.append(AICallLog.billing_tenant_id == scope.tenant_id)

        stmt = (
            select(
                AICallLog.conversation_id,
                func.count(AICallLog.id).label("call_count"),
                func.coalesce(func.sum(AICallLog.total_tokens), 0).label("total_tokens"),
                func.coalesce(func.sum(AICallLog.cost), 0).label("total_cost"),
                func.max(AICallLog.created_at).label("last_call_at"),
            )
            .where(*filters)
            .group_by(AICallLog.conversation_id)
        )
        rows = (await self.db.execute(stmt)).all()
        return {
            row.conversation_id: {
                "call_count": self._safe_int(row.call_count),
                "total_tokens": self._safe_int(row.total_tokens),
                "total_cost": self._safe_float(row.total_cost),
                "last_call_at": row.last_call_at,
            }
            for row in rows
            if row.conversation_id is not None
        }

    async def _load_tenant_names(self, tenant_ids: set[int]) -> dict[int, str]:
        if not tenant_ids:
            return {}
        rows = (
            await self.db.execute(
                select(Tenant.id, Tenant.name).where(
                    Tenant.id.in_(tenant_ids),
                    Tenant.is_deleted.is_(False),
                )
            )
        ).all()
        return {row.id: row.name for row in rows}

    async def get_usage_dashboard(
        self,
        scope: MonitoringScope,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> MonitoringUsageDashboard:
        filters = self._scope_usage_filters(scope, start_date=start_date, end_date=end_date)
        stat_date = cast(AICallLog.created_at, Date)
        tenant_name_expr = self._effective_usage_tenant_name_expr()

        summary_stmt = select(
            func.count(AICallLog.id).label("total_calls"),
            func.coalesce(func.sum(AICallLog.total_tokens), 0).label("total_tokens"),
            func.coalesce(func.sum(AICallLog.input_tokens), 0).label("input_tokens"),
            func.coalesce(func.sum(AICallLog.output_tokens), 0).label("output_tokens"),
            func.coalesce(func.sum(AICallLog.cost), 0).label("total_cost"),
            func.sum(case((AICallLog.status == CallStatusEnum.SUCCESS.value, 1), else_=0)).label("success_calls"),
            func.sum(case((AICallLog.status == CallStatusEnum.FAILED.value, 1), else_=0)).label("failed_calls"),
        ).where(*filters)
        summary_row = (await self.db.execute(summary_stmt)).one()
        total_calls = self._safe_int(summary_row.total_calls)
        success_calls = self._safe_int(summary_row.success_calls)
        failed_calls = self._safe_int(summary_row.failed_calls)
        summary = MonitoringUsageSummary(
            total_calls=total_calls,
            total_tokens=self._safe_int(summary_row.total_tokens),
            input_tokens=self._safe_int(summary_row.input_tokens),
            output_tokens=self._safe_int(summary_row.output_tokens),
            total_cost=self._safe_float(summary_row.total_cost),
            success_calls=success_calls,
            failed_calls=failed_calls,
            success_rate=(round(success_calls / total_calls * 100, 1) if total_calls > 0 else 0.0),
        )

        daily_stmt = (
            select(
                stat_date.label("date"),
                func.count(AICallLog.id).label("call_count"),
                func.coalesce(func.sum(AICallLog.input_tokens), 0).label("input_tokens"),
                func.coalesce(func.sum(AICallLog.output_tokens), 0).label("output_tokens"),
                func.coalesce(func.sum(AICallLog.total_tokens), 0).label("total_tokens"),
                func.coalesce(func.sum(AICallLog.cost), 0).label("total_cost"),
                func.sum(case((AICallLog.status == CallStatusEnum.SUCCESS.value, 1), else_=0)).label("success_calls"),
                func.sum(case((AICallLog.status == CallStatusEnum.FAILED.value, 1), else_=0)).label("failed_calls"),
            )
            .where(*filters)
            .group_by(stat_date)
            .order_by(stat_date)
        )
        daily_rows = (await self.db.execute(daily_stmt)).all()
        daily_stats = [
            MonitoringUsageSeriesPoint(
                date=str(row.date),
                call_count=self._safe_int(row.call_count),
                input_tokens=self._safe_int(row.input_tokens),
                output_tokens=self._safe_int(row.output_tokens),
                total_tokens=self._safe_int(row.total_tokens),
                total_cost=self._safe_float(row.total_cost),
                success_calls=self._safe_int(row.success_calls),
                failed_calls=self._safe_int(row.failed_calls),
            )
            for row in daily_rows
        ]

        model_stmt = (
            select(
                AICallLog.model_id.label("key"),
                func.coalesce(AICallLog.model_name_snapshot, AIModel.name).label("label"),
                func.count(AICallLog.id).label("call_count"),
                func.coalesce(func.sum(AICallLog.total_tokens), 0).label("total_tokens"),
                func.coalesce(func.sum(AICallLog.cost), 0).label("total_cost"),
                func.sum(case((AICallLog.status == CallStatusEnum.SUCCESS.value, 1), else_=0)).label("success_calls"),
                func.sum(case((AICallLog.status == CallStatusEnum.FAILED.value, 1), else_=0)).label("failed_calls"),
            )
            .select_from(AICallLog)
            .join(AIModel, AIModel.id == AICallLog.model_id, isouter=True)
            .where(*filters)
            .group_by(AICallLog.model_id, func.coalesce(AICallLog.model_name_snapshot, AIModel.name))
            .order_by(func.coalesce(func.sum(AICallLog.total_tokens), 0).desc())
            .limit(10)
        )
        model_rows = (await self.db.execute(model_stmt)).all()
        model_stats = [
            MonitoringUsageBreakdownItem(
                key=f"{row.key or 'unknown'}:{row.label or 'unknown'}",
                label=row.label or "Unknown",
                call_count=self._safe_int(row.call_count),
                total_tokens=self._safe_int(row.total_tokens),
                total_cost=self._safe_float(row.total_cost),
                success_calls=self._safe_int(row.success_calls),
                failed_calls=self._safe_int(row.failed_calls),
            )
            for row in model_rows
        ]

        channel_stmt = (
            select(
                AICallLog.access_channel.label("key"),
                AICallLog.access_channel.label("label"),
                func.count(AICallLog.id).label("call_count"),
                func.coalesce(func.sum(AICallLog.total_tokens), 0).label("total_tokens"),
                func.coalesce(func.sum(AICallLog.cost), 0).label("total_cost"),
                func.sum(case((AICallLog.status == CallStatusEnum.SUCCESS.value, 1), else_=0)).label("success_calls"),
                func.sum(case((AICallLog.status == CallStatusEnum.FAILED.value, 1), else_=0)).label("failed_calls"),
            )
            .where(*filters)
            .group_by(AICallLog.access_channel)
            .order_by(func.coalesce(func.sum(AICallLog.total_tokens), 0).desc())
        )
        channel_rows = (await self.db.execute(channel_stmt)).all()
        access_channel_stats = [
            MonitoringUsageBreakdownItem(
                key=str(row.key or "unknown"),
                label=str(row.label or "unknown"),
                call_count=self._safe_int(row.call_count),
                total_tokens=self._safe_int(row.total_tokens),
                total_cost=self._safe_float(row.total_cost),
                success_calls=self._safe_int(row.success_calls),
                failed_calls=self._safe_int(row.failed_calls),
            )
            for row in channel_rows
        ]

        agent_stmt = (
            select(
                AICallLog.agent_id.label("key"),
                func.coalesce(AICallLog.agent_name_snapshot, Agent.name).label("label"),
                func.count(AICallLog.id).label("call_count"),
                func.coalesce(func.sum(AICallLog.total_tokens), 0).label("total_tokens"),
                func.coalesce(func.sum(AICallLog.cost), 0).label("total_cost"),
                func.sum(case((AICallLog.status == CallStatusEnum.SUCCESS.value, 1), else_=0)).label("success_calls"),
                func.sum(case((AICallLog.status == CallStatusEnum.FAILED.value, 1), else_=0)).label("failed_calls"),
            )
            .select_from(AICallLog)
            .join(Agent, Agent.id == AICallLog.agent_id, isouter=True)
            .where(*filters, AICallLog.agent_id.is_not(None))
            .group_by(AICallLog.agent_id, func.coalesce(AICallLog.agent_name_snapshot, Agent.name))
            .order_by(func.coalesce(func.sum(AICallLog.total_tokens), 0).desc())
            .limit(10)
        )
        agent_rows = (await self.db.execute(agent_stmt)).all()
        top_agents = [
            MonitoringUsageBreakdownItem(
                key=f"{row.key}:{row.label or row.key}",
                label=row.label or f"Agent #{row.key}",
                call_count=self._safe_int(row.call_count),
                total_tokens=self._safe_int(row.total_tokens),
                total_cost=self._safe_float(row.total_cost),
                success_calls=self._safe_int(row.success_calls),
                failed_calls=self._safe_int(row.failed_calls),
            )
            for row in agent_rows
        ]

        actor_stmt = (
            select(
                AICallLog.actor_user_type.label("actor_type"),
                AICallLog.actor_user_id.label("actor_id"),
                func.count(AICallLog.id).label("call_count"),
                func.coalesce(func.sum(AICallLog.total_tokens), 0).label("total_tokens"),
                func.coalesce(func.sum(AICallLog.cost), 0).label("total_cost"),
                func.sum(case((AICallLog.status == CallStatusEnum.SUCCESS.value, 1), else_=0)).label("success_calls"),
                func.sum(case((AICallLog.status == CallStatusEnum.FAILED.value, 1), else_=0)).label("failed_calls"),
            )
            .where(*filters, AICallLog.actor_user_id.is_not(None))
            .group_by(AICallLog.actor_user_type, AICallLog.actor_user_id)
            .order_by(func.coalesce(func.sum(AICallLog.total_tokens), 0).desc())
            .limit(10)
        )
        actor_rows = (await self.db.execute(actor_stmt)).all()
        actor_map = await self._load_actor_map({
            (str(row.actor_type or ""), int(row.actor_id))
            for row in actor_rows
            if row.actor_type and row.actor_id
        })
        top_users = [
            MonitoringUsageBreakdownItem(
                key=f"{row.actor_type}:{row.actor_id}",
                label=(
                    actor_map.get((str(row.actor_type), int(row.actor_id))).display_name
                    if actor_map.get((str(row.actor_type), int(row.actor_id)))
                    else f"{row.actor_type}:{row.actor_id}"
                ),
                call_count=self._safe_int(row.call_count),
                total_tokens=self._safe_int(row.total_tokens),
                total_cost=self._safe_float(row.total_cost),
                success_calls=self._safe_int(row.success_calls),
                failed_calls=self._safe_int(row.failed_calls),
            )
            for row in actor_rows
        ]

        top_tenants: list[MonitoringUsageBreakdownItem] = []
        if scope.is_admin:
            tenant_base = (
                select(
                    self._effective_usage_tenant_expr().label("tenant_id"),
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
                    func.coalesce(func.sum(tenant_base.c.total_tokens), 0).label("total_tokens"),
                    func.coalesce(func.sum(tenant_base.c.cost), 0).label("total_cost"),
                    func.sum(case((tenant_base.c.status == CallStatusEnum.SUCCESS.value, 1), else_=0)).label("success_calls"),
                    func.sum(case((tenant_base.c.status == CallStatusEnum.FAILED.value, 1), else_=0)).label("failed_calls"),
                )
                .group_by(tenant_base.c.tenant_id, tenant_base.c.tenant_name)
                .order_by(func.coalesce(func.sum(tenant_base.c.total_tokens), 0).desc())
                .limit(10)
            )
            tenant_rows = (await self.db.execute(tenant_stmt)).all()
            top_tenants = [
                MonitoringUsageBreakdownItem(
                    key=str(row.key),
                    label=row.label or ("平台管理端" if row.key == PLATFORM_TENANT_ID else "-"),
                    call_count=self._safe_int(row.call_count),
                    total_tokens=self._safe_int(row.total_tokens),
                    total_cost=self._safe_float(row.total_cost),
                    success_calls=self._safe_int(row.success_calls),
                    failed_calls=self._safe_int(row.failed_calls),
                )
                for row in tenant_rows
            ]

        tenant_name = None
        if scope.is_tenant and scope.tenant_id is not None:
            tenant_name = (await self._load_tenant_names({scope.tenant_id})).get(scope.tenant_id)

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

    async def list_conversations(
        self,
        scope: MonitoringScope,
        spec: QuerySpec,
    ) -> tuple[list[MonitoringConversationListItem], int]:
        if scope.is_tenant:
            service = ConversationService(self.db, int(scope.tenant_id))
            items, total = await service.query_list(spec=spec)
        else:
            repo = AdminAgentConversationRepository(self.db)
            items, total = await repo.query_list(spec)

        conversation_ids = {item.id for item in items}
        tenant_ids = {item.tenant_id for item in items if item.tenant_id is not None}
        usage_map = await self._load_conversation_usage_map(scope, conversation_ids)
        tenant_names = await self._load_tenant_names(tenant_ids)
        actor_map = await self._load_actor_map({
            (str(item.owner_type or ""), int(item.user_id))
            for item in items
            if item.user_id is not None and item.owner_type in {"platform_admin", "tenant_admin", "tenant_user"}
        })

        result: list[MonitoringConversationListItem] = []
        for item in items:
            usage = usage_map.get(item.id, {})
            actor = None
            if item.user_id is not None and item.owner_type:
                actor = actor_map.get((str(item.owner_type), int(item.user_id)))
            result.append(
                MonitoringConversationListItem(
                    id=item.id,
                    tenant_id=item.tenant_id,
                    tenant_name=(
                        self.PLATFORM_USAGE_TENANT_NAME
                        if item.tenant_id == PLATFORM_TENANT_ID
                        else tenant_names.get(item.tenant_id)
                    ),
                    agent_id=item.agent_id,
                    agent_name=getattr(getattr(item, "agent", None), "name", None),
                    agent_avatar=getattr(getattr(item, "agent", None), "avatar", None),
                    owner_type=item.owner_type,
                    actor=actor,
                    title=item.title,
                    status=item.status,
                    message_count=self._safe_int(item.message_count),
                    call_count=self._safe_int(usage.get("call_count")),
                    total_tokens=max(self._safe_int(item.token_count), self._safe_int(usage.get("total_tokens"))),
                    total_cost=max(self._safe_float(item.cost), self._safe_float(usage.get("total_cost"))),
                    last_call_at=usage.get("last_call_at"),
                    created_at=item.created_at,
                    updated_at=item.updated_at,
                )
            )
        return result, total

    async def get_conversation_detail(
        self,
        scope: MonitoringScope,
        conversation_id: int,
        *,
        message_skip: int = 0,
        message_limit: int = 50,
    ) -> MonitoringConversationDetail:
        if scope.is_tenant:
            service = ConversationService(self.db, int(scope.tenant_id))
            conversation = await service.get_by_id(conversation_id)
            if not conversation:
                raise NotFoundException(message="conversation not found")
        else:
            service, conversation = await ConversationService.get_service_for_conversation(
                self.db, conversation_id,
            )

        detail = await service.get_conversation_detail(
            conversation_id=conversation_id,
            message_skip=message_skip,
            message_limit=message_limit,
        )
        usage = (await self._load_conversation_usage_map(scope, {conversation_id})).get(conversation_id, {})
        actor = None
        if conversation.user_id is not None and conversation.owner_type:
            actor = (
                await self._load_actor_map({
                    (str(conversation.owner_type), int(conversation.user_id)),
                })
            ).get((str(conversation.owner_type), int(conversation.user_id)))

        trace_filters = [
            AICallLog.is_deleted.is_(False),
            AICallLog.conversation_id == conversation_id,
        ]
        if scope.is_tenant:
            trace_filters.append(AICallLog.billing_tenant_id == scope.tenant_id)
        trace_stmt = (
            select(
                AICallLog.id,
                AICallLog.created_at,
                AICallLog.status,
                AICallLog.request_type,
                func.coalesce(AICallLog.model_name_snapshot, AIModel.name).label("model_name"),
                func.coalesce(AICallLog.provider_name_snapshot, AIProvider.name).label("provider_name"),
                AICallLog.total_tokens,
                AICallLog.cost,
                AICallLog.latency_ms,
                AICallLog.error_message,
                AICallLog.request_metadata,
            )
            .select_from(AICallLog)
            .join(AIModel, AIModel.id == AICallLog.model_id, isouter=True)
            .join(AIProvider, AIProvider.id == AICallLog.provider_id, isouter=True)
            .where(*trace_filters)
            .order_by(AICallLog.created_at.desc())
            .limit(200)
        )
        trace_rows = (await self.db.execute(trace_stmt)).all()
        call_trace = [
            MonitoringCallTraceItem(
                id=row.id,
                created_at=row.created_at,
                status=row.status,
                request_type=row.request_type,
                model_name=row.model_name,
                provider_name=row.provider_name,
                total_tokens=self._safe_int(row.total_tokens),
                cost=self._safe_float(row.cost),
                latency_ms=row.latency_ms,
                usage_mode=((row.request_metadata or {}).get("response") or {}).get("usage_mode")
                if isinstance(row.request_metadata, dict)
                else None,
                error_message=row.error_message,
            )
            for row in trace_rows
        ]

        return MonitoringConversationDetail(
            id=conversation.id,
            tenant_id=conversation.tenant_id,
            tenant_name=(
                self.PLATFORM_USAGE_TENANT_NAME
                if conversation.tenant_id == PLATFORM_TENANT_ID
                else (await self._load_tenant_names({conversation.tenant_id})).get(conversation.tenant_id)
            ),
            agent_id=conversation.agent_id,
            agent_name=detail.get("agent_name"),
            agent_avatar=detail.get("agent_avatar"),
            owner_type=conversation.owner_type,
            actor=actor,
            title=conversation.title,
            status=conversation.status,
            message_count=self._safe_int(detail.get("message_count")),
            total_tokens=max(self._safe_int(detail.get("token_count")), self._safe_int(usage.get("total_tokens"))),
            total_cost=max(self._safe_float(detail.get("cost")), self._safe_float(usage.get("total_cost"))),
            call_count=self._safe_int(usage.get("call_count")),
            last_call_at=usage.get("last_call_at"),
            created_at=conversation.created_at,
            updated_at=conversation.updated_at,
            metadata=detail.get("metadata"),
            message_list=detail.get("message_list") or [],
            call_trace=call_trace,
        )


__all__ = ["MonitoringScope", "MonitoringService"]
