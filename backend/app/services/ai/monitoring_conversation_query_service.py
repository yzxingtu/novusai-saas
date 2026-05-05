"""
Monitoring conversation query service.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import exists, func, select

from app.configs.service import PLATFORM_TENANT_ID
from app.exceptions import NotFoundException
from app.models.ai import AgentConversation, AICallLog, AIModel, AIProvider
from app.schemas.ai.monitoring import (
    MonitoringConversationDetail,
    MonitoringConversationListItem,
)
from app.schemas.common.query import QuerySpec
from app.services.ai.agent_chat_interaction_support import (
    strip_legacy_interaction_mode_fields,
)
from app.services.ai.conversation_payload_sanitizer import (
    strip_assistant_legacy_turn_projection_fields,
)
from app.services.ai.conversation_turn_flow_projector import (
    ConversationTurnFlowProjector,
)
from app.services.ai.monitoring_call_trace_projector import (
    MonitoringCallTraceProjector,
)
from app.services.ai.monitoring_query_dependencies import (
    resolve_monitoring_conversation_query_dependencies,
)
from app.services.ai.monitoring_read_model_projector import (
    MonitoringReadModelProjector,
)

if TYPE_CHECKING:
    from app.services.ai.monitoring_service import MonitoringScope, MonitoringService


class MonitoringConversationQueryService:
    def __init__(self, service: MonitoringService) -> None:
        self.service = service

    async def query_conversations(
        self,
        scope: MonitoringScope,
        spec: QuerySpec,
    ) -> tuple[list[AgentConversation], int]:
        base = self.service
        dependencies = resolve_monitoring_conversation_query_dependencies(base)
        provider_id, model_id, normalized_spec = (
            base._split_conversation_runtime_filters(spec)
        )

        if provider_id is None and model_id is None:
            if scope.is_tenant:
                service = dependencies.tenant_conversation_service_factory(
                    base.db,
                    int(scope.tenant_id),
                )
                return await service.query_list(spec=normalized_spec)

            repo = dependencies.admin_conversation_repo_factory(base.db)
            return await repo.query_list(normalized_spec)

        repo = (
            dependencies.tenant_conversation_repo_factory(
                base.db,
                int(scope.tenant_id),
            )
            if scope.is_tenant
            else dependencies.admin_conversation_repo_factory(base.db)
        )
        allowed_fields = repo.get_allowed_fields(None)

        query = select(AgentConversation).where(
            *base._scope_conversation_filters(scope)
        )
        if normalized_spec.filters:
            query = repo._apply_filters(query, normalized_spec.filters, allowed_fields)

        runtime_filters = [
            AICallLog.is_deleted.is_(False),
            AICallLog.conversation_id == AgentConversation.id,
        ]
        if scope.is_tenant:
            runtime_filters.append(AICallLog.billing_tenant_id == scope.tenant_id)
        if provider_id is not None:
            runtime_filters.append(AICallLog.provider_id == provider_id)
        if model_id is not None:
            runtime_filters.append(AICallLog.model_id == model_id)

        query = query.where(exists(select(AICallLog.id).where(*runtime_filters)))
        query = repo._apply_data_permission_if_needed(query)

        total = (
            await base.db.execute(select(func.count()).select_from(query.subquery()))
        ).scalar() or 0
        query = repo._apply_sort(
            query, normalized_spec.sort, repo.get_sortable_fields()
        )
        query = query.offset(normalized_spec.offset).limit(normalized_spec.limit)

        result = await base.db.execute(query)
        return list(result.scalars().all()), total

    async def list_conversations(
        self,
        scope: MonitoringScope,
        spec: QuerySpec,
    ) -> tuple[list[MonitoringConversationListItem], int]:
        base = self.service
        items, total = await self.query_conversations(scope, spec)

        conversation_ids = {item.id for item in items}
        tenant_ids = {item.tenant_id for item in items if item.tenant_id is not None}
        usage_map = await base._load_conversation_usage_map(scope, conversation_ids)
        latest_turn_map = await base._load_conversation_latest_turn_map(
            scope,
            conversation_ids,
        )
        conversation_actor_snapshot_map = (
            await base._load_conversation_actor_snapshot_map(
                scope,
                conversation_ids,
            )
        )
        tenant_names = await base._load_tenant_names(tenant_ids)
        actor_refs = {
            (str(item.owner_type), int(item.user_id))
            for item in items
            if item.user_id is not None
            and item.owner_type in {"platform_admin", "tenant_admin", "tenant_user"}
        }
        actor_refs.update(
            {
                (
                    str(snapshot_info.get("actor_type")),
                    int(snapshot_info.get("actor_id")),
                )
                for snapshot_info in conversation_actor_snapshot_map.values()
                if snapshot_info.get("actor_type") and snapshot_info.get("actor_id")
            }
        )
        actor_map = await base._load_actor_map(actor_refs)

        result: list[MonitoringConversationListItem] = []
        for item in items:
            usage = usage_map.get(item.id, {})
            latest_turn = latest_turn_map.get(item.id, {})
            snapshot_info = conversation_actor_snapshot_map.get(item.id, {})
            actor_ref = None
            if snapshot_info.get("actor_type") and snapshot_info.get("actor_id"):
                actor_ref = (
                    str(snapshot_info.get("actor_type")),
                    int(snapshot_info.get("actor_id")),
                )
            elif item.user_id is not None and item.owner_type:
                actor_ref = (str(item.owner_type), int(item.user_id))
            actor = base._build_actor_info_from_snapshot(
                snapshot_info.get("snapshot"),
                actor_id=actor_ref[1] if actor_ref else None,
                actor_type=actor_ref[0] if actor_ref else None,
                tenant_id=(
                    PLATFORM_TENANT_ID
                    if item.tenant_id == PLATFORM_TENANT_ID
                    else item.tenant_id
                ),
                tenant_name=(
                    base.PLATFORM_USAGE_TENANT_NAME
                    if item.tenant_id == PLATFORM_TENANT_ID
                    else tenant_names.get(item.tenant_id)
                ),
                live_actor=actor_map.get(actor_ref) if actor_ref else None,
            )
            result.append(
                MonitoringConversationListItem(
                    id=item.id,
                    tenant_id=item.tenant_id,
                    tenant_name=(
                        base.PLATFORM_USAGE_TENANT_NAME
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
                    lifecycle_status=item.status,
                    display_status=latest_turn.get("display_status") or item.status,
                    latest_turn_status=latest_turn.get("latest_turn_status"),
                    latest_turn_outcome=latest_turn.get("latest_turn_outcome"),
                    latest_conversation_outcome=latest_turn.get(
                        "latest_conversation_outcome"
                    ),
                    latest_failure_kind=latest_turn.get("latest_failure_kind"),
                    latest_termination_reason=latest_turn.get(
                        "latest_termination_reason"
                    ),
                    latest_error_message=latest_turn.get("latest_error_message"),
                    latest_turn_flow_terminal_status=latest_turn.get(
                        "latest_turn_flow_terminal_status"
                    ),
                    latest_turn_flow_terminal_type=latest_turn.get(
                        "latest_turn_flow_terminal_type"
                    ),
                    latest_turn_error_type=latest_turn.get("latest_turn_error_type"),
                    latest_turn_created_at=latest_turn.get("latest_turn_created_at"),
                    message_count=base._safe_int(item.message_count),
                    call_count=base._safe_int(usage.get("call_count")),
                    total_tokens=max(
                        base._safe_int(item.token_count),
                        base._safe_int(usage.get("total_tokens")),
                    ),
                    total_cost=max(
                        base._safe_float(item.cost),
                        base._safe_float(usage.get("total_cost")),
                    ),
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
        base = self.service
        dependencies = resolve_monitoring_conversation_query_dependencies(base)
        if scope.is_tenant:
            service = dependencies.tenant_conversation_service_factory(
                base.db,
                int(scope.tenant_id),
            )
            conversation = await service.get_by_id(conversation_id)
            if not conversation:
                raise NotFoundException(message="conversation not found")
        else:
            (
                service,
                conversation,
            ) = await dependencies.conversation_service_cls.get_service_for_conversation(
                base.db,
                conversation_id,
            )

        detail = await service.get_conversation_detail(
            conversation_id=conversation_id,
            message_skip=message_skip,
            message_limit=message_limit,
        )
        normalized_message_list: list[dict[str, object]] = []
        for item in detail.get("message_list") or []:
            if not isinstance(item, dict):
                continue
            payload = dict(item)
            projected_turn_flow = (
                ConversationTurnFlowProjector.project_from_message_payload(payload)
            )
            if projected_turn_flow is not None:
                payload["turn_flow"] = projected_turn_flow
                metadata_payload = (
                    dict(payload.get("metadata") or {})
                    if isinstance(payload.get("metadata"), dict)
                    else {}
                )
                metadata_payload["turn_flow"] = projected_turn_flow
                payload["metadata"] = metadata_payload
            normalized_message_list.append(
                strip_assistant_legacy_turn_projection_fields(payload)
            )
        usage = (await base._load_conversation_usage_map(scope, {conversation_id})).get(
            conversation_id, {}
        )
        conversation_actor_snapshot_map = (
            await base._load_conversation_actor_snapshot_map(
                scope,
                {conversation_id},
            )
        )
        snapshot_info = conversation_actor_snapshot_map.get(conversation_id, {})
        actor_ref = None
        if snapshot_info.get("actor_type") and snapshot_info.get("actor_id"):
            actor_ref = (
                str(snapshot_info.get("actor_type")),
                int(snapshot_info.get("actor_id")),
            )
        elif conversation.user_id is not None and conversation.owner_type:
            actor_ref = (str(conversation.owner_type), int(conversation.user_id))
        actor_map = await base._load_actor_map({actor_ref}) if actor_ref else {}
        actor = base._build_actor_info_from_snapshot(
            snapshot_info.get("snapshot"),
            actor_id=actor_ref[1] if actor_ref else None,
            actor_type=actor_ref[0] if actor_ref else None,
            tenant_id=(
                PLATFORM_TENANT_ID
                if conversation.tenant_id == PLATFORM_TENANT_ID
                else conversation.tenant_id
            ),
            tenant_name=(
                base.PLATFORM_USAGE_TENANT_NAME
                if conversation.tenant_id == PLATFORM_TENANT_ID
                else (await base._load_tenant_names({conversation.tenant_id})).get(
                    conversation.tenant_id
                )
            ),
            live_actor=actor_map.get(actor_ref) if actor_ref else None,
        )

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
                func.coalesce(AICallLog.model_name_snapshot, AIModel.name).label(
                    "model_name"
                ),
                func.coalesce(AICallLog.provider_name_snapshot, AIProvider.name).label(
                    "provider_name"
                ),
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
        trace_rows = (await base.db.execute(trace_stmt)).all()
        call_trace = [
            MonitoringCallTraceProjector.build_item(row) for row in trace_rows
        ]
        latest_turn = {}
        for message in reversed(normalized_message_list):
            latest_turn = MonitoringReadModelProjector.build_latest_turn_summary_from_message_payload(
                message
            )
            if latest_turn:
                break
        if not latest_turn:
            latest_turn = MonitoringReadModelProjector.build_latest_turn_summary(
                metadata={
                    "context_diagnostics": detail.get("context_diagnostics"),
                    "last_run_summary": detail.get("last_run_summary"),
                }
            )

        return MonitoringConversationDetail(
            id=conversation.id,
            tenant_id=conversation.tenant_id,
            tenant_name=(
                base.PLATFORM_USAGE_TENANT_NAME
                if conversation.tenant_id == PLATFORM_TENANT_ID
                else (await base._load_tenant_names({conversation.tenant_id})).get(
                    conversation.tenant_id
                )
            ),
            agent_id=conversation.agent_id,
            agent_name=detail.get("agent_name"),
            agent_avatar=detail.get("agent_avatar"),
            owner_type=conversation.owner_type,
            actor=actor,
            title=conversation.title,
            status=conversation.status,
            lifecycle_status=conversation.status,
            display_status=latest_turn.get("display_status") or conversation.status,
            latest_turn_status=latest_turn.get("latest_turn_status"),
            latest_turn_outcome=latest_turn.get("latest_turn_outcome"),
            latest_conversation_outcome=latest_turn.get("latest_conversation_outcome"),
            latest_failure_kind=latest_turn.get("latest_failure_kind"),
            latest_termination_reason=latest_turn.get("latest_termination_reason"),
            latest_error_message=latest_turn.get("latest_error_message"),
            latest_turn_flow_terminal_status=latest_turn.get(
                "latest_turn_flow_terminal_status"
            ),
            latest_turn_flow_terminal_type=latest_turn.get(
                "latest_turn_flow_terminal_type"
            ),
            latest_turn_error_type=latest_turn.get("latest_turn_error_type"),
            latest_turn_created_at=latest_turn.get("latest_turn_created_at"),
            message_count=base._safe_int(detail.get("message_count")),
            total_tokens=max(
                base._safe_int(detail.get("token_count")),
                base._safe_int(usage.get("total_tokens")),
            ),
            total_cost=max(
                base._safe_float(detail.get("cost")),
                base._safe_float(usage.get("total_cost")),
            ),
            call_count=base._safe_int(usage.get("call_count")),
            last_call_at=usage.get("last_call_at"),
            created_at=conversation.created_at,
            updated_at=conversation.updated_at,
            context_diagnostics=detail.get("context_diagnostics"),
            last_run_summary=detail.get("last_run_summary"),
            metadata=strip_legacy_interaction_mode_fields(detail.get("metadata")),
            message_list=normalized_message_list,
            call_trace=call_trace,
        )
