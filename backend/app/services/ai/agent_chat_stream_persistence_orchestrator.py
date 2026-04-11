"""Stream persistence orchestrator for AgentChatService."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import Any

from app.ai.engine.types import ExecutionResult
from app.ai.events.hooks import HookPoint
from app.ai.json_safe import normalize_json_safe, normalize_json_safe_dict
from app.ai.utils.token_estimator import estimate_tokens
from app.core.i18n import _
from app.core.logging import LogManager
from app.enums.agent import MessageRoleEnum
from app.services.ai.agent_chat_stream_runtime_dependencies import (
    AgentChatStreamPersistenceDependencies,
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
        build_context_diagnostics: Callable[[ExecutionResult], dict[str, Any]],
        build_last_run_summary: Callable[[ExecutionResult], dict[str, Any]],
        assistant_message_has_visible_reply_payload: Callable[[dict[str, Any]], bool],
        friendly_stream_error_text: Callable[..., str],
        build_stream_error_display: Callable[..., dict[str, Any]],
        runtime_dependencies:
            AgentChatStreamPersistenceDependencies
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
    def _has_stream_contract(service: Any, method_name: str) -> bool:
        return callable(getattr(type(service), method_name, None))

    async def _persist_stream_last_error_marker(
        self,
        *,
        error_type: str,
        error_message: str,
        friendly_message: str,
        partial: bool,
        extra_payload: dict[str, Any] | None = None,
    ) -> bool:
        deps = self._deps()
        async with deps.session_factory() as marker_db:
            marker_conv_svc = deps.conversation_service_cls(marker_db, self.tenant_id)
            if self._has_stream_contract(
                marker_conv_svc,
                "persist_stream_last_error_marker",
            ):
                return await marker_conv_svc.persist_stream_last_error_marker(
                    conversation_id=self.conversation_id,
                    error_type=error_type,
                    error_message=error_message,
                    friendly_message=friendly_message,
                    partial=partial,
                    extra_payload=extra_payload,
                )
            marker_conv = await marker_conv_svc.repo.get_by_id(self.conversation_id)
            if marker_conv is None:
                logger.warning(
                    "Skip stream error marker because conversation is missing: conversation_id={}",
                    self.conversation_id,
                )
                return False

            conversation_metadata = dict(marker_conv.metadata_ or {})
            marker_payload: dict[str, Any] = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "error_type": error_type,
                "error_message": str(error_message or "")[:500],
                "friendly_message": friendly_message,
                "partial": bool(partial),
            }
            if isinstance(extra_payload, dict) and extra_payload:
                marker_payload["details"] = normalize_json_safe(extra_payload)
            conversation_metadata["last_error"] = marker_payload
            marker_conv.metadata_ = normalize_json_safe_dict(conversation_metadata) or {}
            await marker_db.commit()
            return True

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
        deps = self._deps()
        async with deps.session_factory() as err_db:
            err_conv_svc = deps.conversation_service_cls(err_db, self.tenant_id)
            if self._has_stream_contract(err_conv_svc, "save_stream_error_message"):
                return await err_conv_svc.save_stream_error_message(
                    conversation_id=self.conversation_id,
                    error_text=error_text,
                    user_message=user_message,
                    result=result,
                    context_diagnostics_payload=context_diagnostics_payload,
                    last_run_summary_payload=last_run_summary_payload,
                    persist_user_message=persist_user_message,
                    agent_id=self.agent_id,
                    build_stream_error_display=self.build_stream_error_display,
                )
            err_conv = await err_conv_svc.repo.get_by_id(self.conversation_id)
            if err_conv is None:
                logger.warning(
                    "Skip stream error persistence because conversation is missing: conversation_id={}",
                    self.conversation_id,
                )
                return 0

            current_count = await err_conv_svc.message_repo.count_by_conversation(
                self.conversation_id
            )
            next_seq = await err_conv_svc.message_repo.get_next_sequence(
                self.conversation_id
            )
            persisted_rows = 0
            error_display = self.build_stream_error_display(
                result.error or error_text,
                failure_kind=str(
                    getattr(result, "provider_failure_kind", "") or ""
                ).strip()
                or None,
            )
            error_message = str(
                error_display.get("message") or error_text or _("common.server_error")
            ).strip() or _("common.server_error")
            normalized_user_message = str(user_message or "").strip()
            if persist_user_message and normalized_user_message:
                await err_conv_svc.message_repo.create(
                    {
                        "tenant_id": self.tenant_id,
                        "conversation_id": self.conversation_id,
                        "role": MessageRoleEnum.USER.value,
                        "content": normalized_user_message,
                        "sequence": next_seq,
                        "token_count": estimate_tokens(normalized_user_message),
                        "agent_id": None,
                        "model_id": None,
                        "metadata_": normalize_json_safe_dict(
                            {
                                "recovered_from_failed_stream": True,
                                "stream_error_recovered": True,
                            }
                        )
                        or {},
                    }
                )
                next_seq += 1
                persisted_rows += 1

            error_metadata: dict[str, Any] = {
                "error": True,
                "error_debug_message": error_display.get("debug_message"),
                "error_message": error_message,
                "error_only": bool(error_display.get("error_only")),
                "error_trace_id": error_display.get("trace_id"),
                "error_type": error_display.get("error_type") or "stream_execution_error",
                "raw_error_message": str(result.error or "")[:500],
                "partial_output": result.output or "",
                "total_tokens": result.total_tokens or 0,
                "duration_ms": result.duration_ms or 0,
                "user_message_preview": (user_message or "")[:200],
            }
            if context_diagnostics_payload:
                error_metadata["context_diagnostics"] = normalize_json_safe(
                    context_diagnostics_payload
                )
            if last_run_summary_payload:
                error_metadata["last_run_summary"] = normalize_json_safe(
                    last_run_summary_payload
                )
            error_metadata = normalize_json_safe_dict(error_metadata) or {}

            await err_conv_svc.message_repo.create(
                {
                    "tenant_id": self.tenant_id,
                    "conversation_id": self.conversation_id,
                    "role": MessageRoleEnum.ASSISTANT.value,
                    "content": error_message,
                    "sequence": next_seq,
                    "token_count": estimate_tokens(error_message),
                    "agent_id": self.agent_id,
                    "model_id": result.runtime_model_id,
                    "metadata_": error_metadata,
                }
            )
            persisted_rows += 1

            conversation_metadata = dict(err_conv.metadata_ or {})
            conversation_metadata["last_error"] = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "debug_message": error_display.get("debug_message"),
                "error_message": str(result.error or "")[:500],
                "error_type": error_display.get("error_type") or "stream_execution_error",
                "friendly_message": error_message,
                "partial": bool(result.partial),
                "trace_id": error_display.get("trace_id"),
            }
            if persisted_rows:
                err_conv.message_count = max(
                    int(getattr(err_conv, "message_count", 0) or 0),
                    int(current_count or 0),
                ) + persisted_rows
            err_conv.metadata_ = normalize_json_safe_dict(conversation_metadata) or {}
            await err_db.commit()
            logger.info(
                "Stream error message saved: conversation_id={} error_type=stream_execution_error",
                self.conversation_id,
            )
            return int(persisted_rows or 0)

    async def _run_stream_post_persist_tail(
        self,
        *,
        final_result: ExecutionResult,
        extra: dict[str, Any],
    ) -> None:
        try:
            try:
                await self._deps().record_chat_stats(
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
                        deps = self._deps()
                        async with deps.session_factory() as mem_db:
                            try:
                                mem_conv_svc = deps.conversation_service_cls(
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
                    logger.warning(
                        "Persist stream session memory failed: tenant={} conversation={} err={}",
                        self.tenant_id,
                        self.conversation_id,
                        str(mem_exc),
                    )

            actual_tokens = final_result.total_tokens or 0
            await self._deps().adjust_usage(
                tenant_id=self.tenant_id,
                agent_id=self.agent_id,
                estimated_tokens=self.estimated_tokens,
                actual_tokens=actual_tokens,
                config=self.quota_config,
            )

            if self.user_id and actual_tokens > 0:
                await self._deps().record_user_usage(
                    tenant_id=self.tenant_id,
                    agent_id=self.agent_id,
                    user_id=self.user_id,
                    tokens=actual_tokens,
                )

            if self.hook_registry.has_hooks(HookPoint.AFTER_AGENT_CHAT):
                hook_ctx = await self.hook_registry.trigger(
                    HookPoint.AFTER_AGENT_CHAT,
                    tenant_id=self.tenant_id,
                    agent_id=self.agent_id,
                    response=final_result.output,
                    total_tokens=final_result.total_tokens,
                )
                if "response" in hook_ctx and hook_ctx["response"] != final_result.output:
                    final_result.output = hook_ctx["response"]

            await self.hook_registry.trigger(
                HookPoint.AFTER_EXECUTE,
                tenant_id=self.tenant_id,
                agent_id=self.agent_id,
                result=final_result,
            )

            if final_result.success:
                await self._deps().publish_execution_completed(
                    self.request,
                    self.agent,
                    final_result,
                )
            else:
                await self._deps().publish_execution_failed(
                    self.request,
                    self.agent,
                    final_result.error or "",
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
                await self._deps().release_concurrency(
                    tenant_id=self.tenant_id,
                    agent_id=self.agent_id,
                    lock_token=self.lock_token,
                )

    async def __call__(self, result: ExecutionResult) -> dict[str, Any] | None:
        extra: dict[str, Any] = {}
        persisted_message_count = 0
        context_diagnostics_payload: dict[str, Any] = {}
        last_run_summary_payload: dict[str, Any] = {}
        system_count = 0
        error_message_persisted = False
        critical_persistence_committed = False
        last_error_marker_persisted = False
        tail_result = result

        try:
            context_diagnostics_payload = self.build_context_diagnostics(result)
            last_run_summary_payload = self.build_last_run_summary(result)

            system_count = sum(
                1 for m in (result.messages or []) if m.get("role") == "system"
            )
            has_new_messages = (result.messages or []) and len(
                result.messages
            ) > system_count + self.history_count
            if result.success or has_new_messages:
                try:
                    deps = self._deps()
                    async with deps.session_factory() as cb_db:
                        try:
                            cb_conv_svc = deps.conversation_service_cls(
                                cb_db,
                                self.tenant_id,
                            )
                            if self._has_stream_contract(
                                cb_conv_svc,
                                "persist_stream_completion",
                            ):
                                persisted_message_count = (
                                    await cb_conv_svc.persist_stream_completion(
                                        conversation_id=self.conversation_id,
                                        result=result,
                                        history_count=self.history_count,
                                        agent_id=self.agent_id,
                                        route_source=self.route_source,
                                        context_diagnostics=context_diagnostics_payload,
                                        last_run_summary=last_run_summary_payload,
                                        current_agent=self.agent,
                                    )
                                )
                            else:
                                cb_conv = await cb_conv_svc.repo.get_by_id(
                                    self.conversation_id
                                )
                                _persisted_tool_calls, persisted_message_count = (
                                    await cb_conv_svc.persist_chat_messages(
                                        conversation=cb_conv,
                                        result=result,
                                        history_count=self.history_count,
                                        agent_id=self.agent_id,
                                        route_source=self.route_source,
                                        context_diagnostics=context_diagnostics_payload,
                                        last_run_summary=last_run_summary_payload,
                                    )
                                )
                                await cb_conv_svc.update_stats(
                                    cb_conv,
                                    result,
                                    current_agent=self.agent,
                                )
                                await cb_db.commit()
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
                    persist_failure_result = ExecutionResult(
                        **{
                            **result.__dict__,
                            "error": str(persist_exc),
                            "provider_failure_kind": "none",
                        }
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
                            marker_persisted = await self._persist_stream_last_error_marker(
                                error_type="stream_on_complete_persistence_error",
                                error_message=str(fallback_exc),
                                friendly_message=_("common.server_error"),
                                partial=bool(result.partial),
                                extra_payload={
                                    "stage": "persist_chat_messages",
                                    "original_error": str(persist_exc)[:500],
                                    "fallback_error": str(fallback_exc)[:500],
                                },
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

            new_start = system_count + self.history_count
            new_messages_raw = (result.messages or [])[new_start:]
            user_message_count = sum(1 for m in new_messages_raw if m.get("role") == "user")
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
            fallback_result = ExecutionResult(
                **{
                    **result.__dict__,
                    "error": str(on_complete_exc),
                    "provider_failure_kind": "none",
                }
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
                        "context_diagnostics_present": bool(context_diagnostics_payload),
                        "last_run_summary_present": bool(last_run_summary_payload),
                    },
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

        extra["__post_done_callback__"] = (
            lambda final_result=tail_result: self._run_stream_post_persist_tail(
                final_result=final_result,
                extra=extra,
            )
        )
        return extra or None


__all__ = ["AgentChatStreamPersistenceOrchestrator"]
