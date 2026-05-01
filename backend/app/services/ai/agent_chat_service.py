"""
智能体对话执行 Service / Agent Chat Service

编排完整对话流程：创建/续接对话 → 加载历史 → 调 ExecutionDispatcher → 持久化消息
Orchestrates full chat flow: create/resume conversation → load history → call ExecutionDispatcher → persist messages.
"""

from typing import TYPE_CHECKING, Any

from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.agent_quota import (  # noqa: F401
    AgentConcurrencyLimiter,
    AgentQuotaConfig,
    AgentQuotaManager,
)
from app.ai.agent_stats import AgentStatsManager  # noqa: F401
from app.ai.constants import (
    DEFAULT_MEMORY_SCENE,
    MEMORY_CHANNEL_SYSTEM,
)
from app.ai.engine.base import BaseEngine  # noqa: F401
from app.ai.engine.conversation import ConversationEngine
from app.ai.engine.dispatcher import ExecutionDispatcher  # noqa: F401
from app.ai.engine.types import ExecutionRequest, ExecutionResult
from app.ai.events.hooks import HookPoint, get_hook_registry  # noqa: F401
from app.core.database import async_session_factory  # noqa: F401
from app.core.logging import LogManager
from app.enums.common import UserRoleEnum
from app.schemas.ai.agent_chat import AgentChatResponse, InteractionMode
from app.services.ai.agent_chat_command_service import AgentChatCommandService
from app.services.ai.agent_chat_error_surface import (
    build_stream_error_display,
    friendly_stream_error_detail,
    friendly_stream_error_text,
    strip_stream_error_trace,
)
from app.services.ai.agent_chat_interaction_mode_manager import (
    AgentChatInteractionModeManager,
)
from app.services.ai.agent_chat_query_service import AgentChatQueryService
from app.services.ai.agent_chat_runtime_support import AgentChatRuntimeSupport
from app.services.ai.agent_chat_stream_bootstrap_service import (
    AgentChatStreamBootstrapService,
)
from app.services.ai.agent_chat_stream_support import AgentChatStreamSupport
from app.services.ai.agent_chat_turn_orchestrator import AgentChatTurnOrchestrator
from app.services.ai.agent_chat_turn_projection_service import (
    AgentChatTurnProjectionService,
)
from app.services.ai.conversation_service import ConversationService
from app.services.ai.execution_trust_policy_service import (
    ExecutionTrustPolicyService,
)
from app.services.ai.long_term_memory_provider import get_long_term_memory_provider
from app.services.ai.session_memory_service import SessionMemoryService

if TYPE_CHECKING:
    from app.models.ai.agent import Agent

logger = LogManager.get_logger("ai.agent_chat_service")


