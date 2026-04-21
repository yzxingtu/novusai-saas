"""Stream persistence orchestrator for AgentChatService."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from app.ai.engine.execution_postflight_support import (
    ExecutionPostflightDependencies,
    apply_execution_result_postflight,
    release_execution_postflight_lock,
)
from app.ai.engine.types import ExecutionResult
from app.ai.events.hooks import HookPoint
from app.ai.memory_policy import attach_memory_runtime_policy
from app.ai.types import ChatMessage
from app.core.i18n import _
from app.core.logging import LogManager
from app.services.ai.agent_chat_stream_persistence_error_support import (
    persist_stream_last_error_marker,
    save_error_message_to_conversation,
)
from app.services.ai.agent_chat_stream_runtime_dependencies import (
    AgentChatStreamPersistenceDependencies,
)
from app.services.ai.conversation_message_persistence_service import (
    ConversationMessagePersistenceService,
)

logger = LogManager.get_logger("ai.agent_chat_service")


class AgentChatStreamPersistenceOrchestrator:
    """Owns stream `on_complete` persistence branches and post-persist tail."""

    def __init__(
        self,
        *,
        tenant_id: int,
        agent_id: int,
        conversation_id: int,
        request: Any,
        agent: Any,
        message: str,
        first_message: str,
        history_count: int,
        history_messages: list[ChatMessage],
        seeded_user_message_count: int,
        route_source: str | None,
        interaction_mode_effective: str,
        interaction_mode_downgrade_reason: str | None,
        memory_event_id: str,
        estimated_tokens: int,
        quota_config: Any,
        user_id: int | None,
        lock_token: str,
        hook_registry: Any,
        persist_session_memory: Callable[..., Awaitable[dict[str, list[str]] | None]],
        commit_stream_memory_writes: Callable[[], Awaitable[None]] | None,
        rollback_stream_memory_writes: Callable[[], Awaitable[None]] | None,
        build_context_diagnostics: Callable[[ExecutionResult], dict[str, Any]],
        build_last_run_summary: Callable[[ExecutionResult], dict[str, Any]],
        assistant_message_has_visible_reply_payload: Callable[[dict[str, Any]], bool],
        friendly_stream_error_text: Callable[..., str],
        build_stream_error_display: Callable[..., dict[str, Any]],
        runtime_dependencies: AgentChatStreamPersistenceDependencies
        | Callable[[], AgentChatStreamPersistenceDependencies],
    ) -> None:
        self.tenant_id = tenant_id
        self.agent_id = agent_id
        self.conversation_id = conversation_id
        self.request = request
        self.agent = agent
        self.message = message
        self.first_message = first_message
        self.history_count = history_count
        self.history_messages = list(history_messages or [])
        self.seeded_user_message_count = seeded_user_message_count
        self.route_source = route_source
        self.interaction_mode_effective = interaction_mode_effective
        self.interaction_mode_downgrade_reason = interaction_mode_downgrade_reason
        self.memory_event_id = memory_event_id
        self.estimated_tokens = estimated_tokens
        self.quota_config = quota_config
        self.user_id = user_id
        self.lock_token = lock_token
        self.hook_registry = hook_registry
        self.persist_session_memory = persist_session_memory
        self.commit_stream_memory_writes = commit_stream_memory_writes
        self.rollback_stream_memory_writes = rollback_stream_memory_writes
        self.build_context_diagnostics = build_context_diagnostics
        self.build_last_run_summary = build_last_run_summary
        self.assistant_message_has_visible_reply_payload = (
            assistant_message_has_visible_reply_payload
        )
        self.friendly_stream_error_text = friendly_stream_error_text
        self.build_stream_error_display = build_stream_error_display
        self.runtime_dependencies = runtime_dependencies

    def _deps(self) -> AgentChatStreamPersistenceDependencies:
        dependencies = self.runtime_dependencies
        if callable(dependencies):
            dependencies = dependencies()
        return dependencies

    @staticmethod
    def _copy_execution_result(
        result: ExecutionResult,
        **overrides: Any,
    ) -> ExecutionResult:
        payload = {
            key: getattr(result, key) for key in ExecutionResult.__dataclass_fields__
        }
        payload.update(overrides)
        return ExecutionResult(**payload)

    async def _persist_stream_last_error_marker(
        self,
        *,
        error_type: str,
        error_message: str,
        friendly_message: str,
        partial: bool,
        extra_payload: dict[str, Any] | None = None,
        memory_runtime_policy: dict[str, Any] | None = None,
    ) -> bool:
        return await persist_stream_last_error_marker(
            self,
            error_type=error_type,
            error_message=error_message,
            friendly_message=friendly_message,
            partial=partial,
            extra_payload=extra_payload,
            memory_runtime_policy=memory_runtime_policy,
        )

    async def _save_error_message_to_conversation(
        self,
        *,
        error_text: str,
        user_message: str,
        result: ExecutionResult,
        context_diagnostics_payload: dict[str, Any],
        last_run_summary_payload: dict[str, Any],
        persist_user_message: bool,
    ) -> int:
        return await save_error_message_to_conversation(
            self,
            error_text=error_text,
            user_message=user_message,
            result=result,
            context_diagnostics_payload=context_diagnostics_payload,
            last_run_summary_payload=last_run_summary_payload,
            persist_user_message=persist_user_message,
        )

    async def _run_stream_post_persist_tail(
        self,
        *,
        final_result: ExecutionResult,
        extra: dict[str, Any],
    ) -> None:
        runtime_deps = self._deps()
        postflight_dependencies = ExecutionPostflightDependencies(
            adjust_usage=runtime_deps.adjust_usage,
            record_user_usage=runtime_deps.record_user_usage,
            release_concurrency=runtime_deps.release_concurrency,
            publish_execution_completed=runtime_deps.publish_execution_completed,
            publish_execution_failed=runtime_deps.publish_execution_failed,
        )
        try:
            try:
                await runtime_deps.record_chat_stats(
                    tenant_id=self.tenant_id,
                    agent_id=self.agent_id,
                    tokens=final_result.total_tokens,
                )
            except Exception as stats_exc:
                logger.warning(
                    "Record agent stats failed: tenant={} agent={} conversation={} err={}",
                    self.tenant_id,
                    self.agent_id,
                    self.conversation_id,
                    str(stats_exc),
                )

            if final_result.success:
                try:
                    memory_delta = await self.persist_session_memory(
                        request=self.request,
                        message=self.message,
                        response=final_result.output or "",
                        event_id=self.memory_event_id,
                    )
                    if memory_delta:
                        if self.commit_stream_memory_writes is not None:
                            await self.commit_stream_memory_writes()
                        async with runtime_deps.session_factory() as mem_db:
                            try:
                                mem_conv_svc = runtime_deps.conversation_service_cls(
                                    mem_db,
                                    self.tenant_id,
                                )
                                await mem_conv_svc.mark_memory_updated(
                                    self.conversation_id,
                                )
                                await mem_db.commit()
                            except Exception:
                                await mem_db.rollback()
                                raise
                        extra["memory_updated"] = True
                except Exception as mem_exc:
                    if self.rollback_stream_memory_writes is not None:
                        try:
                            await self.rollback_stream_memory_writes()
                        except Exception:
                            logger.warning(
                                "Rollback stream memory writes failed: tenant={} conversation={}",
                                self.tenant_id,
                                self.conversation_id,
                            )
                    logger.warning(
                        "Persist stream session memory failed: tenant={} conversation={} err={}",
                        self.tenant_id,
                        self.conversation_id,
                        str(mem_exc),
                    )

            if self.hook_registry.has_hooks(HookPoint.AFTER_AGENT_CHAT):
                hook_ctx = await self.hook_registry.trigger(
                    HookPoint.AFTER_AGENT_CHAT,
                    tenant_id=self.tenant_id,
                    agent_id=self.agent_id,
                    response=final_result.output,
                    total_tokens=final_result.total_tokens,
                )
                if (
                    "response" in hook_ctx
                    and hook_ctx["response"] != final_result.output
                ):
                    final_result.output = hook_ctx["response"]

            await apply_execution_result_postflight(
                request=self.request,
                agent=self.agent,
                agent_id=self.agent_id,
                result=final_result,
                hook_registry=self.hook_registry,
                estimated_tokens=self.estimated_tokens,
                quota_config=self.quota_config,
                user_id=self.user_id,
                dependencies=postflight_dependencies,
            )
        except Exception as tail_exc:
            logger.error(
                "Stream post-persist tail failed: tenant={} conversation={} err={}",
                self.tenant_id,
                self.conversation_id,
                str(tail_exc),
                exc_info=True,
            )
        finally:
            if self.lock_token:
                await release_execution_postflight_lock(
                    request=self.request,
                    agent_id=self.agent_id,
                    lock_token=self.lock_token,
                    dependencies=postflight_dependencies,
                )

    async def __call__(self, result: ExecutionResult) -> dict[str, Any] | None:
        extra: dict[str, Any] = {}
        persisted_message_count = 0
        context_diagnostics_payload: dict[str, Any] = {}
        last_run_summary_payload: dict[str, Any] = {}
        error_message_persisted = False
        critical_persistence_committed = False
        last_error_marker_persisted = False
        tail_result = result

        try:
            memory_policy = attach_memory_runtime_policy(
                request=self.request,
                result=result,
            )
            result.memory_runtime_policy = memory_policy.to_dict()
            context_diagnostics_payload = self.build_context_diagnostics(result)
            last_run_summary_payload = self.build_last_run_summary(result)

            new_start = ConversationMessagePersistenceService.resolve_new_message_start(
                result_messages=result.messages or [],
                history_count=self.history_count,
                history_messages=self.history_messages,
            )
            has_new_messages = bool((result.messages or [])[new_start:])
            if result.success or has_new_messages:
                try:
                    deps = self._deps()
                    async with deps.session_factory() as cb_db:
                        try:
                            cb_conv_svc = deps.conversation_service_cls(
                                cb_db,
                                self.tenant_id,
                            )
                            persisted_message_count = (
                                await cb_conv_svc.persist_stream_completion(
                                    conversation_id=self.conversation_id,
                                    result=result,
                                    history_count=self.history_count,
                                    history_messages=self.history_messages,
                                    agent_id=self.agent_id,
                                    route_source=self.route_source,
                                    context_diagnostics=context_diagnostics_payload,
                                    last_run_summary=last_run_summary_payload,
                                    current_agent=self.agent,
                                )
                            )
                            critical_persistence_committed = True
                        except Exception:
                            await cb_db.rollback()
                            raise
                except Exception as persist_exc:
                    logger.error(
                        "Stream completion persistence failed: tenant={} conversation={} err={}",
                        self.tenant_id,
                        self.conversation_id,
                        str(persist_exc),
                        exc_info=True,
                    )
                    extra["persistence_error"] = True
                    persist_failure_result = self._copy_execution_result(
                        result,
                        error=str(persist_exc),
                        provider_failure_kind="none",
                    )
                    try:
                        fallback_rows = await self._save_error_message_to_conversation(
                            error_text=_("common.server_error"),
                            user_message=self.first_message,
                            result=persist_failure_result,
                            persist_user_message=self.seeded_user_message_count <= 0,
                            context_diagnostics_payload={
                                **(context_diagnostics_payload or {}),
                                "persistence_error": True,
                                "persistence_error_message": str(persist_exc)[:500],
                            },
                            last_run_summary_payload={
                                **(last_run_summary_payload or {}),
                                "persistence_error": True,
                                "persistence_error_message": str(persist_exc)[:500],
                            },
                        )
                        if fallback_rows > 0:
                            persisted_message_count += fallback_rows
                            error_message_persisted = True
                            critical_persistence_committed = True
                    except Exception as fallback_exc:
                        logger.error(
                            "Fallback stream error persistence failed: tenant={} conversation={} err={}",
                            self.tenant_id,
                            self.conversation_id,
                            str(fallback_exc),
                            exc_info=True,
                        )
                        try:
                            marker_persisted = (
                                await self._persist_stream_last_error_marker(
                                    error_type="stream_on_complete_persistence_error",
                                    error_message=str(fallback_exc),
                                    friendly_message=_("common.server_error"),
                                    partial=bool(result.partial),
                                    extra_payload={
                                        "stage": "persist_chat_messages",
                                        "original_error": str(persist_exc)[:500],
                                        "fallback_error": str(fallback_exc)[:500],
                                    },
                                    memory_runtime_policy=result.memory_runtime_policy,
                                )
                            )
                            last_error_marker_persisted = (
                                last_error_marker_persisted or marker_persisted
                            )
                            critical_persistence_committed = (
                                critical_persistence_committed or marker_persisted
                            )
                        except Exception as marker_exc:
                            logger.error(
                                "Persist stream error marker failed after fallback error: tenant={} conversation={} err={}",
                                self.tenant_id,
                                self.conversation_id,
                                str(marker_exc),
                                exc_info=True,
                            )

            new_start = ConversationMessagePersistenceService.resolve_new_message_start(
                result_messages=result.messages or [],
                history_count=self.history_count,
                history_messages=self.history_messages,
            )
            new_messages_raw = (result.messages or [])[new_start:]
            user_message_count = sum(
                1 for m in new_messages_raw if m.get("role") == "user"
            )
            has_assistant_persisted = persisted_message_count > user_message_count
            has_visible_assistant_reply = any(
                self.assistant_message_has_visible_reply_payload(message)
                for message in new_messages_raw
            )
            if not result.success and (
                not has_assistant_persisted or not has_visible_assistant_reply
            ):
                friendly_error_text = self.friendly_stream_error_text(result.error)
                fallback_rows = await self._save_error_message_to_conversation(
                    error_text=friendly_error_text,
                    user_message=self.first_message,
                    result=result,
                    persist_user_message=self.seeded_user_message_count <= 0,
                    context_diagnostics_payload=context_diagnostics_payload,
                    last_run_summary_payload=last_run_summary_payload,
                )
                if fallback_rows > 0:
                    persisted_message_count += fallback_rows
                    error_message_persisted = True
                    critical_persistence_committed = True
                logger.warning(
                    "Stream execution failed for conversation_id={}: {}",
                    self.conversation_id,
                    result.error or "Unknown error",
                )
            extra["persistence_committed"] = critical_persistence_committed
            extra["persisted_message_count"] = int(persisted_message_count or 0)
        except Exception as on_complete_exc:
            logger.error(
                "Stream on_complete callback failed: tenant={} conversation={} err={}",
                self.tenant_id,
                self.conversation_id,
                str(on_complete_exc),
                exc_info=True,
            )
            extra["on_complete_error"] = True
            fallback_result = self._copy_execution_result(
                result,
                error=str(on_complete_exc),
                provider_failure_kind="none",
            )
            tail_result = fallback_result
            fallback_error_text = self.friendly_stream_error_text(fallback_result.error)
            if not error_message_persisted:
                try:
                    fallback_rows = await self._save_error_message_to_conversation(
                        error_text=fallback_error_text,
                        user_message=self.first_message,
                        result=fallback_result,
                        persist_user_message=self.seeded_user_message_count <= 0,
                        context_diagnostics_payload={
                            **(context_diagnostics_payload or {}),
                            "on_complete_error": True,
                            "on_complete_error_message": str(on_complete_exc)[:500],
                        },
                        last_run_summary_payload={
                            **(last_run_summary_payload or {}),
                            "on_complete_error": True,
                            "on_complete_error_message": str(on_complete_exc)[:500],
                        },
                    )
                    if fallback_rows > 0:
                        persisted_message_count += fallback_rows
                        error_message_persisted = True
                        critical_persistence_committed = True
                except Exception as fallback_exc:
                    logger.error(
                        "Final stream error message persistence failed: tenant={} conversation={} err={}",
                        self.tenant_id,
                        self.conversation_id,
                        str(fallback_exc),
                        exc_info=True,
                    )

            try:
                marker_persisted = await self._persist_stream_last_error_marker(
                    error_type="stream_on_complete_callback_error",
                    error_message=str(on_complete_exc),
                    friendly_message=fallback_error_text,
                    partial=bool(result.partial),
                    extra_payload={
                        "context_diagnostics_present": bool(
                            context_diagnostics_payload
                        ),
                        "last_run_summary_present": bool(last_run_summary_payload),
                    },
                    memory_runtime_policy=fallback_result.memory_runtime_policy,
                )
                last_error_marker_persisted = (
                    last_error_marker_persisted or marker_persisted
                )
                critical_persistence_committed = (
                    critical_persistence_committed or marker_persisted
                )
            except Exception as marker_exc:
                logger.error(
                    "Final stream error marker persistence failed: tenant={} conversation={} err={}",
                    self.tenant_id,
                    self.conversation_id,
                    str(marker_exc),
                    exc_info=True,
                )
            extra["persistence_committed"] = critical_persistence_committed
            extra["persisted_message_count"] = int(persisted_message_count or 0)

        extra["__post_done_callback__"] = lambda final_result=tail_result: (
            self._run_stream_post_persist_tail(
                final_result=final_result,
                extra=extra,
            )
        )
        return extra or None


__all__ = ["AgentChatStreamPersistenceOrchestrator"]
