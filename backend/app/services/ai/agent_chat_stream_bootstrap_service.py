"""Shared streaming bootstrap helpers for AgentChatService."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.ai.agent_quota import (
    AgentConcurrencyExceeded,
    AgentConcurrencyLimiter,
    AgentQuotaConfig,
    AgentQuotaExceeded,
    AgentQuotaManager,
)
from app.ai.constants import MEMORY_CHANNEL_SYSTEM
from app.ai.engine.base import BaseEngine
from app.ai.engine.conversation import ConversationEngine
from app.ai.engine.image_generation import ImageGenerationEngine
from app.ai.engine.types import ExecutionRequest
from app.ai.events.hooks import HookPoint, get_hook_registry
from app.ai.gateway import AIGateway
from app.ai.tools.sandbox import ToolSandbox
from app.ai.types import ChatMessage
from app.ai.utils.token_estimator import estimate_tokens
from app.configs.service import ConfigService
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

    gateway: AIGateway
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
        self._inject_session_memory(request, session_memory_text)
        return StreamRequestBundle(
            request=request,
            quota_config=AgentQuotaConfig.from_dict(agent.quota_config),
            estimated_tokens=max(
                sum(estimate_tokens(m.content or "") for m in all_messages),
                100,
            ),
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
            estimated_tokens=max(estimate_tokens(message), 100),
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
        hook_registry = get_hook_registry()
        try:
            if (
                quota_config.max_concurrent > 0
                or quota_config.tenant_max_concurrent > 0
            ):
                lock_token = await AgentConcurrencyLimiter.acquire(
                    tenant_id=self.tenant_id,
                    agent_id=agent_id,
                    max_concurrent=quota_config.max_concurrent,
                    tenant_max_concurrent=quota_config.tenant_max_concurrent,
                )
            await AgentQuotaManager.check_quota(
                tenant_id=self.tenant_id,
                agent_id=agent_id,
                config=quota_config,
                estimated_tokens=estimated_tokens,
            )
            if user_id:
                await AgentQuotaManager.check_user_quota(
                    tenant_id=self.tenant_id,
                    agent_id=agent_id,
                    user_id=user_id,
                    config=quota_config,
                )
            await self._check_tenant_api_quota()
            hook_context = await hook_registry.trigger(
                HookPoint.BEFORE_EXECUTE,
                tenant_id=self.tenant_id,
                agent_id=agent_id,
                execution_mode=request.execution_mode,
                request=request,
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
        agent_id: int,
        user_id: int | None,
        user_role: str,
        permissions: set[str] | None,
        variables: dict[str, Any] | None,
        page_session_id: str | None,
        trust_policy_ref: dict[str, Any] | None,
        interaction_mode: str = "trusted_auto",
        enable_tool_runtime: bool = True,
    ) -> StreamEngineBundle:
        gateway = AIGateway(self.db)
        model_obj = getattr(agent, "model", None)
        is_image_model = (
            model_obj is not None and getattr(model_obj, "type", "") == "image"
        )
        if is_image_model:
            return StreamEngineBundle(
                gateway=gateway,
                engine=ImageGenerationEngine(gateway=gateway),
                skill_result=None,
                is_image_model=True,
            )

        if not enable_tool_runtime:
            return StreamEngineBundle(
                gateway=gateway,
                engine=self._build_conversation_engine(
                    gateway=gateway,
                    sandbox=None,
                ),
                skill_result=None,
                is_image_model=False,
            )

        try:
            from app.ai.skills import resolver as skill_resolver_module

            skill_result = await skill_resolver_module.resolve_for_agent(
                self.db,
                agent,
                tenant_id=self.tenant_id,
                user_role=user_role,
            )
        except Exception as skill_exc:  # pragma: no cover - defensive logging path
            logger.error(
                "Skill resolution failed for agent {}: {}",
                agent_id,
                str(skill_exc),
            )
            skill_result = None

        config_service = ConfigService(self.db)
        toolkit_security_level = await config_service.get_platform_config(
            "toolkit_security_level",
            default="normal",
        )
        toolkit_memory_limit_mb = await config_service.get_platform_config(
            "toolkit_memory_limit_mb",
            default=256,
        )
        sandbox = ToolSandbox(
            tenant_id=self.tenant_id,
            agent_id=agent_id,
            user_id=user_id,
            user_role=user_role,
            permissions=permissions,
            gateway=gateway,
            db=self.db,
            agent=agent,
            toolkit_security_level=str(toolkit_security_level),
            toolkit_memory_limit_mb=int(toolkit_memory_limit_mb),
            input_variables=variables or {},
            page_session_id=page_session_id,
            trust_policy_ref=trust_policy_ref,
            interaction_mode=interaction_mode,
        )
        return StreamEngineBundle(
            gateway=gateway,
            engine=self._build_conversation_engine(
                gateway=gateway,
                sandbox=sandbox,
            ),
            skill_result=skill_result,
            is_image_model=False,
        )

    def _build_conversation_engine(
        self,
        *,
        gateway: AIGateway,
        sandbox: Any,
    ) -> Any:
        if self.conversation_engine_factory is not None:
            return self.conversation_engine_factory(
                db=self.db,
                gateway=gateway,
                sandbox=sandbox,
            )
        return ConversationEngine(db=self.db, gateway=gateway, sandbox=sandbox)

    @staticmethod
    def _inject_session_memory(
        request: ExecutionRequest,
        session_memory_text: str,
    ) -> None:
        request.session_memory_injected = bool(session_memory_text)
        if not session_memory_text:
            return
        if request.messages and request.messages[0].role == "system":
            request.messages[0].content = (
                f"{request.messages[0].content}\n\n{session_memory_text}"
            )
            return
        request.messages.insert(
            0,
            ChatMessage(role="system", content=session_memory_text),
        )

    async def _check_tenant_api_quota(self) -> None:
        if not self.tenant_id:
            return
        from app.enums import ErrorCode
        from app.services.tenant.quota_service import QuotaService

        api_check = await QuotaService.check_api_quota_for_tenant_id(
            self.db,
            self.tenant_id,
        )
        if not api_check.allowed:
            raise BusinessException(
                message=api_check.message or _("quota.api_calls_exceeded"),
                code=ErrorCode.CONFLICT,
            )
