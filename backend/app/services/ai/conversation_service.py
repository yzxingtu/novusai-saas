"""
对话数据生命周期管理 Service / Conversation Lifecycle Service

提供对话列表、详情、搜索、归档、删除和导出
Provides conversation list, detail, search, archive, delete and export.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.configs.service import PLATFORM_TENANT_ID
from app.core.base_service import TenantService
from app.core.i18n import _
from app.core.logging import LogManager
from app.enums.agent import (
    ConversationOwnerTypeEnum,
    ConversationStatusEnum,
)
from app.exceptions import BusinessException, NotFoundException
from app.models.ai.agent_conversation import AgentConversation
from app.repositories.ai.agent_conversation_repository import (
    AdminAgentConversationRepository,
    AgentConversationRepository,
)
from app.services.ai.conversation_facade_mixins import (
    ConversationDependencyFacade,
    ConversationDiagnosticsFacade,
    ConversationExportFacade,
    ConversationHistoryFacade,
    ConversationPersistenceFacade,
)
from app.services.ai.conversation_read_model_service import (
    ConversationReadModelService,
)

logger = LogManager.get_logger("ai.conversation_service")
_CONTEXT_COMPACTION_METADATA_KEY = "context_compaction"


class ConversationService(
    ConversationDependencyFacade,
    ConversationDiagnosticsFacade,
    ConversationExportFacade,
    ConversationHistoryFacade,
    ConversationPersistenceFacade,
    TenantService[AgentConversation, AgentConversationRepository],
):
    """
    对话数据生命周期管理 Service / Conversation lifecycle service.

    提供对话列表、详情、搜索、归档、删除和导出
    """

    model = AgentConversation
    repository_class = AgentConversationRepository
    CONTEXT_COMPACTION_METADATA_KEY = _CONTEXT_COMPACTION_METADATA_KEY

    @staticmethod
    def _format_dt(dt: datetime | None) -> str | None:
        return ConversationReadModelService.format_dt(dt)

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
        conversation = await self.get_accessible_conversation(
            conversation_id,
            user_id=user_id,
            owner_type=owner_type,
        )
        state = await self.memory_state_service.get_state(conversation_id)
        return await self._attach_long_term_memory_preview(state, conversation)

    async def _attach_long_term_memory_preview(
        self,
        state: dict[str, Any],
        conversation: AgentConversation,
    ) -> dict[str, Any]:
        agent_id = int(getattr(conversation, "agent_id", 0) or 0)
        conversation_user_id = int(getattr(conversation, "user_id", 0) or 0)
        if not agent_id or not conversation_user_id:
            return state
        if not isinstance(getattr(self, "db", None), AsyncSession):
            return state

        try:
            from app.enums.memory import MemoryScopeTypeEnum
            from app.repositories.ai.memory_record_repository import (
                MemoryRecordRepository,
            )
            from app.services.ai.long_term_memory_service import (
                LongTermMemoryService,
            )

            scope_type = MemoryScopeTypeEnum.USER_AGENT.value
            scope_key = LongTermMemoryService.build_scope_key(
                scope_type,
                agent_id=agent_id,
                user_id=conversation_user_id,
            )
            records = await MemoryRecordRepository(
                self.db,
                self._get_memory_tenant_id(),
            ).list_for_scope(
                scope_type=scope_type,
                scope_key=scope_key,
                limit=12,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Long-term memory preview degraded: conversation={} err={}",
                getattr(conversation, "id", None),
                str(exc),
            )
            return state

        summaries: list[str] = []
        for record in records:
            text = str(
                getattr(record, "summary", None)
                or getattr(record, "content", None)
                or ""
            ).strip()
            if text and text not in summaries:
                summaries.append(text)

        if summaries:
            state = dict(state)
            state["long_term_memories"] = summaries
            state["long_term_memory_count"] = len(records)
        return state

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
        return await self.memory_state_service.clear_state(conversation_id)

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
        await self.memory_state_service.clear_state_safe(
            conversation_id=conversation_id,
            tenant_id=self.tenant_id,
            logger=logger,
            log_message=(
                "Conversation memory cleanup failed: conversation={} tenant={} err={}"
            ),
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
            await self.memory_state_service.clear_state(id)
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

    # ========================================
    # Chat execution helpers (from AgentChatService) / 对话执行辅助（从 AgentChatService 提取）
    # ========================================

    # Max history messages to load (fallback default) / 历史消息最大条数（兜底默认）
    MAX_HISTORY_MESSAGES = 50
    # Default runtime history token budget when the agent leaves it unspecified.
    # Explicit max_tokens=0 still means unlimited for maintenance flows.
    MAX_HISTORY_TOKENS = 2400
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


__all__ = ["ConversationService"]