class AgentChatService:
    """
    智能体对话执行 Service / Agent chat execution service.

    职责：
    1. 创建或续接对话（AgentConversation）
    2. 从 ConversationMessage 加载历史消息
    3. 将历史 + 新消息转换为 ChatMessage 列表
    4. 调用 ExecutionDispatcher 完成推理
    5. 将新消息持久化为 ConversationMessage
    6. 更新对话统计信息

    注意：本 Service 不继承 TenantService，因为它不管理单一 CRUD 模型，
    而是编排多个 Repository 和 Engine 完成对话执行。
    """

    def __init__(self, db: AsyncSession, tenant_id: int):
        """
        初始化 / Initialize.

        Args:
            db: 异步数据库会话
            tenant_id: 企业 ID
        """
        self.db = db
        self.tenant_id = tenant_id
        self.conversation_svc = ConversationService(db, tenant_id)
        self.query_service = AgentChatQueryService(db, tenant_id)
        self.runtime_support = AgentChatRuntimeSupport(db, tenant_id)
        self.stream_bootstrap = AgentChatStreamBootstrapService(
            db,
            tenant_id,
            conversation_engine_factory=lambda **kwargs: ConversationEngine(**kwargs),
        )
        interaction_mode_manager = AgentChatInteractionModeManager(self.runtime_support)
        self._interaction_mode_manager = interaction_mode_manager
        self.turn_orchestrator = AgentChatTurnOrchestrator(
            conversation_service=self.conversation_svc,
            interaction_mode_manager=interaction_mode_manager,
            build_memory_event_id=self._build_memory_event_id,
        )
        self.stream_support = AgentChatStreamSupport()

    # ========================================
    # Internal: Agent validation / 内部：Agent 校验
    # ========================================

    async def _validate_agent(self, agent_id: int) -> "Agent":
        """
        加载并校验 Agent（存在性 + 已发布状态）。 / Load and validate agent (existence + published).

        Args:
            agent_id: 智能体 ID

        Returns:
            Agent 实例

        Raises:
            NotFoundException: 智能体不存在
            BusinessException: 智能体未发布
        """
        return await self.query_service.validate_agent(agent_id)

    async def _build_billing_context(
        self,
        *,
        agent: "Agent",
        user_id: int | None,
        user_role: str,
        user_role_id: int | None = None,
    ) -> dict[str, Any]:
        return await self.runtime_support.build_billing_context(
            agent=agent,
            user_id=user_id,
            user_role=user_role,
            user_role_id=user_role_id,
        )

    async def _extract_memory_delta(
        self,
        message: str,
        response: str,
        agent_id: int,
    ) -> dict[str, list[str]]:
        return await self.runtime_support.extract_memory_delta(
            message=message,
            response=response,
            agent_id=agent_id,
        )

    async def _load_session_memory_context(
        self,
        *,
        request: ExecutionRequest,
    ) -> str:
        return await self.runtime_support.load_session_memory_context(
            request=request,
            session_memory_service_cls=SessionMemoryService,
        )

    async def _persist_session_memory(
        self,
        *,
        request: ExecutionRequest,
        message: str,
        response: str,
        event_id: str,
    ) -> dict[str, list[str]] | None:
        return await self.runtime_support.persist_session_memory(
            request=request,
            message=message,
            response=response,
            event_id=event_id,
            extract_memory_delta_fn=self._extract_memory_delta,
            session_memory_service_cls=SessionMemoryService,
            long_term_memory_provider_factory=get_long_term_memory_provider,
        )

    @staticmethod
    def _build_memory_event_id(conversation_id: int) -> str:
        return AgentChatRuntimeSupport.build_memory_event_id(conversation_id)

    @staticmethod
    def _resolve_memory_context(
        memory_scene: str,
        memory_channel: str,
        memory_source: str,
    ) -> tuple[str, str, str, bool]:
        return AgentChatRuntimeSupport.resolve_memory_context(
            memory_scene=memory_scene,
            memory_channel=memory_channel,
            memory_source=memory_source,
        )

    async def _resolve_effective_memory_enabled(
        self,
        *,
        agent_id: int,
        scene: str,
        scene_enabled: bool,
    ) -> bool:
        return await self.runtime_support.resolve_effective_memory_enabled(
            agent_id=agent_id,
            scene=scene,
            scene_enabled=scene_enabled,
        )

    async def _resolve_runtime_trust_policy_ref(
        self,
        *,
        conversation_id: int | None,
        agent_id: int,
        operator_id: int | None,
        operator_type: str | None,
        explicit_ref: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        return await self.runtime_support.resolve_runtime_trust_policy_ref(
            conversation_id=conversation_id,
            agent_id=agent_id,
            operator_id=operator_id,
            operator_type=operator_type,
            explicit_ref=explicit_ref,
            trust_policy_service_cls=ExecutionTrustPolicyService,
        )

    async def _resolve_interaction_mode(
        self,
        *,
        requested_mode: str | None,
        conversation_id: int | None,
        agent_id: int,
        operator_id: int | None,
        operator_type: str | None,
        explicit_trust_policy_ref: dict[str, Any] | None = None,
        interaction_updates: list[dict[str, Any]] | None = None,
    ) -> tuple[InteractionMode, dict[str, Any] | None, str | None]:
        outcome = await self._interaction_mode_manager.resolve_mode(
            requested_mode=requested_mode,
            conversation_id=conversation_id,
            agent_id=agent_id,
            operator_id=operator_id,
            operator_type=operator_type,
            explicit_trust_policy_ref=explicit_trust_policy_ref,
            interaction_updates=interaction_updates,
        )
        return (
            outcome.effective_mode,
            outcome.trust_policy_ref,
            outcome.downgrade_reason,
        )

    @staticmethod
    def _friendly_stream_error_text(
        error: Any,
        *,
        failure_kind: str | None = None,
    ) -> str:
        return friendly_stream_error_text(error, failure_kind=failure_kind)

    @staticmethod
    def _strip_stream_error_trace(error: Any) -> str:
        return strip_stream_error_trace(error)

    @staticmethod
    def _friendly_stream_error_detail(
        error: Any,
        *,
        failure_kind: str | None = None,
    ) -> str | None:
        return friendly_stream_error_detail(error, failure_kind=failure_kind)

    @classmethod
    def _build_stream_error_display(
        cls,
        error: Any,
        *,
        failure_kind: str | None = None,
    ) -> dict[str, Any]:
        del cls
        return build_stream_error_display(error, failure_kind=failure_kind)

    @staticmethod
    def _build_context_diagnostics(
        result: ExecutionResult,
        *,
        interaction_mode_effective: str,
    ) -> dict[str, Any]:
        return AgentChatTurnProjectionService.build_context_diagnostics(
            result,
            interaction_mode_effective=interaction_mode_effective,
        )

    @staticmethod
    def _build_last_run_summary(
        result: ExecutionResult,
        *,
        interaction_mode_effective: str,
        downgrade_reason: str | None,
    ) -> dict[str, Any]:
        return AgentChatTurnProjectionService.build_last_run_summary(
            result,
            interaction_mode_effective=interaction_mode_effective,
            downgrade_reason=downgrade_reason,
        )

    # ========================================
    # Non-streaming chat / 非流式对话
    # ========================================

    async def chat(
        self,
        agent_id: int,
        message: str,
        conversation_id: int | None = None,
        variables: dict[str, Any] | None = None,
        user_id: int | None = None,
        knowledge_base_ids: list[int] | None = None,
        user_role: str = UserRoleEnum.TENANT_ADMIN.value,
        user_role_id: int | None = None,
        permissions: set[str] | None = None,
        consented_actions: list[str] | None = None,
        attachments: list[dict[str, Any]] | None = None,
        memory_scene: str = DEFAULT_MEMORY_SCENE,
        memory_channel: str = MEMORY_CHANNEL_SYSTEM,
        memory_source: str = "",
        selected_skill_names: list[str] | None = None,
        interaction_updates: list[dict[str, Any]] | None = None,
        trust_policy_ref: dict[str, Any] | None = None,
        interaction_mode: InteractionMode = "trusted_auto",
    ) -> AgentChatResponse:
        return await AgentChatCommandService.chat(
            self,
            agent_id=agent_id,
            message=message,
            conversation_id=conversation_id,
            variables=variables,
            user_id=user_id,
            knowledge_base_ids=knowledge_base_ids,
            user_role=user_role,
            user_role_id=user_role_id,
            permissions=permissions,
            consented_actions=consented_actions,
            attachments=attachments,
            memory_scene=memory_scene,
            memory_channel=memory_channel,
            memory_source=memory_source,
            selected_skill_names=selected_skill_names,
            interaction_updates=interaction_updates,
            trust_policy_ref=trust_policy_ref,
            interaction_mode=interaction_mode,
        )

    # ========================================
    # Streaming chat (M16-T3-2) / 流式对话
    # ========================================

    async def stream_chat(
        self,
        agent_id: int,
        message: str = "",
        messages: list[str] | None = None,
        conversation_id: int | None = None,
        variables: dict[str, Any] | None = None,
        user_id: int | None = None,
        knowledge_base_ids: list[int] | None = None,
        user_role: str = UserRoleEnum.TENANT_ADMIN.value,
        user_role_id: int | None = None,
        permissions: set[str] | None = None,
        consented_actions: list[str] | None = None,
        attachments: list[dict[str, Any]] | None = None,
        image_params: dict[str, Any] | None = None,
        memory_scene: str = DEFAULT_MEMORY_SCENE,
        memory_channel: str = MEMORY_CHANNEL_SYSTEM,
        memory_source: str = "",
        selected_skill_names: list[str] | None = None,
        interaction_updates: list[dict[str, Any]] | None = None,
        trust_policy_ref: dict[str, Any] | None = None,
        interaction_mode: InteractionMode = "trusted_auto",
    ) -> StreamingResponse:
        return await AgentChatCommandService.stream_chat(
            self,
            agent_id=agent_id,
            message=message,
            messages=messages,
            conversation_id=conversation_id,
            variables=variables,
            user_id=user_id,
            knowledge_base_ids=knowledge_base_ids,
            user_role=user_role,
            user_role_id=user_role_id,
            permissions=permissions,
            consented_actions=consented_actions,
            attachments=attachments,
            image_params=image_params,
            memory_scene=memory_scene,
            memory_channel=memory_channel,
            memory_source=memory_source,
            selected_skill_names=selected_skill_names,
            interaction_updates=interaction_updates,
            trust_policy_ref=trust_policy_ref,
            interaction_mode=interaction_mode,
        )

    # ========================================
    # Lightweight streaming (no conversation record) / 轻量级流式（无对话记录）
    # ========================================

    async def stream_chat_ephemeral(
        self,
        agent_id: int,
        message: str,
        variables: dict[str, Any] | None = None,
        user_id: int | None = None,
        knowledge_base_ids: list[int] | None = None,
        user_role: str = UserRoleEnum.TENANT_ADMIN.value,
        user_role_id: int | None = None,
        permissions: set[str] | None = None,
    ) -> StreamingResponse:
        return await AgentChatCommandService.stream_chat_ephemeral(
            self,
            agent_id=agent_id,
            message=message,
            variables=variables,
            user_id=user_id,
            knowledge_base_ids=knowledge_base_ids,
            user_role=user_role,
            user_role_id=user_role_id,
            permissions=permissions,
        )


__all__ = ["AgentChatService"]
