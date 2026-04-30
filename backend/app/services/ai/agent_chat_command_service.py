"""Command orchestrators for AgentChatService chat and stream writes."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from fastapi.responses import StreamingResponse

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
from app.ai.engine.dispatcher import ExecutionDispatcher
from app.ai.engine.types import ExecutionRequest
from app.ai.events.hooks import HookPoint
from app.ai.memory_policy import (
    attach_memory_runtime_policy,
)
from app.ai.types import ChatMessage
from app.ai.utils.token_estimator import estimate_tokens
from app.core.i18n import _
from app.core.logging import LogManager
from app.enums.agent import AgentExecutionModeEnum
from app.enums.common import UserRoleEnum
from app.exceptions import BusinessException
from app.schemas.ai.agent_chat import AgentChatResponse, InteractionMode
from app.schemas.ai.retired_page_awareness import retired_page_awareness_input_keys
from app.services.ai.agent_chat_command_ephemeral_support import (
    execute_ephemeral_stream_chat,
)
from app.services.ai.agent_chat_command_preflight_support import (
    build_user_messages,
    merge_history_with_user_messages,
    run_before_agent_chat_hook,
)
from app.services.ai.agent_chat_stream_persistence_orchestrator import (
    AgentChatStreamPersistenceOrchestrator,
)
from app.services.ai.agent_chat_turn_projection_support import (
    bind_turn_projector,
    build_turn_projection_bundle,
)

if TYPE_CHECKING:
    from app.services.ai.agent_chat_service import AgentChatService

logger = LogManager.get_logger("ai.agent_chat_service")


def _normalize_chat_variables(
    variables: dict[str, Any] | None,
) -> dict[str, Any] | None:
    normalized_variables = dict(variables or {})
    retired_keys = retired_page_awareness_input_keys(normalized_variables)
    if retired_keys:
        raise BusinessException(
            message=_(
                "agent_chat.error.retired_page_awareness_fields",
                fields=", ".join(retired_keys),
            )
        )
    return normalized_variables or None


class AgentChatCommandService:
    """Command entrypoints extracted from AgentChatService."""

    @staticmethod
    async def chat(
        service: AgentChatService,
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
        route_source: str | None = None,
        interaction_updates: list[dict[str, Any]] | None = None,
        trust_policy_ref: dict[str, Any] | None = None,
        interaction_mode: InteractionMode = "trusted_auto",
    ) -> AgentChatResponse:
        """Non-streaming chat orchestration."""
        start = time.perf_counter()
        variables = _normalize_chat_variables(variables)

        agent = await service._validate_agent(agent_id)
        (
            knowledge_base_ids,
            dropped_knowledge_base_ids,
        ) = await service.query_service.sanitize_client_knowledge_base_ids(
            agent_id,
            knowledge_base_ids,
        )

        prepared_turn = await service.turn_orchestrator.prepare_conversation_turn(
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

        if is_new_conversation:
            await AgentQuotaManager.record_conversation(
                tenant_id=service.tenant_id,
                agent_id=agent_id,
                user_id=user_id,
            )

        ctx_cfg = agent.context_config or {}
        history_messages = await service.conversation_svc.load_chat_history(
            conversation_id=conversation.id,
            max_messages=ctx_cfg.get("max_history_messages", 0),
            max_tokens=ctx_cfg.get("max_history_tokens"),
        )

        user_messages = build_user_messages(
            batch=None,
            message=message,
            attachments=attachments,
        )
        all_messages = merge_history_with_user_messages(history_messages, user_messages)
        hook_registry, all_messages = await run_before_agent_chat_hook(
            tenant_id=service.tenant_id,
            agent_id=agent_id,
            messages=all_messages,
            variables=variables,
            knowledge_base_ids=knowledge_base_ids,
        )

        normalized_scene, normalized_channel, normalized_source, memory_enabled = (
            service._resolve_memory_context(
                memory_scene=memory_scene,
                memory_channel=memory_channel,
                memory_source=memory_source,
            )
        )
        memory_enabled = await service._resolve_effective_memory_enabled(
            agent_id=agent_id,
            scene=normalized_scene,
            scene_enabled=memory_enabled,
        )
        request = ExecutionRequest(
            agent_id=agent_id,
            tenant_id=service.tenant_id,
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
            billing_context=await service._build_billing_context(
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
        service.runtime_support.prepare_request_memory_startup(
            request=request,
            conversation=conversation,
        )

        mem_text = await service._load_session_memory_context(request=request)
        request.session_memory_injected = bool(mem_text)
        if mem_text:
            if request.messages and request.messages[0].role == "system":
                request.messages[
                    0
                ].content = f"{request.messages[0].content}\n\n{mem_text}"
            else:
                request.messages.insert(0, ChatMessage(role="system", content=mem_text))

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

        dispatcher = ExecutionDispatcher(service.db)
        result = await dispatcher.dispatch(request, pre_loaded_agent=agent)

        if not result.success:
            raise BusinessException(
                message=result.error or _("agent_chat.error.execution_failed")
            )

        if hook_registry.has_hooks(HookPoint.AFTER_AGENT_CHAT):
            hook_ctx = await hook_registry.trigger(
                HookPoint.AFTER_AGENT_CHAT,
                tenant_id=service.tenant_id,
                agent_id=agent_id,
                response=result.output,
                total_tokens=result.total_tokens,
            )
            if "response" in hook_ctx and hook_ctx["response"] != result.output:
                result.output = hook_ctx["response"]

        history_count = len(history_messages)
        memory_policy = attach_memory_runtime_policy(request=request, result=result)
        result.memory_runtime_policy = memory_policy.to_dict()
        turn_projection = build_turn_projection_bundle(
            result,
            interaction_mode_effective=interaction_mode_effective,
            downgrade_reason=interaction_mode_downgrade_reason,
        )
        context_diagnostics_payload = turn_projection.context_diagnostics
        last_run_summary_payload = turn_projection.last_run_summary
        (
            tool_calls_collected,
            _persisted_message_count,
        ) = await service.conversation_svc.persist_chat_messages(
            conversation=conversation,
            result=result,
            history_count=history_count,
            history_messages=history_messages,
            agent_id=agent_id,
            route_source=route_source,
            context_diagnostics=context_diagnostics_payload,
            last_run_summary=last_run_summary_payload,
        )

        await service.conversation_svc.update_stats(
            conversation,
            result,
            current_agent=agent,
        )
        await AgentStatsManager.record_chat(
            tenant_id=service.tenant_id,
            agent_id=agent_id,
            tokens=result.total_tokens,
        )

        try:
            memory_delta = await service._persist_session_memory(
                request=request,
                message=message,
                response=result.output or "",
                event_id=memory_event_id,
            )
            if memory_delta:
                await service.conversation_svc.mark_memory_updated(conversation.id)
        except Exception as exc:
            logger.warning(
                "Persist session memory failed: tenant={} conversation={} err={}",
                service.tenant_id,
                conversation.id,
                str(exc),
            )
        await service.db.commit()

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
            context_diagnostics=context_diagnostics_payload,
            last_run_summary=last_run_summary_payload,
        )

    @staticmethod
    async def stream_chat(
        service: AgentChatService,
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
        route_source: str | None = None,
        interaction_updates: list[dict[str, Any]] | None = None,
        trust_policy_ref: dict[str, Any] | None = None,
        interaction_mode: InteractionMode = "trusted_auto",
    ) -> StreamingResponse:
        """Streaming chat orchestration."""
        variables = _normalize_chat_variables(variables)

        agent = await service._validate_agent(agent_id)
        (
            knowledge_base_ids,
            dropped_knowledge_base_ids,
        ) = await service.query_service.sanitize_client_knowledge_base_ids(
            agent_id,
            knowledge_base_ids,
        )

        batch = messages if messages else ([message] if message else [])
        first_message = batch[0] if batch else ""

        prepared_turn = await service.turn_orchestrator.prepare_conversation_turn(
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

        ctx_cfg = agent.context_config or {}
        history_messages = await service.conversation_svc.load_chat_history(
            conversation_id=conversation.id,
            max_messages=ctx_cfg.get("max_history_messages", 0),
            max_tokens=ctx_cfg.get("max_history_tokens"),
        )

        user_msgs = build_user_messages(
            batch=batch,
            message=message,
            attachments=attachments,
        )
        all_messages = merge_history_with_user_messages(history_messages, user_msgs)
        hook_registry, all_messages = await run_before_agent_chat_hook(
            tenant_id=service.tenant_id,
            agent_id=agent_id,
            messages=all_messages,
            variables=variables,
            knowledge_base_ids=knowledge_base_ids,
        )

        normalized_scene, normalized_channel, normalized_source, memory_enabled = (
            service._resolve_memory_context(
                memory_scene=memory_scene,
                memory_channel=memory_channel,
                memory_source=memory_source,
            )
        )
        memory_enabled = await service._resolve_effective_memory_enabled(
            agent_id=agent_id,
            scene=normalized_scene,
            scene_enabled=memory_enabled,
        )
        billing_context = await service._build_billing_context(
            agent=agent,
            user_id=user_id,
            user_role=user_role,
            user_role_id=user_role_id,
        )
        request_bundle = (
            await service.stream_bootstrap.build_conversation_stream_request(
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
                interaction_updates=interaction_updates,
                long_term_memory_enabled=bool(
                    ctx_cfg.get("long_term_memory_enabled", memory_enabled)
                ),
                session_memory_text="",
            )
        )
        request = request_bundle.request
        service.runtime_support.prepare_request_memory_startup(
            request=request,
            conversation=conversation,
        )

        mem_text = await service._load_session_memory_context(request=request)
        service.stream_bootstrap._inject_session_memory(request, mem_text)

        await service.stream_bootstrap.check_conversation_limits(
            quota_config=request_bundle.quota_config,
            messages=request.messages,
        )

        preflight = await service.stream_bootstrap.run_stream_preflight(
            agent=agent,
            agent_id=agent_id,
            request=request,
            quota_config=request_bundle.quota_config,
            estimated_tokens=request_bundle.estimated_tokens,
            user_id=user_id,
            persist_new_conversation=is_new_conversation,
            persist_user_messages=service.conversation_svc.persist_user_messages,
            conversation=conversation,
            user_msgs=user_msgs,
        )
        hook_registry = preflight.hook_registry
        lock_token = preflight.lock_token
        seeded_user_message_count = preflight.seeded_user_message_count

        engine_bundle = await service.stream_bootstrap.build_stream_engine_bundle(
            agent=agent,
            request=request,
        )
        engine = engine_bundle.engine
        is_image_model = engine_bundle.is_image_model
        skill_result = engine_bundle.skill_result

        history_count = len(history_messages) + int(seeded_user_message_count or 0)
        turn_projector = bind_turn_projector(
            interaction_mode_effective=interaction_mode_effective,
            downgrade_reason=interaction_mode_downgrade_reason,
            context_diagnostics_builder=lambda result: (
                service._build_context_diagnostics(
                    result,
                    interaction_mode_effective=interaction_mode_effective,
                )
            ),
            last_run_summary_builder=lambda result: service._build_last_run_summary(
                result,
                interaction_mode_effective=interaction_mode_effective,
                downgrade_reason=interaction_mode_downgrade_reason,
            ),
        )
        on_stream_complete = AgentChatStreamPersistenceOrchestrator(
            tenant_id=service.tenant_id,
            agent_id=agent_id,
            conversation_id=conversation.id,
            request=request,
            agent=agent,
            message=message,
            first_message=first_message,
            history_count=history_count,
            history_messages=all_messages,
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
            persist_session_memory=service._persist_session_memory,
            commit_stream_memory_writes=service.db.commit,
            rollback_stream_memory_writes=service.db.rollback,
            build_context_diagnostics=turn_projector.build_context_diagnostics,
            build_last_run_summary=turn_projector.build_last_run_summary,
            assistant_message_has_visible_reply_payload=service.stream_support.assistant_message_has_visible_reply_payload,
            friendly_stream_error_text=service._friendly_stream_error_text,
            build_stream_error_display=service._build_stream_error_display,
            runtime_dependencies=service.stream_support.build_stream_runtime_dependencies,
        )

        if is_image_model:
            return await engine.stream_execute(
                agent=agent,
                request=request,
                on_complete=on_stream_complete,
                image_params=image_params,
            )
        return await engine.stream_execute(
            agent=agent,
            request=request,
            on_complete=on_stream_complete,
            skill_result=skill_result,
        )

    @staticmethod
    async def stream_chat_ephemeral(
        service: AgentChatService,
        agent_id: int,
        message: str,
        variables: dict[str, Any] | None = None,
        user_id: int | None = None,
        knowledge_base_ids: list[int] | None = None,
        user_role: str = UserRoleEnum.TENANT_ADMIN.value,
        user_role_id: int | None = None,
        permissions: set[str] | None = None,
    ) -> StreamingResponse:
        return await execute_ephemeral_stream_chat(
            service=service,
            agent_id=agent_id,
            message=message,
            variables=variables,
            user_id=user_id,
            knowledge_base_ids=knowledge_base_ids,
            user_role=user_role,
            user_role_id=user_role_id,
            permissions=permissions,
            agent_concurrency_limiter=AgentConcurrencyLimiter,
            agent_quota_manager=AgentQuotaManager,
            agent_stats_manager=AgentStatsManager,
        )


__all__ = ["AgentChatCommandService"]
