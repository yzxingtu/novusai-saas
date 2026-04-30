"""Shared streaming bootstrap helpers for AgentChatService."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.ai.agent_quota import (
    AgentConcurrencyExceeded,
    AgentQuotaConfig,
    AgentQuotaExceeded,
    AgentQuotaManager,
)
from app.ai.constants import MEMORY_CHANNEL_SYSTEM
from app.ai.engine.base import BaseEngine
from app.ai.engine.engine_bootstrap_support import build_engine_bootstrap_bundle
from app.ai.engine.execution_preflight_support import (
    acquire_preflight_lock,
    check_preflight_quota,
    estimate_preflight_tokens,
    trigger_before_execute_preflight,
)
from app.ai.engine.types import ExecutionRequest
from app.ai.types import ChatMessage
from app.ai.utils.token_estimator import estimate_tokens
from app.core.i18n import _
from app.core.logging import LogManager
from app.enums.agent import AgentExecutionModeEnum
from app.exceptions import BusinessException

logger = LogManager.get_logger("ai.agent_chat_stream_bootstrap_service")


@dataclass(frozen=True)
class StreamRequestBundle:
    """Built execution request plus stream quota metadata."""

    request: ExecutionRequest
    quota_config: AgentQuotaConfig
    estimated_tokens: int


@dataclass(frozen=True)
class StreamPreflightBundle:
    """Preflight results required by the caller after quota checks."""

    hook_registry: Any
    lock_token: str
    seeded_user_message_count: int


@dataclass(frozen=True)
class StreamEngineBundle:
    """Engine wiring result for a stream execution."""

    gateway: Any
    engine: Any
    skill_result: Any
    is_image_model: bool


class AgentChatStreamBootstrapService:
    """Extract shared request/preflight/engine bootstrap from AgentChatService."""

    def __init__(
        self,
        db,
        tenant_id: int,
        *,
        conversation_engine_factory: Callable[..., Any] | None = None,
    ) -> None:
        self.db = db
        self.tenant_id = tenant_id
        self.conversation_engine_factory = conversation_engine_factory

    @staticmethod
    def _normalize_page_session_id(value: Any) -> str | None:
        if not isinstance(value, str):
            return None
        normalized = value.strip()
        if not normalized:
            return None
        return normalized[:64]

    @classmethod
    def _resolve_page_session_id(
        cls,
        *,
        variables: dict[str, Any] | None,
        explicit_page_session_id: str | None,
    ) -> str | None:
        del variables, explicit_page_session_id
        return None

    async def build_conversation_stream_request(
        self,
        *,
        agent: Any,
        agent_id: int,
        conversation_id: int,
        all_messages: list[ChatMessage],
        variables: dict[str, Any] | None,
        knowledge_base_ids: list[int] | None,
        dropped_knowledge_base_ids: list[int],
        consented_actions: list[str] | None,
        user_role: str,
        user_role_id: int | None,
        permissions: set[str] | None,
        billing_context: dict[str, Any],
        normalized_scene: str,
        normalized_channel: str,
        normalized_source: str,
        memory_enabled: bool,
        trust_policy_ref: dict[str, Any] | None,
        interaction_mode: str,
        page_session_id: str | None,
        interaction_updates: list[dict[str, Any]] | None,
        long_term_memory_enabled: bool,
        session_memory_text: str,
    ) -> StreamRequestBundle:
        effective_page_session_id = self._resolve_page_session_id(
            variables=variables,
            explicit_page_session_id=page_session_id,
        )
        request = ExecutionRequest(
            agent_id=agent_id,
            tenant_id=self.tenant_id,
            user_id=billing_context.get("user_id"),
            messages=list(all_messages),
            input_variables=variables or {},
            execution_mode=AgentExecutionModeEnum.CONVERSATION.value,
            stream=True,
            conversation_id=conversation_id,
            knowledge_base_ids=knowledge_base_ids,
            consented_actions=consented_actions,
            user_role=user_role,
            user_role_id=user_role_id,
            permissions=permissions,
            billing_context=billing_context,
            memory_scene=normalized_scene,
            memory_channel=normalized_channel,
            memory_source=normalized_source,
            memory_enabled=memory_enabled,
            long_term_memory_enabled=long_term_memory_enabled,
            trust_policy_ref=trust_policy_ref,
            interaction_mode=interaction_mode,
            page_session_id=effective_page_session_id,
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
        self._inject_session_memory(request, session_memory_text)
        return StreamRequestBundle(
            request=request,
            quota_config=AgentQuotaConfig.from_dict(agent.quota_config),
            estimated_tokens=estimate_preflight_tokens(all_messages),
        )

    async def build_ephemeral_stream_request(
        self,
        *,
        agent: Any,
        agent_id: int,
        message: str,
        variables: dict[str, Any] | None,
        user_id: int | None,
        knowledge_base_ids: list[int] | None,
        dropped_knowledge_base_ids: list[int],
        user_role: str,
        user_role_id: int | None,
        permissions: set[str] | None,
        billing_context: dict[str, Any],
    ) -> StreamRequestBundle:
        request = ExecutionRequest(
            agent_id=agent_id,
            tenant_id=self.tenant_id,
            user_id=user_id,
            messages=[ChatMessage(role="user", content=message)],
            input_variables=variables or {},
            execution_mode=AgentExecutionModeEnum.CONVERSATION.value,
            stream=True,
            conversation_id=None,
            knowledge_base_ids=knowledge_base_ids,
            skip_persistence=True,
            user_role=user_role,
            user_role_id=user_role_id,
            permissions=permissions,
            billing_context=billing_context,
            memory_scene="ephemeral",
            memory_channel=MEMORY_CHANNEL_SYSTEM,
            memory_source="system.ai_writing",
            memory_enabled=False,
            long_term_memory_enabled=False,
            knowledge_base_feedback=(
                {
                    "dropped_knowledge_base_ids": dropped_knowledge_base_ids,
                    "effective_knowledge_base_ids": knowledge_base_ids or [],
                }
                if dropped_knowledge_base_ids
                else None
            ),
        )
        return StreamRequestBundle(
            request=request,
            quota_config=AgentQuotaConfig.from_dict(agent.quota_config),
            estimated_tokens=estimate_preflight_tokens(request.messages),
        )

    async def check_conversation_limits(
        self,
        *,
        quota_config: AgentQuotaConfig,
        messages: list[ChatMessage],
    ) -> None:
        if (
            quota_config.max_turns_per_conversation <= 0
            and quota_config.max_tokens_per_conversation <= 0
        ):
            return
        current_turns = sum(1 for m in messages if m.role == "assistant")
        current_tokens = sum(estimate_tokens(m.content or "") for m in messages)
        await AgentQuotaManager.check_conversation_limits(
            config=quota_config,
            current_turns=current_turns,
            current_tokens=current_tokens,
        )

    async def run_stream_preflight(
        self,
        *,
        agent: Any,
        agent_id: int,
        request: ExecutionRequest,
        quota_config: AgentQuotaConfig,
        estimated_tokens: int,
        user_id: int | None,
        persist_new_conversation: bool,
        persist_user_messages,
        conversation: Any = None,
        user_msgs: list[ChatMessage] | None = None,
    ) -> StreamPreflightBundle:
        lock_token = ""
        seeded_user_message_count = 0
        try:
            lock_token = await acquire_preflight_lock(
                tenant_id=self.tenant_id,
                agent_id=agent_id,
                quota_config=quota_config,
            )
            await check_preflight_quota(
                db=self.db,
                request=request,
                agent_id=agent_id,
                quota_config=quota_config,
                estimated_tokens=estimated_tokens,
            )
            hook_registry, hook_context = await trigger_before_execute_preflight(
                request=request,
                agent_id=agent_id,
            )
            if hook_context.get("blocked"):
                raise BusinessException(
                    message=hook_context.get(
                        "block_reason",
                        _("agent.error.blocked_by_hook"),
                    )
                )
            if persist_new_conversation:
                await AgentQuotaManager.record_conversation(
                    tenant_id=self.tenant_id,
                    agent_id=agent_id,
                    user_id=user_id,
                )
            if conversation is not None and user_msgs:
                seeded_user_message_count = await persist_user_messages(
                    conversation=conversation,
                    messages=user_msgs,
                )
            await self.db.commit()
            await BaseEngine._publish_execution_started(request, agent)
            return StreamPreflightBundle(
                hook_registry=hook_registry,
                lock_token=lock_token,
                seeded_user_message_count=seeded_user_message_count,
            )
        except (AgentQuotaExceeded, AgentConcurrencyExceeded, BusinessException):
            if lock_token:
                from app.ai.agent_quota import AgentConcurrencyLimiter

                await AgentConcurrencyLimiter.release(
                    tenant_id=self.tenant_id,
                    agent_id=agent_id,
                    lock_token=lock_token,
                )
            raise

    async def build_stream_engine_bundle(
        self,
        *,
        agent: Any,
        request: ExecutionRequest,
        enable_tool_runtime: bool = True,
    ) -> StreamEngineBundle:
        bundle = await build_engine_bootstrap_bundle(
            db=self.db,
            agent=agent,
            request=request,
            enable_tool_runtime=enable_tool_runtime,
            allow_image_engine=True,
            tolerate_skill_resolution_failure=True,
            conversation_engine_factory=self.conversation_engine_factory,
            log=logger,
        )
        return StreamEngineBundle(
            gateway=bundle.gateway,
            engine=bundle.engine,
            skill_result=bundle.skill_result,
            is_image_model=bundle.is_image_model,
        )

    @staticmethod
    def _inject_session_memory(
        request: ExecutionRequest,
        session_memory_text: str,
    ) -> None:
        request.session_memory_injected = bool(session_memory_text)
        if not session_memory_text:
            return
        if request.messages and request.messages[0].role == "system":
            request.messages[
                0
            ].content = f"{request.messages[0].content}\n\n{session_memory_text}"
            return
        request.messages.insert(
            0,
            ChatMessage(role="system", content=session_memory_text),
        )
