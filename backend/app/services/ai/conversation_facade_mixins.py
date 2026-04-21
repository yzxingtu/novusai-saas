"""ConversationService facade mixins."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.ai.types import ChatMessage
from app.models.ai.agent import Agent
from app.models.ai.agent_conversation import AgentConversation
from app.repositories.ai.conversation_message_repository import (
    ConversationMessageRepository,
)
from app.services.ai.action_log_service import resolve_action_level, write_ai_action_log
from app.services.ai.conversation_chat_lifecycle_service import (
    ConversationChatLifecycleService,
)
from app.services.ai.conversation_compaction_service import (
    ConversationCompactionService,
)
from app.services.ai.conversation_diagnostics_support import (
    build_context_diagnostics_payload,
    build_last_run_summary_payload,
    copy_metadata,
    extract_turn_diagnostics_from_metadata,
    normalize_context_sources,
    normalize_intent_plan,
    normalize_json_dict,
    normalize_json_safe_dict_value,
    normalize_json_safe_value,
    normalize_provider_events,
    normalize_retry_events,
    normalize_string_list,
    normalize_turn_record_payload,
    to_non_empty_str,
)
from app.services.ai.conversation_export_formatter import (
    to_json as export_to_json,
)
from app.services.ai.conversation_export_formatter import (
    to_markdown as export_to_markdown,
)
from app.services.ai.conversation_export_runtime_service import (
    ConversationExportRuntimeService,
)
from app.services.ai.conversation_history_access import (
    get_messages_for_conversation as fetch_messages_for_conversation,
)
from app.services.ai.conversation_history_access import (
    load_chat_history as load_chat_history_access,
)
from app.services.ai.conversation_history_access import (
    sanitize_tool_messages as sanitize_tool_messages_access,
)
from app.services.ai.conversation_history_service import ConversationHistoryService
from app.services.ai.conversation_interaction_service import (
    ConversationInteractionService,
)
from app.services.ai.conversation_memory_state_service import (
    ConversationMemoryStateService,
)
from app.services.ai.conversation_output_parser import parse_output
from app.services.ai.conversation_persistence_facade import (
    get_context_compaction_snapshot as load_context_compaction_snapshot,
)
from app.services.ai.conversation_persistence_facade import (
    mark_memory_updated as mark_memory_updated_persist,
)
from app.services.ai.conversation_persistence_facade import (
    persist_chat_messages as persist_chat_messages_persist,
)
from app.services.ai.conversation_persistence_facade import (
    persist_stream_completion as persist_stream_completion_persist,
)
from app.services.ai.conversation_persistence_facade import (
    persist_stream_last_error_marker as persist_stream_last_error_marker_persist,
)
from app.services.ai.conversation_persistence_facade import (
    persist_user_messages as persist_user_messages_persist,
)
from app.services.ai.conversation_persistence_facade import (
    save_stream_error_message as save_stream_error_message_persist,
)
from app.services.ai.conversation_persistence_facade import (
    update_stats as update_stats_persist,
)
from app.services.ai.conversation_persistence_facade import (
    upsert_context_compaction_snapshot as upsert_context_compaction_snapshot_persist,
)
from app.services.ai.conversation_read_model_service import (
    ConversationReadModelService,
)
from app.services.ai.conversation_runtime_projection_service import (
    ConversationRuntimeProjectionService,
)
from app.services.ai.conversation_search_query_service import (
    ConversationSearchQueryService,
)
from app.services.ai.conversation_stats_service import ConversationStatsService
from app.services.ai.conversation_timeline_service import (
    ConversationTimelineService,
)
from app.services.ai.execution_decision_service import ExecutionDecisionService
from app.services.ai.execution_trust_policy_service import (
    ExecutionTrustPolicyService,
)

if TYPE_CHECKING:
    from app.ai.engine.types import ExecutionResult
    from app.services.ai.conversation_service import ConversationService


class ConversationDiagnosticsFacade:
    @staticmethod
    def _build_context_diagnostics_payload(
        last_assistant_message: dict[str, Any] | None,
        *,
        compaction_snapshot: dict[str, Any] | None,
        interaction_mode_effective: str,
    ) -> dict[str, Any]:
        return build_context_diagnostics_payload(
            last_assistant_message,
            compaction_snapshot=compaction_snapshot,
            interaction_mode_effective=interaction_mode_effective,
        )

    @staticmethod
    def _build_last_run_summary_payload(
        last_assistant_message: dict[str, Any] | None,
        *,
        interaction_mode_effective: str,
        downgrade_reason: Any,
    ) -> dict[str, Any]:
        return build_last_run_summary_payload(
            last_assistant_message,
            interaction_mode_effective=interaction_mode_effective,
            downgrade_reason=downgrade_reason,
        )

    @staticmethod
    def _copy_metadata(raw: Any) -> dict[str, Any] | None:
        return copy_metadata(raw)

    @staticmethod
    def _normalize_json_safe(value: Any) -> Any:
        return normalize_json_safe_value(value)

    @staticmethod
    def _normalize_json_safe_dict(raw: Any) -> dict[str, Any] | None:
        return normalize_json_safe_dict_value(raw)

    @staticmethod
    def _normalize_turn_record_payload(turn_record: Any) -> dict[str, Any] | None:
        """Normalize runtime turn_record into JSON-safe dict / 将运行时 turn_record 规范化为可落库字典。"""
        return normalize_turn_record_payload(turn_record)

    @staticmethod
    def _to_non_empty_str(value: Any) -> str | None:
        return to_non_empty_str(value)

    @staticmethod
    def _normalize_string_list(value: Any) -> list[str]:
        return normalize_string_list(value)

    @staticmethod
    def _normalize_context_sources(value: Any) -> list[dict[str, Any]]:
        return normalize_context_sources(value)

    @staticmethod
    def _normalize_json_dict(value: Any) -> dict[str, Any] | None:
        return normalize_json_dict(value)

    @classmethod
    def _normalize_intent_plan(cls, value: Any) -> list[dict[str, Any]]:
        return normalize_intent_plan(value)

    @classmethod
    def _normalize_retry_events(cls, value: Any) -> list[dict[str, Any]]:
        return normalize_retry_events(value)

    @classmethod
    def _normalize_provider_events(cls, value: Any) -> list[dict[str, Any]]:
        return normalize_provider_events(value)

    @classmethod
    def _extract_turn_diagnostics_from_metadata(
        cls,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        return extract_turn_diagnostics_from_metadata(metadata)


class ConversationDependencyFacade:
    @property
    def read_model_service(self: ConversationService) -> ConversationReadModelService:
        if not hasattr(self, "_read_model_service"):
            self._read_model_service = ConversationReadModelService(
                self.db,
                tenant_admin_repo=self.tenant_admin_repo,
            )
        return self._read_model_service

    @property
    def message_repo(self: ConversationService) -> ConversationMessageRepository:
        if not hasattr(self, "_message_repo"):
            self._message_repo = ConversationMessageRepository(
                self.db,
                self.tenant_id,
            )
        return self._message_repo

    @property
    def timeline_service(self: ConversationService) -> ConversationTimelineService:
        if not hasattr(self, "_timeline_service"):
            self._timeline_service = ConversationTimelineService(
                self.db,
                memory_tenant_id=self._get_memory_tenant_id(),
                format_dt=self._format_dt,
            )
        return self._timeline_service

    @property
    def interaction_service(
        self: ConversationService,
    ) -> ConversationInteractionService:
        if not hasattr(self, "_interaction_service"):
            self._interaction_service = ConversationInteractionService(
                self.db,
                message_repo=self.message_repo,
                memory_tenant_id=self._get_memory_tenant_id(),
                decision_service_cls=ExecutionDecisionService,
                trust_policy_service_cls=ExecutionTrustPolicyService,
                write_ai_action_log_fn=write_ai_action_log,
                resolve_action_level_fn=resolve_action_level,
            )
        return self._interaction_service

    @property
    def export_runtime_service(
        self: ConversationService,
    ) -> ConversationExportRuntimeService:
        if not hasattr(self, "_export_runtime_service"):
            self._export_runtime_service = ConversationExportRuntimeService(
                message_repo=self.message_repo,
                read_model_service=self.read_model_service,
            )
        return self._export_runtime_service

    @property
    def history_service(self: ConversationService) -> ConversationHistoryService:
        if not hasattr(self, "_history_service"):
            self._history_service = ConversationHistoryService(
                message_repo=self.message_repo,
                read_model_service=self.read_model_service,
                default_max_messages=self.MAX_HISTORY_MESSAGES,
            )
        return self._history_service

    @property
    def search_query_service(
        self: ConversationService,
    ) -> ConversationSearchQueryService:
        if not hasattr(self, "_search_query_service"):
            self._search_query_service = ConversationSearchQueryService(
                message_repo=self.message_repo,
                read_model_service=self.read_model_service,
            )
        return self._search_query_service

    @property
    def chat_lifecycle_service(
        self: ConversationService,
    ) -> ConversationChatLifecycleService:
        if not hasattr(self, "_chat_lifecycle_service"):
            self._chat_lifecycle_service = ConversationChatLifecycleService(
                repo=self.repo,
                tenant_id=self.tenant_id,
                get_accessible_conversation=self.get_accessible_conversation,
                max_title_length=self.MAX_TITLE_LENGTH,
            )
        return self._chat_lifecycle_service

    @property
    def compaction_service(self: ConversationService) -> ConversationCompactionService:
        if not hasattr(self, "_compaction_service"):
            self._compaction_service = ConversationCompactionService(
                message_repo=self.message_repo,
                load_chat_history=self.load_chat_history,
                upsert_snapshot=self.upsert_context_compaction_snapshot,
            )
        return self._compaction_service

    @property
    def runtime_projection_service(
        self: ConversationService,
    ) -> ConversationRuntimeProjectionService:
        if not hasattr(self, "_runtime_projection_service"):
            self._runtime_projection_service = ConversationRuntimeProjectionService(
                message_repo=self.message_repo,
                read_model_service=self.read_model_service,
                get_accessible_conversation=self.get_accessible_conversation,
                get_context_compaction_snapshot=self.get_context_compaction_snapshot,
            )
        return self._runtime_projection_service

    @property
    def memory_state_service(self: ConversationService) -> Any:
        if not hasattr(self, "_memory_state_service"):
            self._memory_state_service = ConversationMemoryStateService(
                memory_tenant_id=self._get_memory_tenant_id(),
            )
        return self._memory_state_service

    @property
    def stats_service(self: ConversationService) -> ConversationStatsService:
        if not hasattr(self, "_stats_service"):
            self._stats_service = ConversationStatsService(
                repo=self.repo,
                parse_output_fn=parse_output,
            )
        return self._stats_service

    @property
    def stream_persistence_service(self: ConversationService) -> Any:
        if not hasattr(self, "_stream_persistence_service"):
            from app.services.ai.conversation_stream_persistence_service import (
                ConversationStreamPersistenceService,
            )

            self._stream_persistence_service = ConversationStreamPersistenceService(
                self
            )
        return self._stream_persistence_service

    @property
    def tenant_admin_repo(self: ConversationService) -> Any:
        if not hasattr(self, "_tenant_admin_repo"):
            from app.repositories.tenant.tenant_admin_repository import (
                TenantAdminRepository,
            )

            self._tenant_admin_repo = TenantAdminRepository(
                self.db,
                self.tenant_id,
            )
        return self._tenant_admin_repo


class ConversationExportFacade:
    @staticmethod
    def _to_json(
        conversation: AgentConversation,
        messages: list,
    ) -> str:
        return export_to_json(conversation, messages)

    @staticmethod
    def _to_markdown(
        conversation: AgentConversation,
        messages: list,
    ) -> str:
        return export_to_markdown(conversation, messages)


class ConversationHistoryFacade:
    async def load_chat_history(
        self: ConversationService,
        conversation_id: int,
        max_messages: int = 0,
        max_tokens: int = 0,
    ) -> list[ChatMessage]:
        return await load_chat_history_access(
            self,
            conversation_id=conversation_id,
            max_messages=max_messages,
            max_tokens=max_tokens,
        )

    @staticmethod
    def sanitize_tool_messages(
        messages: list[ChatMessage],
    ) -> list[ChatMessage]:
        return sanitize_tool_messages_access(messages)

    async def get_messages_for_conversation(
        self: ConversationService,
        conversation_id: int,
    ) -> list[Any]:
        return await fetch_messages_for_conversation(self, conversation_id)


class ConversationPersistenceFacade:
    async def persist_chat_messages(
        self: ConversationService,
        conversation: AgentConversation,
        result: ExecutionResult,
        history_count: int,
        history_messages: list[ChatMessage] | None = None,
        agent_id: int | None = None,
        route_source: str | None = None,
        *,
        context_diagnostics: dict[str, Any] | None = None,
        last_run_summary: dict[str, Any] | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        return await persist_chat_messages_persist(
            self,
            conversation=conversation,
            result=result,
            history_count=history_count,
            history_messages=history_messages,
            agent_id=agent_id,
            route_source=route_source,
            context_diagnostics=context_diagnostics,
            last_run_summary=last_run_summary,
        )

    async def persist_user_messages(
        self: ConversationService,
        *,
        conversation: AgentConversation,
        messages: list[ChatMessage],
    ) -> int:
        return await persist_user_messages_persist(
            self,
            conversation=conversation,
            messages=messages,
        )

    async def mark_memory_updated(
        self: ConversationService, conversation_id: int
    ) -> None:
        await mark_memory_updated_persist(self, conversation_id)

    async def get_context_compaction_snapshot(
        self: ConversationService,
        conversation_id: int,
    ) -> dict[str, Any] | None:
        return await load_context_compaction_snapshot(
            self,
            conversation_id,
            metadata_key=self.CONTEXT_COMPACTION_METADATA_KEY,
        )

    async def upsert_context_compaction_snapshot(
        self: ConversationService,
        conversation_id: int,
        *,
        summary: str,
        source_message_count: int,
        source_token_estimate: int,
    ) -> dict[str, Any] | None:
        return await upsert_context_compaction_snapshot_persist(
            self,
            conversation_id,
            metadata_key=self.CONTEXT_COMPACTION_METADATA_KEY,
            summary=summary,
            source_message_count=source_message_count,
            source_token_estimate=source_token_estimate,
        )

    async def update_stats(
        self: ConversationService,
        conversation: AgentConversation,
        result: ExecutionResult,
        current_agent: Agent | None = None,
    ) -> None:
        await update_stats_persist(
            self,
            conversation=conversation,
            result=result,
            current_agent=current_agent,
        )

    async def persist_stream_completion(
        self: ConversationService,
        *,
        conversation_id: int,
        result: ExecutionResult,
        history_count: int,
        history_messages: list[ChatMessage] | None = None,
        agent_id: int | None = None,
        route_source: str | None = None,
        context_diagnostics: dict[str, Any] | None = None,
        last_run_summary: dict[str, Any] | None = None,
        current_agent: Agent | None = None,
    ) -> int:
        return await persist_stream_completion_persist(
            self,
            conversation_id=conversation_id,
            result=result,
            history_count=history_count,
            history_messages=history_messages,
            agent_id=agent_id,
            route_source=route_source,
            context_diagnostics=context_diagnostics,
            last_run_summary=last_run_summary,
            current_agent=current_agent,
        )

    async def persist_stream_last_error_marker(
        self: ConversationService,
        *,
        conversation_id: int,
        error_type: str,
        error_message: str,
        friendly_message: str,
        partial: bool,
        extra_payload: dict[str, Any] | None = None,
        memory_runtime_policy: dict[str, Any] | None = None,
    ) -> bool:
        return await persist_stream_last_error_marker_persist(
            self,
            conversation_id=conversation_id,
            error_type=error_type,
            error_message=error_message,
            friendly_message=friendly_message,
            partial=partial,
            extra_payload=extra_payload,
            memory_runtime_policy=memory_runtime_policy,
        )

    async def save_stream_error_message(
        self: ConversationService,
        *,
        conversation_id: int,
        error_text: str,
        user_message: str,
        result: ExecutionResult,
        context_diagnostics_payload: dict[str, Any],
        last_run_summary_payload: dict[str, Any],
        persist_user_message: bool,
        agent_id: int,
        build_stream_error_display: Any,
    ) -> int:
        return await save_stream_error_message_persist(
            self,
            conversation_id=conversation_id,
            error_text=error_text,
            user_message=user_message,
            result=result,
            context_diagnostics_payload=context_diagnostics_payload,
            last_run_summary_payload=last_run_summary_payload,
            persist_user_message=persist_user_message,
            agent_id=agent_id,
            build_stream_error_display=build_stream_error_display,
        )
