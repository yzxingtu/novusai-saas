"""
AI monitoring read service / AI 监控读服务。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from datetime import timezone as dt_timezone
from typing import Any

from sqlalchemy import case, func, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from app.configs.service import PLATFORM_TENANT_ID
from app.core.identity import resolve_identity_display_role_name
from app.models.ai import AgentConversation, AICallLog
from app.models.system.admin import Admin
from app.models.tenant.tenant import Tenant
from app.models.tenant.tenant_admin import TenantAdmin
from app.models.tenant.tenant_user import TenantUser
from app.repositories.ai.agent_conversation_repository import (
    AdminAgentConversationRepository,
    AgentConversationRepository,
)
from app.schemas.ai.monitoring import (
    MonitoringActorInfo,
    MonitoringConversationDetail,
    MonitoringConversationListItem,
    MonitoringUsageDashboard,
)
from app.schemas.common.query import FilterOp, QuerySpec
from app.services.ai.conversation_service import ConversationService
from app.services.ai.monitoring_conversation_query_service import (
    MonitoringConversationQueryService,
)
from app.services.ai.monitoring_read_model_projector import (
    MonitoringReadModelProjector,
)
from app.services.ai.monitoring_usage_query_service import MonitoringUsageQueryService


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
    ConversationService = ConversationService
    AdminAgentConversationRepository = AdminAgentConversationRepository
    AgentConversationRepository = AgentConversationRepository

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
    def _normalize_optional_bool(value: Any) -> bool | None:
        return MonitoringReadModelProjector.normalize_optional_bool(value)

    @staticmethod
    def _normalize_fallback_history(value: Any) -> list[dict[str, Any]]:
        return MonitoringReadModelProjector.normalize_fallback_history(value)

    @classmethod
    def _extract_call_trace_diagnostics(cls, request_metadata: Any) -> dict[str, Any]:
        return MonitoringReadModelProjector.extract_call_trace_diagnostics(
            request_metadata
        )

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

    @staticmethod
    def _extract_caller_snapshot(request_metadata: Any) -> dict[str, Any]:
        return MonitoringReadModelProjector.extract_caller_snapshot(request_metadata)

    @classmethod
    def _resolve_snapshot_display_role_name(
        cls,
        snapshot: dict[str, Any] | None,
        live_actor: MonitoringActorInfo | None = None,
    ) -> str | None:
        return MonitoringReadModelProjector.resolve_snapshot_display_role_name(
            snapshot,
            live_actor,
        )

    @classmethod
    def _build_actor_info_from_snapshot(
        cls,
        snapshot: dict[str, Any] | None,
        *,
        actor_id: int | None = None,
        actor_type: str | None = None,
        tenant_id: int | None = None,
        tenant_name: str | None = None,
        live_actor: MonitoringActorInfo | None = None,
    ) -> MonitoringActorInfo | None:
        return MonitoringReadModelProjector.build_actor_info_from_snapshot(
            snapshot,
            platform_usage_tenant_name=cls.PLATFORM_USAGE_TENANT_NAME,
            actor_id=actor_id,
            actor_type=actor_type,
            tenant_id=tenant_id,
            tenant_name=tenant_name,
            live_actor=live_actor,
        )

    async def _load_actor_snapshot_map(
        self,
        scope: MonitoringScope,
        refs: set[tuple[str, int]],
        *,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> dict[tuple[str, int], dict[str, Any]]:
        actor_refs = sorted(
            {
                (str(actor_type), int(actor_id))
                for actor_type, actor_id in refs
                if actor_type and actor_id
            }
        )
        if not actor_refs:
            return {}

        filters = [
            AICallLog.is_deleted.is_(False),
            AICallLog.actor_user_id.is_not(None),
            tuple_(AICallLog.actor_user_type, AICallLog.actor_user_id).in_(actor_refs),
        ]
        filters.extend(self._date_filters(AICallLog.created_at, start_date, end_date))
        if scope.is_tenant:
            filters.append(AICallLog.billing_tenant_id == scope.tenant_id)

        ranked = (
            select(
                AICallLog.actor_user_type.label("actor_type"),
                AICallLog.actor_user_id.label("actor_id"),
                AICallLog.request_metadata.label("request_metadata"),
                func.row_number()
                .over(
                    partition_by=(
                        AICallLog.actor_user_type,
                        AICallLog.actor_user_id,
                    ),
                    order_by=AICallLog.created_at.desc(),
                )
                .label("rn"),
            )
            .where(*filters)
            .subquery("monitoring_actor_snapshot_ranked")
        )

        rows = (
            await self.db.execute(
                select(
                    ranked.c.actor_type,
                    ranked.c.actor_id,
                    ranked.c.request_metadata,
                ).where(ranked.c.rn == 1)
            )
        ).all()

        return {
            (str(row.actor_type), int(row.actor_id)): snapshot
            for row in rows
            if (snapshot := self._extract_caller_snapshot(row.request_metadata))
        }

    async def _load_conversation_actor_snapshot_map(
        self,
        scope: MonitoringScope,
        conversation_ids: set[int],
    ) -> dict[int, dict[str, Any]]:
        normalized_ids = sorted({int(conversation_id) for conversation_id in conversation_ids if conversation_id})
        if not normalized_ids:
            return {}

        filters = [
            AICallLog.is_deleted.is_(False),
            AICallLog.conversation_id.in_(normalized_ids),
        ]
        if scope.is_tenant:
            filters.append(AICallLog.billing_tenant_id == scope.tenant_id)

        ranked = (
            select(
                AICallLog.conversation_id.label("conversation_id"),
                AICallLog.actor_user_type.label("actor_type"),
                AICallLog.actor_user_id.label("actor_id"),
                AICallLog.request_metadata.label("request_metadata"),
                func.row_number()
                .over(
                    partition_by=AICallLog.conversation_id,
                    order_by=AICallLog.created_at.desc(),
                )
                .label("rn"),
            )
            .where(*filters)
            .subquery("monitoring_conversation_actor_ranked")
        )

        rows = (
            await self.db.execute(
                select(
                    ranked.c.conversation_id,
                    ranked.c.actor_type,
                    ranked.c.actor_id,
                    ranked.c.request_metadata,
                ).where(ranked.c.rn == 1)
            )
        ).all()

        return {
            int(row.conversation_id): {
                "snapshot": self._extract_caller_snapshot(row.request_metadata),
                "actor_type": str(row.actor_type) if row.actor_type else None,
                "actor_id": int(row.actor_id) if row.actor_id else None,
            }
            for row in rows
            if row.conversation_id is not None
        }

    async def _load_actor_map(
        self,
        refs: set[tuple[str, int]],
    ) -> dict[tuple[str, int], MonitoringActorInfo]:
        from app.models.auth.admin_role import AdminRole
        from app.models.auth.tenant_admin_role import TenantAdminRole
        from app.models.auth.tenant_user_role import TenantUserRole
        from app.models.org.admin_org_node import AdminOrgNode
        from app.models.org.tenant_org_node import TenantOrgNode

        result: dict[tuple[str, int], MonitoringActorInfo] = {}
        if not refs:
            return result

        admin_ids = {uid for kind, uid in refs if kind == "platform_admin"}
        tenant_admin_ids = {uid for kind, uid in refs if kind == "tenant_admin"}
        tenant_user_ids = {uid for kind, uid in refs if kind == "tenant_user"}

        if admin_ids:
            rows = (
                await self.db.execute(
                    select(
                        Admin.id,
                        Admin.username,
                        Admin.nickname,
                        Admin.avatar,
                        Admin.org_node_id,
                        Admin.is_active,
                        Admin.is_super,
                        AdminRole.name.label("role_name"),
                        AdminOrgNode.name.label("org_node_name"),
                        AdminOrgNode.leader_id.label("org_leader_id"),
                    )
                    .select_from(Admin)
                    .join(AdminRole, AdminRole.id == Admin.role_id, isouter=True)
                    .join(
                        AdminOrgNode, AdminOrgNode.id == Admin.org_node_id, isouter=True
                    )
                    .where(
                        Admin.id.in_(admin_ids),
                        Admin.is_deleted.is_(False),
                    )
                )
            ).all()
            for row in rows:
                result[("platform_admin", row.id)] = MonitoringActorInfo(
                    id=row.id,
                    type="platform_admin",
                    tenant_id=PLATFORM_TENANT_ID,
                    tenant_name=self.PLATFORM_USAGE_TENANT_NAME,
                    display_name=row.nickname or row.username,
                    username=row.username,
                    nickname=row.nickname,
                    avatar=row.avatar,
                    org_node_id=row.org_node_id,
                    org_node_name=row.org_node_name,
                    role_name=row.role_name,
                    display_role_name=resolve_identity_display_role_name(
                        row.role_name,
                        row.org_node_name,
                    ),
                    is_active=row.is_active,
                    is_owner=bool(row.is_super),
                    is_leader=bool(
                        row.org_leader_id is not None and row.org_leader_id == row.id
                    ),
                )

        if tenant_admin_ids:
            rows = (
                await self.db.execute(
                    select(
                        TenantAdmin.id,
                        TenantAdmin.tenant_id,
                        TenantAdmin.username,
                        TenantAdmin.nickname,
                        TenantAdmin.avatar,
                        TenantAdmin.org_node_id,
                        TenantAdmin.is_active,
                        TenantAdmin.is_owner,
                        Tenant.name.label("tenant_name"),
                        TenantAdminRole.name.label("role_name"),
                        TenantOrgNode.name.label("org_node_name"),
                        TenantOrgNode.leader_id.label("org_leader_id"),
                    )
                    .select_from(TenantAdmin)
                    .join(
                        TenantAdminRole,
                        TenantAdminRole.id == TenantAdmin.role_id,
                        isouter=True,
                    )
                    .join(
                        TenantOrgNode,
                        TenantOrgNode.id == TenantAdmin.org_node_id,
                        isouter=True,
                    )
                    .join(Tenant, Tenant.id == TenantAdmin.tenant_id, isouter=True)
                    .where(
                        TenantAdmin.id.in_(tenant_admin_ids),
                        TenantAdmin.is_deleted.is_(False),
                    )
                )
            ).all()
            for row in rows:
                result[("tenant_admin", row.id)] = MonitoringActorInfo(
                    id=row.id,
                    type="tenant_admin",
                    tenant_id=row.tenant_id,
                    tenant_name=row.tenant_name,
                    display_name=row.nickname or row.username,
                    username=row.username,
                    nickname=row.nickname,
                    avatar=row.avatar,
                    org_node_id=row.org_node_id,
                    org_node_name=row.org_node_name,
                    role_name=row.role_name,
                    display_role_name=resolve_identity_display_role_name(
                        row.role_name,
                        row.org_node_name,
                    ),
                    is_active=row.is_active,
                    is_owner=bool(row.is_owner),
                    is_leader=bool(
                        row.org_leader_id is not None and row.org_leader_id == row.id
                    ),
                )

        if tenant_user_ids:
            rows = (
                await self.db.execute(
                    select(
                        TenantUser.id,
                        TenantUser.tenant_id,
                        TenantUser.username,
                        TenantUser.nickname,
                        TenantUser.avatar,
                        TenantUser.org_node_id,
                        TenantUser.is_active,
                        Tenant.name.label("tenant_name"),
                        TenantUserRole.name.label("role_name"),
                        TenantOrgNode.name.label("org_node_name"),
                    )
                    .select_from(TenantUser)
                    .join(
                        TenantUserRole,
                        TenantUserRole.id == TenantUser.role_id,
                        isouter=True,
                    )
                    .join(
                        TenantOrgNode,
                        TenantOrgNode.id == TenantUser.org_node_id,
                        isouter=True,
                    )
                    .join(Tenant, Tenant.id == TenantUser.tenant_id, isouter=True)
                    .where(
                        TenantUser.id.in_(tenant_user_ids),
                        TenantUser.is_deleted.is_(False),
                    )
                )
            ).all()
            for row in rows:
                result[("tenant_user", row.id)] = MonitoringActorInfo(
                    id=row.id,
                    type="tenant_user",
                    tenant_id=row.tenant_id,
                    tenant_name=row.tenant_name,
                    display_name=row.nickname or row.username,
                    username=row.username,
                    nickname=row.nickname,
                    avatar=row.avatar,
                    org_node_id=row.org_node_id,
                    org_node_name=row.org_node_name,
                    role_name=row.role_name,
                    display_role_name=resolve_identity_display_role_name(
                        row.role_name,
                        row.org_node_name,
                    ),
                    is_active=row.is_active,
                    is_owner=False,
                    is_leader=False,
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
                func.coalesce(func.sum(AICallLog.total_tokens), 0).label(
                    "total_tokens"
                ),
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

    @staticmethod
    def _extract_runtime_filter_value(raw: Any) -> int | None:
        value = MonitoringService._safe_int(raw)
        return value if value > 0 else None

    @classmethod
    def _split_conversation_runtime_filters(
        cls,
        spec: QuerySpec,
    ) -> tuple[int | None, int | None, QuerySpec]:
        provider_id: int | None = None
        model_id: int | None = None
        remaining_filters = []

        for rule in spec.filters:
            if rule.op == FilterOp.eq and rule.field == "provider_id":
                provider_id = cls._extract_runtime_filter_value(rule.value)
                continue
            if rule.op == FilterOp.eq and rule.field == "model_id":
                model_id = cls._extract_runtime_filter_value(rule.value)
                continue
            remaining_filters.append(rule)

        return (
            provider_id,
            model_id,
            QuerySpec(
                filters=remaining_filters,
                sort=list(spec.sort),
                page=spec.page,
                size=spec.size,
            ),
        )

    async def _query_conversations(
        self,
        scope: MonitoringScope,
        spec: QuerySpec,
    ):
        return await MonitoringConversationQueryService(self).query_conversations(
            scope,
            spec,
        )

    async def get_usage_dashboard(
        self,
        scope: MonitoringScope,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> MonitoringUsageDashboard:
        return await MonitoringUsageQueryService(self).get_usage_dashboard(
            scope,
            start_date=start_date,
            end_date=end_date,
        )

    async def list_conversations(
        self,
        scope: MonitoringScope,
        spec: QuerySpec,
    ) -> tuple[list[MonitoringConversationListItem], int]:
        return await MonitoringConversationQueryService(self).list_conversations(
            scope,
            spec,
        )

    async def get_conversation_detail(
        self,
        scope: MonitoringScope,
        conversation_id: int,
        *,
        message_skip: int = 0,
        message_limit: int = 50,
    ) -> MonitoringConversationDetail:
        return await MonitoringConversationQueryService(self).get_conversation_detail(
            scope,
            conversation_id,
            message_skip=message_skip,
            message_limit=message_limit,
        )


__all__ = ["MonitoringScope", "MonitoringService"]
