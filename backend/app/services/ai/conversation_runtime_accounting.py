"""
Focused metering and audit collaborators for ConversationEngine runtime-v2 turns.
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, is_dataclass
from typing import Any

from app.ai.engine.conversation_helpers import await_if_needed as _await_if_needed
from app.ai.engine.conversation_runtime_preflight import ConversationRuntimeContext
from app.ai.engine.types import ToolUsePolicy
from app.ai.runtime.usage_metrics import CostCalculator
from app.ai.types import ChatMessage
from app.ai.usage_mode import resolve_chat_usage
from app.ai.usage_recorder import UsageRecorder
from app.core.logging import LogManager
from app.enums.ai import CallStatusEnum, RequestTypeEnum

logger = LogManager.get_logger("ai.engine.conversation")


@dataclass
class ConversationRuntimeAuditContext:
    tenant_id: int | None
    user_id: int | None
    log_user_type: str | None
    agent_id: int | None
    conversation_id: int | None
    billing_context: dict[str, Any] | None
    context_sources: list[dict[str, Any]]


@dataclass
class ConversationRuntimeRequestContext:
    messages: list[ChatMessage]
    temperature: float
    max_tokens: int | None
    top_p: float
    openai_tools: list[dict[str, Any]] | None
    effective_tool_choice: str | None
    selected_tool_names: list[str]
    all_tool_names: list[str]
    tool_use_policy: ToolUsePolicy
    breach_retry_result: str | None = None
    request_log_data: dict[str, Any] | None = None


@dataclass
class ConversationRuntimeUsageSummary:
    input_tokens: int
    output_tokens: int
    total_tokens: int
    usage_mode: str
    cost: float
    latency_ms: int


class ConversationRuntimeAccounting:
    """
    Handle runtime-v2 usage resolution, metering, and audit logging.
    """

    def __init__(
        self,
        *,
        gateway: Any,
        db: Any,
        cost_calculator: Any = CostCalculator,
    ) -> None:
        self.gateway = gateway
        self.db = db
        self.cost_calculator = cost_calculator

    async def log_failure(
        self,
        *,
        error: Exception,
        start_time: float,
        runtime_context: ConversationRuntimeContext,
        request_context: ConversationRuntimeRequestContext,
        audit_context: ConversationRuntimeAuditContext,
        turn_record: Any,
        failure_log_message: str,
    ) -> None:
        if (
            not runtime_context.should_record_call_log
            or runtime_context.ai_model is None
        ):
            return
        turn_record_payload = self._normalize_turn_record_payload(turn_record)
        try:
            await _await_if_needed(
                self.gateway.usage_recorder.log_call_failure(
                    error=error,
                    start_time=start_time,
                    provider=runtime_context.provider,
                    model=runtime_context.model_code,
                    model_id=runtime_context.ai_model.id,
                    messages=request_context.messages,
                    temperature=request_context.temperature,
                    max_tokens=request_context.max_tokens,
                    top_p=request_context.top_p,
                    tools=request_context.openai_tools,
                    tool_choice=request_context.effective_tool_choice,
                    selected_tool_names=request_context.selected_tool_names,
                    all_tool_names=request_context.all_tool_names,
                    tool_use_policy_family=request_context.tool_use_policy.family,
                    tool_use_policy_mode=request_context.tool_use_policy.mode,
                    allowed_tool_names=request_context.tool_use_policy.allowed_tool_names,
                    breach_retry_result=request_context.breach_retry_result,
                    request_type=RequestTypeEnum.CHAT.value,
                    tenant_id=audit_context.tenant_id,
                    user_id=audit_context.user_id,
                    user_type=audit_context.log_user_type,
                    agent_id=audit_context.agent_id,
                    conversation_id=audit_context.conversation_id,
                    billing_context=self._merged_billing_context(
                        runtime_context=runtime_context,
                        billing_context=audit_context.billing_context,
                    ),
                    call_type="main_chat",
                    turn_record=turn_record_payload,
                    protocol_path=self._extract_protocol_path(
                        turn_record=turn_record,
                        turn_record_payload=turn_record_payload,
                    ),
                    context_sources=audit_context.context_sources,
                    routed_model_id=runtime_context.routed_model_id,
                    route_reason=runtime_context.route_reason,
                )
            )
        except Exception as log_exc:
            logger.error(
                "{}: provider={} model={} conversation={} error={}",
                failure_log_message,
                runtime_context.provider.code,
                runtime_context.model_code,
                audit_context.conversation_id,
                str(log_exc),
            )

    async def finalize_success(
        self,
        *,
        runtime_context: ConversationRuntimeContext,
        request_context: ConversationRuntimeRequestContext,
        audit_context: ConversationRuntimeAuditContext,
        output_text: str,
        input_tokens: int | None,
        output_tokens: int | None,
        total_tokens: int | None,
        start_time: float,
        turn_record: Any,
        success_log_message: str,
        flush_db: bool = False,
        require_estimated_input_for_metering: bool = False,
    ) -> ConversationRuntimeUsageSummary:
        summary = self._resolve_usage_summary(
            runtime_context=runtime_context,
            request_context=request_context,
            output_text=output_text,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            start_time=start_time,
        )
        await self._record_metered_usage(
            runtime_context=runtime_context,
            audit_context=audit_context,
            summary=summary,
            require_estimated_input=require_estimated_input_for_metering,
        )
        runtime_context.api_key.increment_usage()
        if flush_db:
            await _await_if_needed(self.db.flush())
        await self._log_success_call(
            runtime_context=runtime_context,
            request_context=request_context,
            audit_context=audit_context,
            summary=summary,
            turn_record=turn_record,
            success_log_message=success_log_message,
        )
        return summary

    def _resolve_usage_summary(
        self,
        *,
        runtime_context: ConversationRuntimeContext,
        request_context: ConversationRuntimeRequestContext,
        output_text: str,
        input_tokens: int | None,
        output_tokens: int | None,
        total_tokens: int | None,
        start_time: float,
    ) -> ConversationRuntimeUsageSummary:
        resolved_usage = resolve_chat_usage(
            messages=request_context.messages,
            output_text=output_text,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            estimated_input=runtime_context.estimated_input,
        )
        resolved_input_tokens = resolved_usage.input_tokens
        resolved_output_tokens = resolved_usage.output_tokens
        resolved_total_tokens = resolved_usage.total_tokens
        cost = (
            self.cost_calculator.calculate_cost(
                runtime_context.ai_model,
                resolved_input_tokens,
                resolved_output_tokens,
            )
            if runtime_context.ai_model
            else 0.0
        )
        latency_ms = int(self._elapsed_seconds(start_time) * 1000)
        return ConversationRuntimeUsageSummary(
            input_tokens=resolved_input_tokens,
            output_tokens=resolved_output_tokens,
            total_tokens=resolved_total_tokens,
            usage_mode=resolved_usage.usage_mode,
            cost=cost,
            latency_ms=latency_ms,
        )

    async def _record_metered_usage(
        self,
        *,
        runtime_context: ConversationRuntimeContext,
        audit_context: ConversationRuntimeAuditContext,
        summary: ConversationRuntimeUsageSummary,
        require_estimated_input: bool,
    ) -> None:
        should_meter = (
            runtime_context.should_meter_usage
            and runtime_context.ai_model is not None
            and audit_context.tenant_id is not None
        )
        if require_estimated_input:
            should_meter = should_meter and runtime_context.estimated_input > 0
        if not should_meter:
            return
        await _await_if_needed(
            self.gateway.usage_recorder.record_usage_and_adjust(
                tenant_id=audit_context.tenant_id,
                model_id=runtime_context.ai_model.id,
                request_type=RequestTypeEnum.CHAT.value,
                input_tokens=summary.input_tokens,
                output_tokens=summary.output_tokens,
                total_tokens=summary.total_tokens,
                cost=summary.cost,
                estimated_input=runtime_context.estimated_input,
                latency_ms=summary.latency_ms,
                user_id=audit_context.user_id,
                metering_context=runtime_context.metering_context,
            )
        )

    async def _log_success_call(
        self,
        *,
        runtime_context: ConversationRuntimeContext,
        request_context: ConversationRuntimeRequestContext,
        audit_context: ConversationRuntimeAuditContext,
        summary: ConversationRuntimeUsageSummary,
        turn_record: Any,
        success_log_message: str,
    ) -> None:
        if (
            not runtime_context.should_record_call_log
            or runtime_context.ai_model is None
            or audit_context.tenant_id is None
        ):
            return
        turn_record_payload = self._normalize_turn_record_payload(turn_record)
        try:
            await _await_if_needed(
                self.gateway.usage_recorder.call_log_service.log_call_async(
                    tenant_id=audit_context.tenant_id,
                    model_id=runtime_context.ai_model.id,
                    provider_id=runtime_context.provider.id,
                    request_type=RequestTypeEnum.CHAT.value,
                    request_data=dict(request_context.request_log_data or {}),
                    response_data={
                        "input_tokens": summary.input_tokens,
                        "output_tokens": summary.output_tokens,
                        "total_tokens": summary.total_tokens,
                        "model": runtime_context.model_code,
                        "usage_mode": summary.usage_mode,
                    },
                    input_tokens=summary.input_tokens,
                    output_tokens=summary.output_tokens,
                    total_tokens=summary.total_tokens,
                    cost=summary.cost,
                    latency_ms=summary.latency_ms,
                    status=CallStatusEnum.SUCCESS.value,
                    user_id=audit_context.user_id,
                    user_type=UsageRecorder._resolve_call_user_type(
                        audit_context.tenant_id,
                        audit_context.log_user_type,
                    ),
                    agent_id=audit_context.agent_id,
                    conversation_id=audit_context.conversation_id,
                    billing_context=self._merged_billing_context(
                        runtime_context=runtime_context,
                        billing_context=audit_context.billing_context,
                    ),
                    call_type="main_chat",
                    turn_record=turn_record_payload,
                    protocol_path=self._extract_protocol_path(
                        turn_record=turn_record,
                        turn_record_payload=turn_record_payload,
                    ),
                    context_sources=audit_context.context_sources,
                    routed_model_id=runtime_context.routed_model_id,
                    route_reason=runtime_context.route_reason,
                )
            )
        except Exception as log_exc:
            logger.error("{}: {}", success_log_message, str(log_exc))

    def _merged_billing_context(
        self,
        *,
        runtime_context: ConversationRuntimeContext,
        billing_context: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        return self.gateway._merge_model_provider_snapshots(
            billing_context,
            provider=runtime_context.provider,
            ai_model=runtime_context.ai_model,
        )

    @staticmethod
    def _normalize_turn_record_payload(turn_record: Any) -> dict[str, Any] | None:
        if turn_record is None:
            return None
        if isinstance(turn_record, dict):
            return dict(turn_record)
        if is_dataclass(turn_record):
            return asdict(turn_record)
        if hasattr(turn_record, "__dict__"):
            return dict(getattr(turn_record, "__dict__", {}) or {})
        return None

    @staticmethod
    def _extract_protocol_path(
        *,
        turn_record: Any,
        turn_record_payload: dict[str, Any] | None,
    ) -> str | None:
        payload_path = str(
            (turn_record_payload or {}).get("protocol_path") or ""
        ).strip()
        if payload_path:
            return payload_path
        value = getattr(turn_record, "protocol_path", None)
        text = str(value or "").strip()
        return text or None

    @staticmethod
    def _elapsed_seconds(start_time: float) -> float:
        wall_elapsed = time.time() - start_time
        monotonic_elapsed = time.perf_counter() - start_time
        candidates = [
            elapsed for elapsed in (wall_elapsed, monotonic_elapsed) if elapsed >= 0
        ]
        return min(candidates) if candidates else 0.0


__all__ = [
    "ConversationRuntimeAccounting",
    "ConversationRuntimeAuditContext",
    "ConversationRuntimeRequestContext",
    "ConversationRuntimeUsageSummary",
]
