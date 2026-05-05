"""
AI monitoring read service / AI 监控读服务。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

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
from app.schemas.common.query import QuerySpec
from app.services.ai.conversation_service import ConversationService
from app.services.ai.monitoring_conversation_query_service import (
    MonitoringConversationQueryService,
)
from app.services.ai.monitoring_query_support import MonitoringQuerySupport
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

    @property
    def _query_support(self) -> MonitoringQuerySupport:
        if not hasattr(self, "__query_support"):
            self.__query_support = MonitoringQuerySupport(
                self.db,
                platform_usage_tenant_name=self.PLATFORM_USAGE_TENANT_NAME,
            )
        return self.__query_support

    @staticmethod
    def admin_scope() -> MonitoringScope:
        return MonitoringScope(scope="admin")

    @staticmethod
    def tenant_scope(tenant_id: int) -> MonitoringScope:
        return MonitoringScope(scope="tenant", tenant_id=tenant_id)

    @staticmethod
    def _safe_int(value: Any) -> int:
        return MonitoringQuerySupport.safe_int(value)

    @staticmethod
    def _safe_float(value: Any) -> float:
        return MonitoringQuerySupport.safe_float(value)

    @staticmethod
    def _normalize_optional_bool(value: Any) -> bool | None:
        return MonitoringQuerySupport.normalize_optional_bool(value)

    @staticmethod
    def _normalize_fallback_history(value: Any) -> list[dict[str, Any]]:
        return MonitoringQuerySupport.normalize_fallback_history(value)

    @classmethod
    def _extract_call_trace_diagnostics(cls, request_metadata: Any) -> dict[str, Any]:
        return MonitoringQuerySupport.extract_call_trace_diagnostics(request_metadata)

    @staticmethod
    def _date_filters(column, start_date: date | None, end_date: date | None) -> list:
        return MonitoringQuerySupport.date_filters(column, start_date, end_date)

    @classmethod
    def _platform_usage_tenant_expr(cls):
        return MonitoringQuerySupport.platform_usage_tenant_expr()

    @classmethod
    def _effective_usage_tenant_expr(cls):
        return MonitoringQuerySupport.effective_usage_tenant_expr()

    @classmethod
    def _effective_usage_tenant_name_expr(cls):
        return MonitoringQuerySupport.effective_usage_tenant_name_expr(
            cls.PLATFORM_USAGE_TENANT_NAME,
        )

    @staticmethod
    def _format_dt(value: datetime | None) -> str | None:
        return MonitoringQuerySupport.format_dt(value)

    def _scope_usage_filters(
        self,
        scope: MonitoringScope,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list:
        return self._query_support.scope_usage_filters(
            scope,
            start_date=start_date,
            end_date=end_date,
        )

    def _scope_conversation_filters(self, scope: MonitoringScope) -> list:
        return self._query_support.scope_conversation_filters(scope)

    @staticmethod
    def _extract_caller_snapshot(request_metadata: Any) -> dict[str, Any]:
        return MonitoringQuerySupport.extract_caller_snapshot(request_metadata)

    @classmethod
    def _resolve_snapshot_display_role_name(
        cls,
        snapshot: dict[str, Any] | None,
        live_actor: MonitoringActorInfo | None = None,
    ) -> str | None:
        return MonitoringQuerySupport.resolve_snapshot_display_role_name(
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
        return MonitoringQuerySupport.build_actor_info_from_snapshot(
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
        return await self._query_support.load_actor_snapshot_map(
            scope,
            refs,
            start_date=start_date,
            end_date=end_date,
        )

    async def _load_conversation_actor_snapshot_map(
        self,
        scope: MonitoringScope,
        conversation_ids: set[int],
    ) -> dict[int, dict[str, Any]]:
        return await self._query_support.load_conversation_actor_snapshot_map(
            scope,
            conversation_ids,
        )

    async def _load_conversation_latest_turn_map(
        self,
        scope: MonitoringScope,
        conversation_ids: set[int],
    ) -> dict[int, dict[str, Any]]:
        return await self._query_support.load_conversation_latest_turn_map(
            scope,
            conversation_ids,
        )

    async def _load_actor_map(
        self,
        refs: set[tuple[str, int]],
    ) -> dict[tuple[str, int], MonitoringActorInfo]:
        return await self._query_support.load_actor_map(refs)

    async def _load_conversation_usage_map(
        self,
        scope: MonitoringScope,
        conversation_ids: set[int],
    ) -> dict[int, dict[str, Any]]:
        return await self._query_support.load_conversation_usage_map(
            scope,
            conversation_ids,
        )

    async def _load_tenant_names(self, tenant_ids: set[int]) -> dict[int, str]:
        return await self._query_support.load_tenant_names(tenant_ids)

    @staticmethod
    def _extract_runtime_filter_value(raw: Any) -> int | None:
        return MonitoringQuerySupport.extract_runtime_filter_value(raw)

    @classmethod
    def _split_conversation_runtime_filters(
        cls,
        spec: QuerySpec,
    ) -> tuple[int | None, int | None, QuerySpec]:
        return MonitoringQuerySupport.split_conversation_runtime_filters(spec)

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
