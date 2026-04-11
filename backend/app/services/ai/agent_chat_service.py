"""
智能体对话执行 Service / Agent Chat Service

编排完整对话流程：创建/续接对话 → 加载历史 → 调 ExecutionDispatcher → 持久化消息
Orchestrates full chat flow: create/resume conversation → load history → call ExecutionDispatcher → persist messages.
"""

import time
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.agent_quota import (
    AgentConcurrencyLimiter,
    AgentQuotaConfig,
    AgentQuotaManager,
)
from app.ai.agent_stats import AgentStatsManager
from app.ai.constants import (
    DEFAULT_MEMORY_SCENE,
    MEMORY_CHANNEL_SYSTEM,
)
from app.ai.context.long_term_memory import get_long_term_memory_provider
from app.ai.engine.base import BaseEngine
from app.ai.engine.conversation import ConversationEngine
from app.ai.engine.dispatcher import ExecutionDispatcher
from app.ai.engine.types import ExecutionRequest, ExecutionResult
from app.ai.events.hooks import HookPoint, get_hook_registry
from app.ai.types import ChatMessage
from app.ai.utils.token_estimator import estimate_tokens
from app.configs.service import PLATFORM_TENANT_ID
from app.core.database import async_session_factory
from app.core.i18n import _
from app.core.logging import LogManager
from app.enums.agent import (
    AgentExecutionModeEnum,
    AgentStatusEnum,
)
from app.enums.common import UserRoleEnum
from app.exceptions import BusinessException, NotFoundException
from app.repositories.ai.agent_repository import AgentRepository
from app.schemas.ai.agent_chat import AgentChatResponse, InteractionMode, PageContext
from app.services.ai.agent_chat_conversation_turn_service import (
    AgentChatConversationTurnService,
    PreparedConversationTurn,
)
from app.services.ai.agent_chat_error_surface import (
    build_stream_error_display,
    friendly_stream_error_detail,
    friendly_stream_error_text,
    strip_stream_error_trace,
)
from app.services.ai.agent_chat_interaction_mode_manager import (
    AgentChatInteractionModeManager,
)
from app.services.ai.agent_chat_runtime_support import AgentChatRuntimeSupport
from app.services.ai.agent_chat_stream_bootstrap_service import (
    AgentChatStreamBootstrapService,
)
from app.services.ai.agent_chat_stream_persistence_orchestrator import (
    AgentChatStreamPersistenceOrchestrator,
)
from app.services.ai.agent_chat_stream_runtime_dependencies import (
    AgentChatStreamPersistenceDependencies,
)
from app.services.ai.agent_chat_turn_projection_service import (
    AgentChatTurnProjectionBundle,
    AgentChatTurnProjectionService,
)
from app.services.ai.conversation_service import ConversationService
from app.services.ai.execution_trust_policy_service import (
    ExecutionTrustPolicyService,
)
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
        self.runtime_support = AgentChatRuntimeSupport(db, tenant_id)
        self.stream_bootstrap = AgentChatStreamBootstrapService(
            db,
            tenant_id,
            conversation_engine_factory=lambda **kwargs: ConversationEngine(**kwargs),
        )
        self._conversation_turn_service = AgentChatConversationTurnService()
        self._interaction_mode_manager = AgentChatInteractionModeManager(
            self.runtime_support
        )
        self._turn_projection_service = AgentChatTurnProjectionService()

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
        if self.tenant_id == PLATFORM_TENANT_ID:
            from app.repositories.ai.agent_repository import AdminAgentRepository

            agent_repo = AdminAgentRepository(self.db)
        else:
            agent_repo = AgentRepository(self.db, self.tenant_id)
        agent = await agent_repo.get_by_id(agent_id)
        if not agent:
            raise NotFoundException(message=_("agent.error.not_found"))
        if agent.status != AgentStatusEnum.PUBLISHED.value:
            raise BusinessException(message=_("agent.error.not_published"))
        return agent

    async def _sanitize_client_knowledge_base_ids(
        self,
        agent_id: int,
        knowledge_base_ids: list[int] | None,
    ) -> tuple[list[int] | None, list[int]]:
        """
        Keep only KB ids bound to the agent (tenant-scoped bindings). None => no narrowing.
        仅保留已绑定到智能体的知识库 ID；None 表示不按客户端列表收窄。
        """
        if not knowledge_base_ids:
            return None, []
        from app.ai.rag_injector import load_agent_kb_bindings

        bound_ids, _ = await load_agent_kb_bindings(self.db, agent_id, self.tenant_id)
        allowed = set(bound_ids or [])
        filtered = [x for x in knowledge_base_ids if x in allowed]
        dropped = [x for x in knowledge_base_ids if x not in allowed]
        if dropped:
            logger.warning(
                "Dropped knowledge_base_ids not bound to agent_id={}: {}",
                agent_id,
                dropped,
            )
        return filtered or None, dropped

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
        return outcome.effective_mode, outcome.trust_policy_ref, outcome.downgrade_reason

    async def _grant_trusted_auto_policies(
        self,
        *,
        conversation_id: int,
        agent_id: int,
        operator_id: int | None,
        operator_type: str | None,
        interaction_updates: list[dict[str, Any]] | None,
        interaction_mode: str,
    ) -> None:
        await self._interaction_mode_manager.grant_trusted_auto_policies(
            conversation_id=conversation_id,
            agent_id=agent_id,
            operator_id=operator_id,
            operator_type=operator_type,
            interaction_updates=interaction_updates,
            interaction_mode=interaction_mode,
        )

    async def _apply_conversation_interaction_state(
        self,
        *,
        conversation: Any,
        agent_id: int,
        user_id: int | None,
        conversation_owner_type: str,
        requested_mode: str | None,
        interaction_mode_effective: str,
        interaction_mode_downgrade_reason: str | None,
        interaction_updates: list[dict[str, Any]] | None,
    ) -> list[dict[str, Any]] | None:
        return await self._conversation_turn_service.apply_interaction_state(
            conversation=conversation,
            agent_id=agent_id,
            user_id=user_id,
            conversation_owner_type=conversation_owner_type,
            requested_mode=requested_mode,
            interaction_mode_effective=interaction_mode_effective,
            interaction_mode_downgrade_reason=interaction_mode_downgrade_reason,
            interaction_updates=interaction_updates,
            conversation_service=self.conversation_svc,
            interaction_mode_manager=self._interaction_mode_manager,
            grant_trusted_auto_policies=self._grant_trusted_auto_policies,
        )

    async def _prepare_conversation_turn(
        self,
        *,
        agent_id: int,
        conversation_id: int | None,
        message: str,
        user_id: int | None,
        user_role: str,
        interaction_mode: str | None,
        interaction_updates: list[dict[str, Any]] | None,
        trust_policy_ref: dict[str, Any] | None,
    ) -> PreparedConversationTurn:
        return await self._conversation_turn_service.prepare_conversation_turn(
            agent_id=agent_id,
            conversation_id=conversation_id,
            user_id=user_id,
            user_role=user_role,
            first_message=message,
            requested_mode=interaction_mode,
            interaction_updates=interaction_updates,
            trust_policy_ref=trust_policy_ref,
            resolve_interaction_mode=self._resolve_interaction_mode,
            apply_interaction_state=self._apply_conversation_interaction_state,
            build_memory_event_id=self._build_memory_event_id,
            conversation_service=self.conversation_svc,
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
    def _assistant_message_has_visible_reply_payload(message: dict[str, Any]) -> bool:
        if not isinstance(message, dict):
            return False
        if str(message.get("role") or "").strip() != "assistant":
            return False
        if str(message.get("content") or "").strip():
            return True
        metadata = message.get("metadata")
        if not isinstance(metadata, dict):
            return False
        if metadata.get("error") is True:
            return True
        if isinstance(metadata.get("pending_confirmation"), dict) or isinstance(
            metadata.get("pending_consent"), dict
        ):
            return True
        action_buttons = metadata.get("action_buttons")
        return isinstance(action_buttons, list) and len(action_buttons) > 0

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

    def _bind_turn_projector(
        self,
        *,
        interaction_mode_effective: str,
        downgrade_reason: str | None,
    ):
        return self._turn_projection_service.bind(
            context_diagnostics_builder=lambda result: self._build_context_diagnostics(
                result,
                interaction_mode_effective=interaction_mode_effective,
            ),
            last_run_summary_builder=lambda result: self._build_last_run_summary(
                result,
                interaction_mode_effective=interaction_mode_effective,
                downgrade_reason=downgrade_reason,
            ),
        )

    def _build_turn_projection_bundle(
        self,
        result: ExecutionResult,
        *,
        interaction_mode_effective: str,
        downgrade_reason: str | None,
    ) -> AgentChatTurnProjectionBundle:
        return self._bind_turn_projector(
            interaction_mode_effective=interaction_mode_effective,
            downgrade_reason=downgrade_reason,
        ).build(result)

    @staticmethod
    def _stream_persistence_runtime_dependencies() -> AgentChatStreamPersistenceDependencies:
        """Late-bind patchable dependencies for stream on_complete persistence."""
        return AgentChatStreamPersistenceDependencies(
            session_factory=async_session_factory,
            conversation_service_cls=ConversationService,
            adjust_usage=AgentQuotaManager.adjust_usage,
            record_user_usage=AgentQuotaManager.record_user_usage,
            record_chat_stats=AgentStatsManager.record_chat,
            release_concurrency=AgentConcurrencyLimiter.release,
            publish_execution_completed=BaseEngine._publish_execution_completed,
            publish_execution_failed=BaseEngine._publish_execution_failed,
        )

    def _build_stream_runtime_dependencies(self) -> AgentChatStreamPersistenceDependencies:
        dependencies = self._stream_persistence_runtime_dependencies()
        if isinstance(dependencies, AgentChatStreamPersistenceDependencies):
            return dependencies
        if isinstance(dependencies, Mapping):
            return AgentChatStreamPersistenceDependencies.from_mapping(dependencies)  # type: ignore[arg-type]
        raise TypeError(
            "Stream persistence dependencies must be a mapping or AgentChatStreamPersistenceDependencies"
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
        page_context: PageContext | dict[str, Any] | None = None,
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
        page_session_id: str | None = None,
        route_source: str | None = None,
        interaction_updates: list[dict[str, Any]] | None = None,
        trust_policy_ref: dict[str, Any] | None = None,
        interaction_mode: InteractionMode = "confirm",
    ) -> AgentChatResponse:
        """
        非流式对话 / Non-streaming chat.

        完整流程：
        校验 Agent → 获取/创建对话 → 加载历史 → 构建消息 → 调 dispatcher → 持久化 → 返回

        Args:
            agent_id: 智能体 ID
            message: 用户消息
            conversation_id: 对话 ID（续接时传入）
            variables: 输入变量（注入到 system_prompt 占位符）
            user_id: 用户 ID
            user_role: 用户角色（platform_admin / tenant_admin / tenant_user）
            permissions: 用户 RBAC 权限码集合

        Returns:
            AgentChatResponse

        Raises:
            NotFoundException: 智能体或对话不存在
            BusinessException: 智能体未发布、对话已归档、执行失败
        """
        start = time.perf_counter()
        variables = PageContext.normalize_variables(variables, page_context)

        # 0. Load and validate Agent (must be published) / 0. 加载并校验 Agent（须已发布）
        agent = await self._validate_agent(agent_id)
        (
            knowledge_base_ids,
            dropped_knowledge_base_ids,
        ) = await self._sanitize_client_knowledge_base_ids(
            agent_id,
            knowledge_base_ids,
        )

        # 1. Get or create conversation / 1. 获取或创建对话
        prepared_turn = await self._prepare_conversation_turn(
            agent_id=agent_id,
            conversation_id=conversation_id,
            message=message,
            user_id=user_id,
            user_role=user_role,
            interaction_mode=interaction_mode,
            interaction_updates=interaction_updates,
            trust_policy_ref=trust_policy_ref,
        )
        conversation = prepared_turn.conversation
        is_new_conversation = prepared_turn.is_new_conversation
        interaction_mode_effective = prepared_turn.interaction_mode_effective
        resolved_trust_policy_ref = prepared_turn.resolved_trust_policy_ref
        interaction_mode_downgrade_reason = (
            prepared_turn.interaction_mode_downgrade_reason
        )
        interaction_updates = prepared_turn.interaction_updates
        memory_event_id = prepared_turn.memory_event_id

        # 1.5 Increment daily conversation count for new chat (conversations_per_day) / 1.5 新对话递增每日计数
        if is_new_conversation:
            await AgentQuotaManager.record_conversation(
                tenant_id=self.tenant_id,
                agent_id=agent_id,
                user_id=user_id,
            )

        # 2. Load history → ChatMessage (context_config) / 2. 加载历史并转 ChatMessage
        ctx_cfg = agent.context_config or {}
        history_messages = await self.conversation_svc.load_chat_history(
            conversation_id=conversation.id,
            max_messages=ctx_cfg.get("max_history_messages", 0),
            max_tokens=ctx_cfg.get("max_history_tokens", 0),
        )

        # 3. Append new user message (with attachments) / 3. 追加用户消息（含附件）
        attach_list = (
            [a if isinstance(a, dict) else a.model_dump() for a in attachments]
            if attachments
            else None
        )
        if message.strip() or attach_list:
            user_msg = ChatMessage(
                role="user",
                content=message,
                attachments=attach_list,
            )
            all_messages = [*history_messages, user_msg]
        else:
            all_messages = list(history_messages)

        # 3.5 BEFORE_AGENT_CHAT hook (messages / system prompt / block) / 3.5 BEFORE_AGENT_CHAT 钩子
        hook_registry = get_hook_registry()
        if hook_registry.has_hooks(HookPoint.BEFORE_AGENT_CHAT):
            hook_ctx = await hook_registry.trigger(
                HookPoint.BEFORE_AGENT_CHAT,
                tenant_id=self.tenant_id,
                agent_id=agent_id,
                messages=all_messages,
                config={
                    "variables": variables,
                    "knowledge_base_ids": knowledge_base_ids,
                },
            )
            if hook_ctx.get("blocked"):
                raise BusinessException(
                    message=hook_ctx.get(
                        "block_reason", _("agent_chat.error.blocked_by_hook")
                    )
                )
            all_messages = hook_ctx.get("messages", all_messages)

        # 4. Build execution request / 4. 构建执行请求
        normalized_scene, normalized_channel, normalized_source, memory_enabled = (
            self._resolve_memory_context(
                memory_scene=memory_scene,
                memory_channel=memory_channel,
                memory_source=memory_source,
            )
        )
        memory_enabled = await self._resolve_effective_memory_enabled(
            agent_id=agent_id,
            scene=normalized_scene,
            scene_enabled=memory_enabled,
        )
        request = ExecutionRequest(
            agent_id=agent_id,
            tenant_id=self.tenant_id,
            user_id=user_id,
            messages=all_messages,
            input_variables=variables or {},
            execution_mode=AgentExecutionModeEnum.CONVERSATION.value,
            conversation_id=conversation.id,
            knowledge_base_ids=knowledge_base_ids,
            consented_actions=consented_actions,
            user_role=user_role,
            user_role_id=user_role_id,
            permissions=permissions,
            billing_context=await self._build_billing_context(
                agent=agent,
                user_id=user_id,
                user_role=user_role,
                user_role_id=user_role_id,
            ),
            memory_scene=normalized_scene,
            memory_channel=normalized_channel,
            memory_source=normalized_source,
            memory_enabled=memory_enabled,
            long_term_memory_enabled=bool(
                ctx_cfg.get("long_term_memory_enabled", memory_enabled)
            ),
            trust_policy_ref=resolved_trust_policy_ref,
            interaction_mode=interaction_mode_effective,
            page_session_id=page_session_id,
            interaction_updates=interaction_updates,
            knowledge_base_feedback=(
                {
                    "dropped_knowledge_base_ids": dropped_knowledge_base_ids,
                    "effective_knowledge_base_ids": knowledge_base_ids or [],
                }
                if dropped_knowledge_base_ids
                else None
            ),
        )

        # 4.1 Session memory injection (ai_chat_page only) / 4.1 会话记忆注入
        mem_text = await self._load_session_memory_context(request=request)
        request.session_memory_injected = bool(mem_text)
        if mem_text:
            # Prefer system slot, else prepend / system 位优先，否则插首位
            if request.messages and request.messages[0].role == "system":
                request.messages[
                    0
                ].content = f"{request.messages[0].content}\n\n{mem_text}"
            else:
                request.messages.insert(0, ChatMessage(role="system", content=mem_text))

        # 4.2 Conversation quota (max_turns / max_tokens per conversation) / 4.2 会话级配额
        quota_config = AgentQuotaConfig.from_dict(agent.quota_config)
        if (
            quota_config.max_turns_per_conversation > 0
            or quota_config.max_tokens_per_conversation > 0
        ):
            current_turns = sum(1 for m in request.messages if m.role == "assistant")
            current_tokens = sum(
                estimate_tokens(m.content or "") for m in request.messages
            )
            await AgentQuotaManager.check_conversation_limits(
                config=quota_config,
                current_turns=current_turns,
                current_tokens=current_tokens,
            )

        # 5. Dispatch with pre-validated agent (skip extra DB in Dispatcher) / 5. 调用分发器（已预校验 agent）
        dispatcher = ExecutionDispatcher(self.db)
        result = await dispatcher.dispatch(request, pre_loaded_agent=agent)

        if not result.success:
            raise BusinessException(
                message=result.error or _("agent_chat.error.execution_failed")
            )

        # 5.5 AFTER_AGENT_CHAT hook / 5.5 AFTER_AGENT_CHAT 钩子
        if hook_registry.has_hooks(HookPoint.AFTER_AGENT_CHAT):
            hook_ctx = await hook_registry.trigger(
                HookPoint.AFTER_AGENT_CHAT,
                tenant_id=self.tenant_id,
                agent_id=agent_id,
                response=result.output,
                total_tokens=result.total_tokens,
            )
            if "response" in hook_ctx and hook_ctx["response"] != result.output:
                result.output = hook_ctx["response"]

        # 6. Persist new messages (user + engine) / 6. 持久化新消息
        history_count = len(history_messages)
        turn_projection = self._build_turn_projection_bundle(
            result,
            interaction_mode_effective=interaction_mode_effective,
            downgrade_reason=interaction_mode_downgrade_reason,
        )
        context_diagnostics_payload = turn_projection.context_diagnostics
        last_run_summary_payload = turn_projection.last_run_summary
        (
            tool_calls_collected,
            _persisted_message_count,
        ) = await self.conversation_svc.persist_chat_messages(
            conversation=conversation,
            result=result,
            history_count=history_count,
            agent_id=agent_id,
            route_source=route_source,
            context_diagnostics=context_diagnostics_payload,
            last_run_summary=last_run_summary_payload,
        )

        # 7. Update conversation stats + agent usage / 7. 更新对话与智能体用量
        await self.conversation_svc.update_stats(
            conversation,
            result,
            current_agent=agent,
        )
        await AgentStatsManager.record_chat(
            tenant_id=self.tenant_id,
            agent_id=agent_id,
            tokens=result.total_tokens,
        )

        # 7.1 Write session memory (non-blocking, fail-safe) / 7.1 写入会话记忆
        try:
            memory_delta = await self._persist_session_memory(
                request=request,
                message=message,
                response=result.output or "",
                event_id=memory_event_id,
            )
            if memory_delta:
                await self.conversation_svc.mark_memory_updated(conversation.id)
        except Exception as exc:
            logger.warning(
                "Persist session memory failed: tenant={} conversation={} err={}",
                self.tenant_id,
                conversation.id,
                str(exc),
            )
        await self.db.commit()

        duration_ms = int((time.perf_counter() - start) * 1000)

        logger.info(
            "Chat completed: agent={} conversation={} tokens={} duration={}ms",
            agent_id,
            conversation.id,
            result.total_tokens,
            duration_ms,
        )

        prune_stats = (
            result.prune_stats if isinstance(result.prune_stats, dict) else None
        )
        rag_source_kinds = (
            result.rag_source_kinds if isinstance(result.rag_source_kinds, list) else []
        )

        return AgentChatResponse(
            conversation_id=conversation.id,
            message=result.output,
            tool_calls=tool_calls_collected or None,
            total_tokens=result.total_tokens,
            duration_ms=duration_ms,
            effective_knowledge_base_ids=knowledge_base_ids,
            dropped_knowledge_base_ids=dropped_knowledge_base_ids or None,
            context_compacted=(
                result.context_compacted
                if isinstance(result.context_compacted, bool)
                else False
            ),
            memory_recalled=(
                result.memory_recalled
                if isinstance(result.memory_recalled, bool)
                else False
            ),
            prune_stats=prune_stats,
            rag_source_kinds=rag_source_kinds,
            interaction_mode_effective=interaction_mode_effective,
            context_diagnostics=context_diagnostics_payload,
            last_run_summary=last_run_summary_payload,
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
        page_context: PageContext | dict[str, Any] | None = None,
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
        page_session_id: str | None = None,
        route_source: str | None = None,
        interaction_updates: list[dict[str, Any]] | None = None,
        trust_policy_ref: dict[str, Any] | None = None,
        interaction_mode: InteractionMode = "confirm",
    ) -> StreamingResponse:
        """
        流式对话（返回 StreamingResponse）/ Streaming chat (returns StreamingResponse).

        流程：加载 Agent → 创建/续接对话 → 加载历史 → 通过 engine.stream_execute SSE 推送

        Args:
            agent_id: 智能体 ID
            message: 用户消息
            conversation_id: 对话 ID（续接时传入）
            variables: 输入变量
            user_id: 用户 ID
            user_role: 用户角色（platform_admin / tenant_admin / tenant_user）
            permissions: 用户 RBAC 权限码集合

        Returns:
            StreamingResponse (SSE)
        """
        variables = PageContext.normalize_variables(variables, page_context)

        # 0. Load and validate Agent (must be published) / 0. 加载并校验 Agent（须已发布）
        agent = await self._validate_agent(agent_id)
        (
            knowledge_base_ids,
            dropped_knowledge_base_ids,
        ) = await self._sanitize_client_knowledge_base_ids(
            agent_id,
            knowledge_base_ids,
        )

        # Parse input: single message or batch / 解析消息：单条 message 或批量 messages
        batch = messages if messages else ([message] if message else [])
        first_message = batch[0] if batch else ""

        # 1. Get or create conversation / 1. 获取或创建对话
        prepared_turn = await self._prepare_conversation_turn(
            agent_id=agent_id,
            conversation_id=conversation_id,
            message=first_message,
            user_id=user_id,
            user_role=user_role,
            interaction_mode=interaction_mode,
            interaction_updates=interaction_updates,
            trust_policy_ref=trust_policy_ref,
        )
        conversation = prepared_turn.conversation
        is_new_conversation = prepared_turn.is_new_conversation
        interaction_mode_effective = prepared_turn.interaction_mode_effective
        resolved_trust_policy_ref = prepared_turn.resolved_trust_policy_ref
        interaction_mode_downgrade_reason = (
            prepared_turn.interaction_mode_downgrade_reason
        )
        interaction_updates = prepared_turn.interaction_updates
        memory_event_id = prepared_turn.memory_event_id

        # 2. Load history (context_config window) / 2. 加载历史
        ctx_cfg = agent.context_config or {}
        history_messages = await self.conversation_svc.load_chat_history(
            conversation_id=conversation.id,
            max_messages=ctx_cfg.get("max_history_messages", 0),
            max_tokens=ctx_cfg.get("max_history_tokens", 0),
        )

        # 3. Append user messages (batch ok; attachments on first only) / 3. 追加用户消息（首条可带附件）
        attach_list = (
            [a if isinstance(a, dict) else a.model_dump() for a in attachments]
            if attachments
            else None
        )
        if batch:
            user_msgs = [
                ChatMessage(
                    role="user", content=m, attachments=attach_list if i == 0 else None
                )
                for i, m in enumerate(batch)
            ]
        elif message.strip() or attach_list:
            user_msgs = [
                ChatMessage(role="user", content=message, attachments=attach_list),
            ]
        else:
            user_msgs = []
        all_messages = [*history_messages, *user_msgs]

        # 3.5 BEFORE_AGENT_CHAT hook (messages / system prompt / block) / 3.5 BEFORE_AGENT_CHAT 钩子
        hook_registry = get_hook_registry()
        if hook_registry.has_hooks(HookPoint.BEFORE_AGENT_CHAT):
            hook_ctx = await hook_registry.trigger(
                HookPoint.BEFORE_AGENT_CHAT,
                tenant_id=self.tenant_id,
                agent_id=agent_id,
                messages=all_messages,
                config={
                    "variables": variables,
                    "knowledge_base_ids": knowledge_base_ids,
                },
            )
            if hook_ctx.get("blocked"):
                raise BusinessException(
                    message=hook_ctx.get(
                        "block_reason", _("agent_chat.error.blocked_by_hook")
                    )
                )
            all_messages = hook_ctx.get("messages", all_messages)

        # 4. Build execution request (stream) / 4. 构建执行请求（流式）
        normalized_scene, normalized_channel, normalized_source, memory_enabled = (
            self._resolve_memory_context(
                memory_scene=memory_scene,
                memory_channel=memory_channel,
                memory_source=memory_source,
            )
        )
        memory_enabled = await self._resolve_effective_memory_enabled(
            agent_id=agent_id,
            scene=normalized_scene,
            scene_enabled=memory_enabled,
        )
        billing_context = await self._build_billing_context(
            agent=agent,
            user_id=user_id,
            user_role=user_role,
            user_role_id=user_role_id,
        )
        request_bundle = await self.stream_bootstrap.build_conversation_stream_request(
            agent=agent,
            agent_id=agent_id,
            conversation_id=conversation.id,
            all_messages=all_messages,
            variables=variables,
            knowledge_base_ids=knowledge_base_ids,
            dropped_knowledge_base_ids=dropped_knowledge_base_ids,
            consented_actions=consented_actions,
            user_role=user_role,
            user_role_id=user_role_id,
            permissions=permissions,
            billing_context=billing_context,
            normalized_scene=normalized_scene,
            normalized_channel=normalized_channel,
            normalized_source=normalized_source,
            memory_enabled=memory_enabled,
            trust_policy_ref=resolved_trust_policy_ref,
            interaction_mode=interaction_mode_effective,
            page_session_id=page_session_id,
            interaction_updates=interaction_updates,
            long_term_memory_enabled=bool(
                ctx_cfg.get("long_term_memory_enabled", memory_enabled)
            ),
            session_memory_text="",
        )
        request = request_bundle.request

        # 4.1 Session memory injection (ai_chat_page only) / 4.1 会话记忆注入
        mem_text = await self._load_session_memory_context(request=request)
        self.stream_bootstrap._inject_session_memory(request, mem_text)

        # 4.2 Conversation quota (max_turns / max_tokens per conversation) / 4.2 会话级配额
        await self.stream_bootstrap.check_conversation_limits(
            quota_config=request_bundle.quota_config,
            messages=request.messages,
        )

        # 5. Pre-check quota, concurrency, hooks (match dispatch) / 5. 配额并发钩子前置检查
        preflight = await self.stream_bootstrap.run_stream_preflight(
            agent=agent,
            agent_id=agent_id,
            request=request,
            quota_config=request_bundle.quota_config,
            estimated_tokens=request_bundle.estimated_tokens,
            user_id=user_id,
            persist_new_conversation=is_new_conversation,
            persist_user_messages=self.conversation_svc.persist_user_messages,
            conversation=conversation,
            user_msgs=user_msgs,
        )
        hook_registry = preflight.hook_registry
        lock_token = preflight.lock_token
        seeded_user_message_count = preflight.seeded_user_message_count

        # 6. Create Gateway / 6. 创建 Gateway
        engine_bundle = await self.stream_bootstrap.build_stream_engine_bundle(
            agent=agent,
            agent_id=agent_id,
            user_id=user_id,
            user_role=user_role,
            permissions=permissions,
            variables=variables,
            page_session_id=page_session_id,
            trust_policy_ref=resolved_trust_policy_ref,
            interaction_mode=interaction_mode_effective,
        )
        engine = engine_bundle.engine
        is_image_model = engine_bundle.is_image_model
        skill_result = engine_bundle.skill_result

        # 7. Persist callback after stream (quota, lock release, hooks) / 7. 流式结束持久化回调
        history_count = len(history_messages) + int(seeded_user_message_count or 0)
        turn_projector = self._bind_turn_projector(
            interaction_mode_effective=interaction_mode_effective,
            downgrade_reason=interaction_mode_downgrade_reason,
        )
        on_stream_complete = AgentChatStreamPersistenceOrchestrator(
            tenant_id=self.tenant_id,
            agent_id=agent_id,
            conversation_id=conversation.id,
            request=request,
            agent=agent,
            message=message,
            first_message=first_message,
            history_count=history_count,
            seeded_user_message_count=seeded_user_message_count,
            route_source=route_source,
            interaction_mode_effective=interaction_mode_effective,
            interaction_mode_downgrade_reason=interaction_mode_downgrade_reason,
            memory_event_id=memory_event_id,
            estimated_tokens=request_bundle.estimated_tokens,
            quota_config=request_bundle.quota_config,
            user_id=user_id,
            lock_token=lock_token,
            hook_registry=hook_registry,
            persist_session_memory=self._persist_session_memory,
            build_context_diagnostics=turn_projector.build_context_diagnostics,
            build_last_run_summary=turn_projector.build_last_run_summary,
            assistant_message_has_visible_reply_payload=self._assistant_message_has_visible_reply_payload,
            friendly_stream_error_text=self._friendly_stream_error_text,
            build_stream_error_display=self._build_stream_error_display,
            runtime_dependencies=self._build_stream_runtime_dependencies,
        )

        if is_image_model:
            return await engine.stream_execute(
                agent=agent,
                request=request,
                on_complete=on_stream_complete,
                image_params=image_params,
            )
        else:
            return await engine.stream_execute(
                agent=agent,
                request=request,
                on_complete=on_stream_complete,
                skill_result=skill_result,
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
        """
        轻量级流式调用（无对话记录，无消息持久化）/ Lightweight streaming (no conversation/message persistence).

        适用于富文本写作操作（续写、优化、校对等），不需要对话上下文。
        与 stream_chat 的区别：
        - 不创建 AgentConversation 记录
        - 不保存消息历史
        - 不注入会话记忆
        - 仍保留配额检查和统计
        """
        agent = await self._validate_agent(agent_id)
        (
            knowledge_base_ids,
            dropped_knowledge_base_ids,
        ) = await self._sanitize_client_knowledge_base_ids(
            agent_id,
            knowledge_base_ids,
        )

        request_bundle = await self.stream_bootstrap.build_ephemeral_stream_request(
            agent=agent,
            agent_id=agent_id,
            message=message,
            variables=variables,
            user_id=user_id,
            knowledge_base_ids=knowledge_base_ids,
            dropped_knowledge_base_ids=dropped_knowledge_base_ids,
            user_role=user_role,
            user_role_id=user_role_id,
            permissions=permissions,
            billing_context=await self._build_billing_context(
                agent=agent,
                user_id=user_id,
                user_role=user_role,
                user_role_id=user_role_id,
            ),
        )
        request = request_bundle.request
        preflight = await self.stream_bootstrap.run_stream_preflight(
            agent=agent,
            agent_id=agent_id,
            request=request,
            quota_config=request_bundle.quota_config,
            estimated_tokens=request_bundle.estimated_tokens,
            user_id=user_id,
            persist_new_conversation=False,
            persist_user_messages=None,
        )
        lock_token = preflight.lock_token

        async def on_stream_complete(result: ExecutionResult) -> dict[str, Any] | None:
            try:
                actual_tokens = result.total_tokens or 0
                await AgentQuotaManager.adjust_usage(
                    tenant_id=self.tenant_id,
                    agent_id=agent_id,
                    estimated_tokens=request_bundle.estimated_tokens,
                    actual_tokens=actual_tokens,
                    config=request_bundle.quota_config,
                )
                if user_id and actual_tokens > 0:
                    await AgentQuotaManager.record_user_usage(
                        tenant_id=self.tenant_id,
                        agent_id=agent_id,
                        user_id=user_id,
                        tokens=actual_tokens,
                    )
                await AgentStatsManager.record_chat(
                    tenant_id=self.tenant_id,
                    agent_id=agent_id,
                    tokens=result.total_tokens,
                )
            finally:
                if lock_token:
                    await AgentConcurrencyLimiter.release(
                        tenant_id=self.tenant_id,
                        agent_id=agent_id,
                        lock_token=lock_token,
                    )
            return None

        engine_bundle = await self.stream_bootstrap.build_stream_engine_bundle(
            agent=agent,
            agent_id=agent_id,
            user_id=user_id,
            user_role=user_role,
            permissions=permissions,
            variables=variables,
            page_session_id=None,
            trust_policy_ref=None,
            interaction_mode="confirm",
            enable_tool_runtime=False,
        )
        engine = engine_bundle.engine
        return await engine.stream_execute(
            agent=agent,
            request=request,
            on_complete=on_stream_complete,
        )


__all__ = ["AgentChatService"]
