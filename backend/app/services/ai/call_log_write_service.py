"""
Call log write-side helpers.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.configs.service import PLATFORM_TENANT_ID
from app.core.logging import LogManager
from app.enums.ai import CallStatusEnum, CallTypeEnum
from app.models.ai import AICallLog

logger = LogManager.get_logger("ai.call_log")


def _active_transaction_event_target(db: Any) -> Session | None:
    if isinstance(db, AsyncSession):
        return db.sync_session if db.in_transaction() else None
    if isinstance(db, Session):
        return db if db.in_transaction() else None
    return None


def _enqueue_call_log_task(task: Any, task_kwargs: dict[str, Any], db: Any) -> None:
    event_target = _active_transaction_event_target(db)
    if event_target is None:
        task.delay(**task_kwargs)
        return

    # 中文: 等当前事务提交后再投递任务，避免 worker 先于会话/消息外键可见性写入日志。
    # EN: Queue after commit so the worker never writes call logs before FK rows are visible.
    def _after_commit(_session: Session) -> None:
        try:
            task.delay(**task_kwargs)
        except Exception as exc:  # noqa: BLE001
            logger.error("Deferred AI call log enqueue failed: {}", str(exc))

    event.listen(event_target, "after_commit", _after_commit, once=True)


class CallLogWriteServiceMixin:
    async def _build_caller_snapshot(
        self,
        *,
        tenant_id: int,
        user_id: int | None,
        user_type: str | None,
        billing_context: dict[str, Any],
    ) -> dict[str, Any] | None:
        actor_user_id = self._normalize_optional_fk_id(
            billing_context.get("actor_user_id", user_id)
        )
        actor_user_type = billing_context.get("actor_user_type", user_type)
        if not actor_user_id or not actor_user_type:
            return None
        load_snapshot = self._load_identity_snapshot()
        return await load_snapshot(
            self.db,
            user_type=actor_user_type,
            user_id=actor_user_id,
            tenant_id=None if tenant_id == PLATFORM_TENANT_ID else tenant_id,
        )

    async def log_call(
        self,
        tenant_id: int,
        model_id: int,
        provider_id: int,
        request_type: str,
        request_data: dict,
        response_data: dict | None,
        input_tokens: int,
        output_tokens: int,
        total_tokens: int,
        cost: float,
        latency_ms: int,
        status: str = CallStatusEnum.SUCCESS.value,
        error_message: str | None = None,
        user_id: int | None = None,
        user_type: str | None = None,
        agent_id: int | None = None,
        conversation_id: int | None = None,
        billing_context: dict[str, Any] | None = None,
        routed_model_id: int | None = None,
        route_reason: str | None = None,
        trace_id: str | None = None,
        tool_call_id: str | None = None,
        turn_record: dict[str, Any] | None = None,
        protocol_path: str | None = None,
        context_sources: list[dict[str, Any]] | None = None,
        selected_tool_names: list[str] | None = None,
        selected_skill_names: list[str] | None = None,
        fallback_history: list[dict[str, Any]] | None = None,
        sync_rescue: bool | None = None,
        should_record_call_log: bool | None = None,
        call_type: str = CallTypeEnum.MAIN_CHAT.value,
    ) -> AICallLog:
        request_payload = self._inject_turn_hints(
            request_data,
            turn_record=turn_record,
            selected_tool_names=selected_tool_names,
            selected_skill_names=selected_skill_names,
            protocol_path=protocol_path,
            context_sources=context_sources,
            fallback_history=fallback_history,
            sync_rescue=sync_rescue,
            should_record_call_log=should_record_call_log,
        )
        turn_diagnostics = self._build_turn_diagnostics(
            request_data=request_payload,
            response_data=response_data,
            status=status,
            error_message=error_message,
        )
        if turn_diagnostics:
            request_payload["turn_diagnostics"] = turn_diagnostics
        if isinstance(turn_diagnostics.get("turn_record"), dict):
            request_payload["turn_record"] = turn_diagnostics["turn_record"]

        messages = request_payload.get("messages", [])
        temperature = request_payload.get("temperature", 0.7)
        tools = request_payload.get("tools")
        tool_choice = request_payload.get("tool_choice")
        request_hash = self._generate_request_hash(
            model_id,
            messages,
            temperature,
            tools,
            tool_choice=tool_choice,
        )

        billing_context = dict(billing_context or {})
        normalized_latency_ms = self._normalize_latency_ms(latency_ms)
        eff_trace = self._normalize_trace_for_call_log(trace_id, use_context_var=True)
        eff_tool = self._normalize_tool_call_id_for_call_log(tool_call_id)
        eff_call_type = self._normalize_call_type_for_call_log(call_type)
        normalized_user_id = self._normalize_optional_fk_id(user_id)
        normalized_agent_id = self._normalize_optional_fk_id(agent_id)
        normalized_conversation_id = self._normalize_optional_fk_id(conversation_id)
        normalized_routed_model_id = self._normalize_optional_fk_id(routed_model_id)
        caller_snapshot = await self._build_caller_snapshot(
            tenant_id=tenant_id,
            user_id=normalized_user_id,
            user_type=user_type,
            billing_context=billing_context,
        )
        if caller_snapshot:
            billing_context["caller_snapshot"] = caller_snapshot
        request_metadata = self._build_request_metadata_payload(
            request_data=request_payload,
            response_data=response_data,
            turn_diagnostics=turn_diagnostics,
            agent_id=normalized_agent_id,
            conversation_id=normalized_conversation_id,
            routed_model_id=normalized_routed_model_id,
            route_reason=route_reason,
            caller_snapshot=caller_snapshot,
        )
        call_log = AICallLog(
            tenant_id=tenant_id,
            user_id=normalized_user_id,
            user_type=user_type,
            billing_tenant_id=self._normalize_optional_fk_id(
                billing_context.get("billing_tenant_id")
            ),
            actor_user_id=self._normalize_optional_fk_id(
                billing_context.get("actor_user_id", normalized_user_id)
            ),
            actor_user_type=billing_context.get("actor_user_type", user_type),
            access_channel=billing_context.get("access_channel"),
            agent_id=normalized_agent_id,
            conversation_id=normalized_conversation_id,
            trace_id=eff_trace,
            tool_call_id=eff_tool,
            provider_id=provider_id,
            model_id=model_id,
            request_type=request_type,
            call_type=eff_call_type,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            cost=cost,
            latency_ms=normalized_latency_ms,
            status=status,
            error_message=error_message,
            request_hash=request_hash,
            request_metadata=request_metadata,
            routed_model_id=normalized_routed_model_id,
            route_reason=route_reason,
            agent_owner_type=billing_context.get("agent_owner_type"),
            agent_owner_tenant_id=self._normalize_optional_fk_id(
                billing_context.get("agent_owner_tenant_id")
            ),
            agent_resource_scope=billing_context.get("agent_resource_scope"),
            tenant_publication_id=self._normalize_optional_fk_id(
                billing_context.get("tenant_publication_id")
            ),
            publication_enabled_snapshot=billing_context.get(
                "publication_enabled_snapshot"
            ),
            publication_access_type_snapshot=billing_context.get(
                "publication_access_type_snapshot"
            ),
            agent_id_snapshot=self._normalize_optional_fk_id(
                billing_context.get("agent_id_snapshot", normalized_agent_id)
            ),
            agent_name_snapshot=billing_context.get("agent_name_snapshot"),
            billing_tenant_name_snapshot=billing_context.get(
                "billing_tenant_name_snapshot"
            ),
            model_name_snapshot=billing_context.get("model_name_snapshot"),
            provider_name_snapshot=billing_context.get("provider_name_snapshot"),
        )

        self.db.add(call_log)
        await self.db.flush()

        logger.info(
            "AI call logged | tenant_id={} model_id={} total_tokens={} cost={} status={}",
            tenant_id,
            model_id,
            total_tokens,
            cost,
            status,
        )

        return call_log

    async def log_call_async(
        self,
        tenant_id: int,
        model_id: int,
        provider_id: int,
        request_type: str,
        request_data: dict,
        response_data: dict | None,
        input_tokens: int,
        output_tokens: int,
        total_tokens: int,
        cost: float,
        latency_ms: int,
        status: str = CallStatusEnum.SUCCESS.value,
        error_message: str | None = None,
        user_id: int | None = None,
        user_type: str | None = None,
        agent_id: int | None = None,
        conversation_id: int | None = None,
        billing_context: dict[str, Any] | None = None,
        routed_model_id: int | None = None,
        route_reason: str | None = None,
        trace_id: str | None = None,
        tool_call_id: str | None = None,
        turn_record: dict[str, Any] | None = None,
        protocol_path: str | None = None,
        context_sources: list[dict[str, Any]] | None = None,
        selected_tool_names: list[str] | None = None,
        selected_skill_names: list[str] | None = None,
        fallback_history: list[dict[str, Any]] | None = None,
        sync_rescue: bool | None = None,
        should_record_call_log: bool | None = None,
        call_type: str = CallTypeEnum.MAIN_CHAT.value,
    ):
        from app.tasks.ai import log_ai_call_task

        normalized_latency_ms = self._normalize_latency_ms(latency_ms)
        eff_trace = self._normalize_trace_for_call_log(trace_id, use_context_var=True)
        eff_tool = self._normalize_tool_call_id_for_call_log(tool_call_id)
        eff_call_type = self._normalize_call_type_for_call_log(call_type)
        normalized_user_id = self._normalize_optional_fk_id(user_id)
        normalized_agent_id = self._normalize_optional_fk_id(agent_id)
        normalized_conversation_id = self._normalize_optional_fk_id(conversation_id)
        normalized_routed_model_id = self._normalize_optional_fk_id(routed_model_id)
        billing_context = dict(billing_context or {})
        caller_snapshot = await self._build_caller_snapshot(
            tenant_id=tenant_id,
            user_id=normalized_user_id,
            user_type=user_type,
            billing_context=billing_context,
        )
        if caller_snapshot:
            billing_context["caller_snapshot"] = caller_snapshot
        request_payload = self._inject_turn_hints(
            request_data,
            turn_record=turn_record,
            selected_tool_names=selected_tool_names,
            selected_skill_names=selected_skill_names,
            protocol_path=protocol_path,
            context_sources=context_sources,
            fallback_history=fallback_history,
            sync_rescue=sync_rescue,
            should_record_call_log=should_record_call_log,
        )
        turn_diagnostics = self._build_turn_diagnostics(
            request_data=request_payload,
            response_data=response_data,
            status=status,
            error_message=error_message,
        )
        if turn_diagnostics:
            request_payload["turn_diagnostics"] = turn_diagnostics
        if isinstance(turn_diagnostics.get("turn_record"), dict):
            request_payload["turn_record"] = turn_diagnostics["turn_record"]

        safe_request_payload = self._sanitize_request(request_payload)
        safe_response_data = self._make_json_safe(
            self._truncate_response(response_data)
        )

        _enqueue_call_log_task(
            log_ai_call_task,
            {
                "tenant_id": tenant_id,
                "model_id": model_id,
                "provider_id": provider_id,
                "request_type": request_type,
                "request_data": safe_request_payload,
                "response_data": safe_response_data,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": total_tokens,
                "cost": float(cost),
                "latency_ms": normalized_latency_ms,
                "status": status,
                "error_message": error_message,
                "user_id": normalized_user_id,
                "user_type": user_type,
                "agent_id": normalized_agent_id,
                "conversation_id": normalized_conversation_id,
                "billing_context": billing_context,
                "routed_model_id": normalized_routed_model_id,
                "route_reason": route_reason,
                "trace_id": eff_trace,
                "tool_call_id": eff_tool,
                "call_type": eff_call_type,
            },
            self.db,
        )

        logger.debug(
            "AI call log queued | tenant_id={} model_id={}",
            tenant_id,
            model_id,
        )


__all__ = ["CallLogWriteServiceMixin"]
