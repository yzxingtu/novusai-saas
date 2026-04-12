"""
对话数据生命周期管理 Service / Conversation Lifecycle Service

提供对话列表、详情、搜索、归档、删除和导出
Provides conversation list, detail, search, archive, delete and export.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.json_safe import normalize_json_safe, normalize_json_safe_dict
from app.ai.types import ChatMessage
from app.configs.service import PLATFORM_TENANT_ID
from app.core.base_service import TenantService
from app.core.i18n import _
from app.core.logging import LogManager
from app.enums.agent import (
    ConversationOwnerTypeEnum,
    ConversationStatusEnum,
)
from app.exceptions import BusinessException, NotFoundException
from app.models.ai.agent import Agent
from app.models.ai.agent_conversation import AgentConversation
from app.repositories.ai.agent_conversation_repository import (
    AdminAgentConversationRepository,
    AgentConversationRepository,
)
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
from app.services.ai.conversation_diagnostics_projector import (
    ConversationDiagnosticsProjector,
)
from app.services.ai.conversation_export_runtime_service import (
    ConversationExportRuntimeService,
)
from app.services.ai.conversation_export_service import ConversationExportService
from app.services.ai.conversation_history_service import ConversationHistoryService
from app.services.ai.conversation_interaction_service import (
    ConversationInteractionService,
)
from app.services.ai.conversation_memory_state_service import (
    ConversationMemoryStateService,
)
from app.services.ai.conversation_message_persistence_service import (
    ConversationMessagePersistenceService,
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
from app.services.ai.execution_decision_service import (
    ExecutionDecisionService,  # noqa: F401
)
from app.services.ai.execution_trust_policy_service import (
    ExecutionTrustPolicyService,  # noqa: F401
)

if TYPE_CHECKING:
    from app.ai.engine.types import ExecutionResult
    from app.repositories.tenant.tenant_admin_repository import (
        TenantAdminRepository,
    )
    from app.services.ai.conversation_stream_persistence_service import (
        ConversationStreamPersistenceService,
    )

logger = LogManager.get_logger("ai.conversation_service")
_CONTEXT_COMPACTION_METADATA_KEY = "context_compaction"


class SessionMemoryService:
    """Legacy shim kept for conversation-service patch compatibility."""

    def __init__(self, memory_tenant_id: int):
        self._service = ConversationMemoryStateService(memory_tenant_id=memory_tenant_id)

    async def get_conversation_memory_state(self, conversation_id: int) -> dict[str, Any]:
        return await self._service.get_state(conversation_id)

    async def clear_conversation_memory(self, conversation_id: int) -> int:
        return await self._service.clear_state(conversation_id)

    async def clear_conversation_memory_safe(self, conversation_id: int) -> None:
        await self._service.clear_state_safe(conversation_id)


def parse_output(*args: Any, **kwargs: Any) -> Any:
    """Lazy shim to preserve the legacy patch path without importing engine at module load."""
    from app.ai.engine.output_parser import parse_output as _parse_output

    return _parse_output(*args, **kwargs)


class ConversationService(
    TenantService[AgentConversation, AgentConversationRepository]
):
    """
    对话数据生命周期管理 Service / Conversation lifecycle service.

    提供对话列表、详情、搜索、归档、删除和导出
    """

    model = AgentConversation
    repository_class = AgentConversationRepository

    @staticmethod
    def _format_dt(dt: datetime | None) -> str | None:
        return ConversationReadModelService.format_dt(dt)

    @property
    def read_model_service(self) -> ConversationReadModelService:
        if not hasattr(self, "_read_model_service"):
            self._read_model_service = ConversationReadModelService(
                self.db,
                tenant_admin_repo=self.tenant_admin_repo,
            )
        return self._read_model_service

    @property
    def message_repo(self) -> ConversationMessageRepository:
        """获取消息 Repository（延迟创建） / Get message repo (lazy init)."""
        if not hasattr(self, "_message_repo"):
            self._message_repo = ConversationMessageRepository(
                self.db,
                self.tenant_id,
            )
        return self._message_repo

    @property
    def timeline_service(self) -> ConversationTimelineService:
        if not hasattr(self, "_timeline_service"):
            self._timeline_service = ConversationTimelineService(
                self.db,
                memory_tenant_id=self._get_memory_tenant_id(),
                format_dt=self._format_dt,
            )
        return self._timeline_service

    @property
    def interaction_service(self) -> ConversationInteractionService:
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
    def export_runtime_service(self) -> ConversationExportRuntimeService:
        if not hasattr(self, "_export_runtime_service"):
            self._export_runtime_service = ConversationExportRuntimeService(
                message_repo=self.message_repo,
                read_model_service=self.read_model_service,
            )
        return self._export_runtime_service

    @property
    def history_service(self) -> ConversationHistoryService:
        if not hasattr(self, "_history_service"):
            self._history_service = ConversationHistoryService(
                message_repo=self.message_repo,
                read_model_service=self.read_model_service,
                default_max_messages=self.MAX_HISTORY_MESSAGES,
            )
        return self._history_service

    @property
    def search_query_service(self) -> ConversationSearchQueryService:
        if not hasattr(self, "_search_query_service"):
            self._search_query_service = ConversationSearchQueryService(
                message_repo=self.message_repo,
                read_model_service=self.read_model_service,
            )
        return self._search_query_service

    @property
    def chat_lifecycle_service(self) -> ConversationChatLifecycleService:
        if not hasattr(self, "_chat_lifecycle_service"):
            self._chat_lifecycle_service = ConversationChatLifecycleService(
                repo=self.repo,
                tenant_id=self.tenant_id,
                get_accessible_conversation=self.get_accessible_conversation,
                max_title_length=self.MAX_TITLE_LENGTH,
            )
        return self._chat_lifecycle_service

    @property
    def compaction_service(self) -> ConversationCompactionService:
        if not hasattr(self, "_compaction_service"):
            self._compaction_service = ConversationCompactionService(
                message_repo=self.message_repo,
                load_chat_history=self.load_chat_history,
                upsert_snapshot=self.upsert_context_compaction_snapshot,
            )
        return self._compaction_service

    @property
    def runtime_projection_service(self) -> ConversationRuntimeProjectionService:
        if not hasattr(self, "_runtime_projection_service"):
            self._runtime_projection_service = ConversationRuntimeProjectionService(
                message_repo=self.message_repo,
                read_model_service=self.read_model_service,
                get_accessible_conversation=self.get_accessible_conversation,
                get_context_compaction_snapshot=self.get_context_compaction_snapshot,
            )
        return self._runtime_projection_service

    @property
    def memory_state_service(self) -> SessionMemoryService:
        if not hasattr(self, "_memory_state_service"):
            self._memory_state_service = SessionMemoryService(
                self._get_memory_tenant_id()
            )
        return self._memory_state_service

    @property
    def stats_service(self) -> ConversationStatsService:
        if not hasattr(self, "_stats_service"):
            self._stats_service = ConversationStatsService(
                repo=self.repo,
                parse_output_fn=lambda output, schema: parse_output(output, schema),
            )
        return self._stats_service

    @property
    def stream_persistence_service(self) -> ConversationStreamPersistenceService:
        if not hasattr(self, "_stream_persistence_service"):
            from app.services.ai.conversation_stream_persistence_service import (
                ConversationStreamPersistenceService,
            )

            self._stream_persistence_service = ConversationStreamPersistenceService(
                self
            )
        return self._stream_persistence_service

    @property
    def tenant_admin_repo(self) -> TenantAdminRepository:
        """获取企业管理员 Repository（延迟创建） / Get tenant admin repo (lazy init)."""
        if not hasattr(self, "_tenant_admin_repo"):
            from app.repositories.tenant.tenant_admin_repository import (
                TenantAdminRepository,
            )

            self._tenant_admin_repo = TenantAdminRepository(
                self.db,
                self.tenant_id,
            )
        return self._tenant_admin_repo

    async def enrich_conversation_list(
        self,
        items: list[AgentConversation],
        include_user_info: bool = False,
    ) -> list[dict]:
        return await self.read_model_service.enrich_conversation_list(
            items,
            include_user_info=include_user_info,
        )

    async def enrich_conversation_detail(
        self,
        detail: dict,
        conversation: AgentConversation,
    ) -> dict:
        return await self.read_model_service.enrich_conversation_detail(
            detail,
            conversation=conversation,
        )

    # ========================================
    # 详情 / Detail
    # ========================================

    @classmethod
    async def get_service_for_conversation(
        cls,
        db: AsyncSession,
        conversation_id: int,
    ) -> tuple[ConversationService, AgentConversation]:
        repo = AdminAgentConversationRepository(db)
        conversation = await repo.get_by_id(conversation_id)
        if not conversation:
            raise NotFoundException(
                message=_("agent_chat.error.conversation_not_found"),
            )
        return cls(db, conversation.tenant_id), conversation

    @classmethod
    async def get_platform_admin_chat_service_for_user(
        cls,
        db: AsyncSession,
        conversation_id: int,
        admin_user_id: int,
    ) -> tuple[ConversationService, AgentConversation]:
        """Resolve platform-admin chat conversation scoped to current admin / 解析当前平台管理员自己的聊天会话。"""
        service = cls(db, PLATFORM_TENANT_ID)
        conversation = await service.get_accessible_conversation(
            conversation_id,
            user_id=admin_user_id,
            owner_type=ConversationOwnerTypeEnum.PLATFORM_ADMIN.value,
        )
        return service, conversation

    async def get_accessible_conversation(
        self,
        conversation_id: int,
        user_id: int | None = None,
        owner_type: str | None = None,
    ) -> AgentConversation:
        conversation = await self.repo.get_by_id(conversation_id)
        if not conversation:
            raise NotFoundException(
                message=_("agent_chat.error.conversation_not_found"),
            )
        if owner_type is not None and conversation.owner_type != owner_type:
            raise NotFoundException(
                message=_("agent_chat.error.conversation_not_found"),
            )
        if user_id is not None and conversation.user_id != user_id:
            raise NotFoundException(
                message=_("agent_chat.error.conversation_not_found"),
            )
        return conversation

    async def get_conversation_detail(
        self,
        conversation_id: int,
        message_skip: int = 0,
        message_limit: int = 50,
        user_id: int | None = None,
        owner_type: str | None = None,
    ) -> dict[str, Any]:
        """
        获取对话详情（含分页消息列表）/ Get conversation detail with paginated messages.

        Args:
            conversation_id: 对话 ID
            message_skip: 消息跳过数量
            message_limit: 消息返回数量

        Returns:
            对话详情字典，含 messages 和 message_count
        """
        return await self.runtime_projection_service.get_conversation_detail(
            conversation_id=conversation_id,
            message_skip=message_skip,
            message_limit=message_limit,
            user_id=user_id,
            owner_type=owner_type,
        )

    async def delete_accessible_conversation(
        self,
        conversation_id: int,
        user_id: int | None = None,
        owner_type: str | None = None,
    ) -> None:
        await self.get_accessible_conversation(
            conversation_id,
            user_id=user_id,
            owner_type=owner_type,
        )
        await self.delete(conversation_id)

    async def update_conversation_title(
        self,
        conversation_id: int,
        title: str,
        user_id: int | None = None,
        owner_type: str | None = None,
    ) -> AgentConversation:
        conversation = await self.get_accessible_conversation(
            conversation_id,
            user_id=user_id,
            owner_type=owner_type,
        )
        normalized_title = (title or "").strip()
        conversation.title = normalized_title[:200] if normalized_title else None
        await self.db.flush()
        return conversation

    async def update_last_assistant_interaction_state(
        self,
        conversation_id: int,
        updates: list[dict[str, Any]],
        user_id: int | None = None,
        owner_type: str | None = None,
        interaction_mode_requested: str | None = None,
        interaction_mode_effective: str | None = None,
        interaction_mode_downgrade_reason: str | None = None,
    ) -> int:
        conversation = await self.get_accessible_conversation(
            conversation_id,
            user_id=user_id,
            owner_type=owner_type,
        )
        return await self.interaction_service.update_last_assistant_interaction_state(
            conversation=conversation,
            updates=updates,
            user_id=user_id,
            owner_type=owner_type,
            interaction_mode_requested=interaction_mode_requested,
            interaction_mode_effective=interaction_mode_effective,
            interaction_mode_downgrade_reason=interaction_mode_downgrade_reason,
        )


    def _get_memory_tenant_id(self) -> int:
        return self.tenant_id if self.tenant_id is not None else PLATFORM_TENANT_ID

    @staticmethod
    def _build_context_diagnostics_payload(
        last_assistant_message: dict[str, Any] | None,
        *,
        compaction_snapshot: dict[str, Any] | None,
        interaction_mode_effective: str,
    ) -> dict[str, Any]:
        return ConversationRuntimeProjectionService.build_context_diagnostics_payload(
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
        return ConversationRuntimeProjectionService.build_last_run_summary_payload(
            last_assistant_message,
            interaction_mode_effective=interaction_mode_effective,
            downgrade_reason=downgrade_reason,
        )

    async def rebuild_context_compaction_snapshot(
        self,
        conversation_id: int,
        *,
        user_id: int | None = None,
        owner_type: str | None = None,
    ) -> dict[str, Any] | None:
        conversation = await self.get_accessible_conversation(
            conversation_id,
            user_id=user_id,
            owner_type=owner_type,
        )
        return await self.compaction_service.rebuild_snapshot(
            conversation_id=conversation_id,
            conversation=conversation,
        )

    async def get_conversation_timeline(
        self,
        conversation_id: int,
        *,
        user_id: int | None = None,
        owner_type: str | None = None,
    ) -> list[dict[str, Any]]:
        conversation = await self.get_accessible_conversation(
            conversation_id,
            user_id=user_id,
            owner_type=owner_type,
        )
        messages = await self.message_repo.get_by_conversation(
            conversation_id=conversation_id,
            skip=0,
            limit=500,
        )
        return await self.timeline_service.get_conversation_timeline(
            conversation_id=conversation_id,
            conversation=conversation,
            messages=messages,
        )

    async def _build_call_log_summary(
        self,
        conversation_id: int,
    ) -> dict[str, Any] | None:
        return await self.timeline_service.build_call_log_summary(conversation_id)

    async def get_conversation_memory_state(
        self,
        conversation_id: int,
        user_id: int | None = None,
        owner_type: str | None = None,
    ) -> dict[str, Any]:
        await self.get_accessible_conversation(
            conversation_id,
            user_id=user_id,
            owner_type=owner_type,
        )
        return await self.memory_state_service.get_conversation_memory_state(
            conversation_id
        )

    async def clear_conversation_memory_state(
        self,
        conversation_id: int,
        user_id: int | None = None,
        owner_type: str | None = None,
    ) -> int:
        await self.get_accessible_conversation(
            conversation_id,
            user_id=user_id,
            owner_type=owner_type,
        )
        return await self.memory_state_service.clear_conversation_memory(
            conversation_id
        )

    # ========================================
    # 搜索 / Search
    # ========================================

    async def search_messages(
        self,
        keyword: str,
        page: int = 1,
        page_size: int = 20,
    ) -> dict[str, Any]:
        """
        跨对话全文搜索消息内容 / Full-text search messages across conversations.

        Args:
            keyword: 搜索关键词
            page: 页码
            page_size: 每页数量

        Returns:
            搜索结果字典
        """
        return await self.search_query_service.search_messages(
            keyword=keyword,
            page=page,
            page_size=page_size,
        )

    # ========================================
    # 归档 / Archive
    # ========================================

    async def archive_conversation(self, conversation_id: int) -> AgentConversation:
        """
        归档单个对话 / Archive single conversation.

        Args:
            conversation_id: 对话 ID

        Returns:
            更新后的 AgentConversation
        """
        conversation = await self.repo.get_by_id(conversation_id)
        if not conversation:
            raise NotFoundException(message=_("conversation.not_found"))

        if conversation.status == ConversationStatusEnum.ARCHIVED.value:
            raise BusinessException(
                message=_("conversation.already_archived"),
            )

        updated = await self.repo.update(
            conversation_id,
            {
                "status": ConversationStatusEnum.ARCHIVED.value,
            },
        )

        # Proactively clear session memory (immediate cleanup beyond TTL) / 主动清理会话记忆（TTL 外的即时清理）
        await self.memory_state_service.clear_conversation_memory_safe(
            conversation_id
        )

        logger.info(
            "Conversation archived: conversation_id={} tenant_id={}",
            conversation_id,
            self.tenant_id,
        )

        return updated

    async def _after_delete(self, id: int) -> None:
        """
        对话删除后清理会话记忆（失败降级，不影响删除主流程）/ Clear session memory after delete (best-effort, does not block delete).
        """
        await super()._after_delete(id)
        try:
            await self.memory_state_service.clear_conversation_memory(id)
        except Exception as exc:  # pragma: no cover - best effort cleanup path
            logger.warning(
                "Delete conversation memory cleanup failed: conversation={} tenant={} err={}",
                id,
                self.tenant_id,
                exc,
            )

    # ========================================
    # 导出 / Export
    # ========================================

    async def export_conversation(
        self,
        conversation_id: int,
        export_format: str = "json",
    ) -> dict[str, Any]:
        """
        导出对话数据 / Export conversation data.

        使用分批加载获取全部消息，避免静默截断。

        Args:
            conversation_id: 对话 ID
            export_format: 导出格式 (json / markdown)

        Returns:
            包含 content、filename、total_message_count 的字典
        """
        conversation = await self.repo.get_by_id(conversation_id)
        if not conversation:
            raise NotFoundException(message=_("conversation.not_found"))
        return await self.export_runtime_service.export_conversation(
            conversation=conversation,
            export_format=export_format,
        )

    @staticmethod
    def _to_json(
        conversation: AgentConversation,
        messages: list,
    ) -> str:
        return ConversationExportService.to_json(conversation, messages)

    @staticmethod
    def _to_markdown(
        conversation: AgentConversation,
        messages: list,
    ) -> str:
        return ConversationExportService.to_markdown(conversation, messages)

    # ========================================
    # Chat execution helpers (from AgentChatService) / 对话执行辅助（从 AgentChatService 提取）
    # ========================================

    # Max history messages to load (fallback default) / 历史消息最大条数（兜底默认）
    MAX_HISTORY_MESSAGES = 50
    # Max history tokens (0 = unlimited) / 历史消息最大 Token（0=不限制）
    MAX_HISTORY_TOKENS = 0
    # 对话标题最大长度 / Max conversation title length
    MAX_TITLE_LENGTH = 100

    async def get_or_create_for_chat(
        self,
        agent_id: int,
        conversation_id: int | None,
        user_id: int | None,
        owner_type: str,
        first_message: str,
    ) -> AgentConversation:
        """
        获取或创建对话（用于对话执行）/ Get or create conversation (for chat execution).

        Args:
            agent_id: 智能体 ID
            conversation_id: 已有对话 ID（续接时传入）
            user_id: 用户 ID
            first_message: 首条消息（用于生成标题）

        Returns:
            AgentConversation 实例

        Raises:
            NotFoundException: 对话不存在
            BusinessException: 对话已归档
        """
        return await self.chat_lifecycle_service.get_or_create_for_chat(
            agent_id=agent_id,
            conversation_id=conversation_id,
            user_id=user_id,
            owner_type=owner_type,
            first_message=first_message,
        )

    async def load_chat_history(
        self,
        conversation_id: int,
        max_messages: int = 0,
        max_tokens: int = 0,
    ) -> list[ChatMessage]:
        """
        从 ConversationMessage 加载历史消息并转换为 ChatMessage / Load history from ConversationMessage and convert to ChatMessage.

        支持两级截断：
        1. max_messages: 最多保留最近 N 条消息
        2. max_tokens: 历史消息总 token 不超过 N（从最旧开始移除）

        Args:
            conversation_id: 对话 ID
            max_messages: 最大消息条数（0 = 使用默认值）
            max_tokens: 最大 token 数（0 = 不限制）

        Returns:
            ChatMessage 列表（不含 system 消息，由引擎构建）
        """
        return await self.history_service.load_chat_history(
            conversation_id=conversation_id,
            max_messages=max_messages,
            max_tokens=max_tokens,
        )

    @staticmethod
    def sanitize_tool_messages(
        messages: list[ChatMessage],
    ) -> list[ChatMessage]:
        return ConversationMessagePersistenceService.sanitize_tool_messages(messages)

    @staticmethod
    def _copy_metadata(raw: Any) -> dict[str, Any] | None:
        return ConversationService._normalize_json_safe_dict(raw)

    @staticmethod
    def _normalize_json_safe(value: Any) -> Any:
        return normalize_json_safe(value)

    @staticmethod
    def _normalize_json_safe_dict(raw: Any) -> dict[str, Any] | None:
        return normalize_json_safe_dict(raw)

    @staticmethod
    def _normalize_turn_record_payload(turn_record: Any) -> dict[str, Any] | None:
        """Normalize runtime turn_record into JSON-safe dict / 将运行时 turn_record 规范化为可落库字典。"""
        return ConversationDiagnosticsProjector.normalize_turn_record_payload(
            turn_record
        )

    @staticmethod
    def _to_non_empty_str(value: Any) -> str | None:
        return ConversationDiagnosticsProjector.to_non_empty_str(value)

    @staticmethod
    def _normalize_string_list(value: Any) -> list[str]:
        return ConversationDiagnosticsProjector.normalize_string_list(value)

    @staticmethod
    def _normalize_context_sources(value: Any) -> list[dict[str, Any]]:
        return ConversationDiagnosticsProjector.normalize_context_sources(value)

    @staticmethod
    def _normalize_json_dict(value: Any) -> dict[str, Any] | None:
        return ConversationDiagnosticsProjector.normalize_json_dict(value)

    @classmethod
    def _normalize_intent_plan(cls, value: Any) -> list[dict[str, Any]]:
        return ConversationDiagnosticsProjector.normalize_intent_plan(value)

    @classmethod
    def _normalize_retry_events(cls, value: Any) -> list[dict[str, Any]]:
        return ConversationDiagnosticsProjector.normalize_retry_events(value)

    @classmethod
    def _normalize_provider_events(cls, value: Any) -> list[dict[str, Any]]:
        return ConversationDiagnosticsProjector.normalize_provider_events(value)

    @classmethod
    def _extract_turn_diagnostics_from_metadata(
        cls,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        return ConversationRuntimeProjectionService.extract_turn_diagnostics_from_metadata(
            metadata
        )

    async def persist_chat_messages(
        self,
        conversation: AgentConversation,
        result: ExecutionResult,
        history_count: int,
        agent_id: int | None = None,
        route_source: str | None = None,
        *,
        context_diagnostics: dict[str, Any] | None = None,
        last_run_summary: dict[str, Any] | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        """
        将执行过程中产生的新消息持久化为 ConversationMessage / Persist new messages from execution as ConversationMessage.

        ExecutionResult.messages 结构:
        [system, ...history..., new_user, (assistant+tool_calls, tool, ...,)* final_assistant]

        持久化 new_user 及之后的所有消息（跳过 system 和 history）。

        Args:
            conversation: 对话实例
            result: 执行结果
            history_count: 历史消息数量（用于计算新消息起始位置）
            agent_id: 智能体 ID（写入 assistant/tool 消息，支持多智能体对话追溯）
            route_source: 前端路由来源标记（如 mention）

        Returns:
            收集到的 tool_calls 与实际持久化的消息数量（用于响应和错误兜底判断）
            / Collected tool_calls plus the number of messages actually persisted.
        """
        return await ConversationMessagePersistenceService.persist_chat_messages(
            self,
            conversation=conversation,
            result=result,
            history_count=history_count,
            agent_id=agent_id,
            route_source=route_source,
            context_diagnostics=context_diagnostics,
            last_run_summary=last_run_summary,
        )

    async def persist_user_messages(
        self,
        *,
        conversation: AgentConversation,
        messages: list[ChatMessage],
    ) -> int:
        return await ConversationMessagePersistenceService.persist_user_messages(
            self,
            conversation=conversation,
            messages=messages,
        )

    async def mark_memory_updated(self, conversation_id: int) -> None:
        """
        标记最后一条 assistant 消息的 metadata 中 memory_updated = true / Mark last assistant message memory_updated in metadata.

        在 _persist_session_memory 成功后调用，用于前端加载历史时恢复记忆标记。
        """
        await ConversationMessagePersistenceService.mark_memory_updated(
            self,
            conversation_id,
        )

    async def get_messages_for_conversation(
        self,
        conversation_id: int,
    ) -> list[Any]:
        return await self.message_repo.get_by_conversation(conversation_id)

    async def get_context_compaction_snapshot(
        self,
        conversation_id: int,
    ) -> dict[str, Any] | None:
        return await ConversationMessagePersistenceService.get_context_compaction_snapshot(
            self,
            conversation_id,
            metadata_key=_CONTEXT_COMPACTION_METADATA_KEY,
        )

    async def upsert_context_compaction_snapshot(
        self,
        conversation_id: int,
        *,
        summary: str,
        source_message_count: int,
        source_token_estimate: int,
    ) -> dict[str, Any] | None:
        return await ConversationMessagePersistenceService.upsert_context_compaction_snapshot(
            self,
            conversation_id,
            metadata_key=_CONTEXT_COMPACTION_METADATA_KEY,
            summary=summary,
            source_message_count=source_message_count,
            source_token_estimate=source_token_estimate,
        )

    async def update_stats(
        self,
        conversation: AgentConversation,
        result: ExecutionResult,
        current_agent: Agent | None = None,
    ) -> None:
        """
        更新对话统计信息，并尝试提取输出变量 / Update conversation stats and try to extract output variables.

        Args:
            conversation: 对话实例
            result: 执行结果
        """
        await self.stats_service.update_stats(
            conversation=conversation,
            result=result,
            current_agent=current_agent,
        )

    async def persist_stream_completion(
        self,
        *,
        conversation_id: int,
        result: ExecutionResult,
        history_count: int,
        agent_id: int | None = None,
        route_source: str | None = None,
        context_diagnostics: dict[str, Any] | None = None,
        last_run_summary: dict[str, Any] | None = None,
        current_agent: Agent | None = None,
    ) -> int:
        return await self.stream_persistence_service.persist_stream_completion(
            conversation_id=conversation_id,
            result=result,
            history_count=history_count,
            agent_id=agent_id,
            route_source=route_source,
            context_diagnostics=context_diagnostics,
            last_run_summary=last_run_summary,
            current_agent=current_agent,
        )

    async def persist_stream_last_error_marker(
        self,
        *,
        conversation_id: int,
        error_type: str,
        error_message: str,
        friendly_message: str,
        partial: bool,
        extra_payload: dict[str, Any] | None = None,
    ) -> bool:
        return await self.stream_persistence_service.persist_stream_last_error_marker(
            conversation_id=conversation_id,
            error_type=error_type,
            error_message=error_message,
            friendly_message=friendly_message,
            partial=partial,
            extra_payload=extra_payload,
        )

    async def save_stream_error_message(
        self,
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
        return await self.stream_persistence_service.save_stream_error_message(
            conversation_id=conversation_id,
            tenant_id=self.tenant_id,
            agent_id=agent_id,
            error_text=error_text,
            user_message=user_message,
            result=result,
            context_diagnostics_payload=context_diagnostics_payload,
            last_run_summary_payload=last_run_summary_payload,
            persist_user_message=persist_user_message,
            build_stream_error_display=build_stream_error_display,
        )


__all__ = ["ConversationService"]

