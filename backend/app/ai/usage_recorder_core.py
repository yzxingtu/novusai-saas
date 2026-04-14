"""
AI Usage Recorder. / AI 使用量记录器。

Handles rate/quota checks, quota adjustment, and call logging.
Extracted from AIGateway to reduce God Object complexity.
负责速率/配额检查、配额调整、调用日志。
从 AIGateway 提取，降低 God Object 复杂度。
"""

from __future__ import annotations

import dataclasses
import time
from datetime import date
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.quota import QuotaExceeded, QuotaManager
from app.ai.rate_limiter import (
    RateLimiter,
    RateLimitExceeded,
    RateLimitReservation,
)
from app.ai.types import (
    ChatMessage,
    messages_to_dicts,
)
from app.ai.usage_recorder_context import UsageMeteringContext
from app.ai.usage_recorder_support import (
    elapsed_milliseconds,
    inject_turn_diagnostics,
    normalize_context_sources,
    normalize_fallback_history,
    normalize_string_list,
    normalize_turn_record_payload,
    pick_first_bool,
    serialize_chat_response,
)
from app.configs.service import PLATFORM_TENANT_ID
from app.core.logging import LogManager
from app.core.runtime_identity import get_runtime_identity_tag
from app.enums.ai import CallStatusEnum, CallTypeEnum, RequestTypeEnum
from app.enums.log import UserTypeEnum as LogUserTypeEnum
from app.models.ai import AIModel, AIProvider, ProviderApiKey
from app.services.ai.call_log_service import CallLogService

logger = LogManager.get_logger("ai")


class UsageRecorder:
    """
    AI Usage Recorder / AI 使用量记录器

    Responsibilities / 职责：
    - Rate limit + quota check / 速率限制 + 配额检查
    - TPM/quota correction / TPM/配额校正
    - Call logging (success/failure) / 调用日志（成功/失败）
    - Stream completion callback / 流式完成回调
    - ChatResponse serialization / ChatResponse 序列化
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.quota_manager = QuotaManager(db)
        self.call_log_service = CallLogService(db)

    @staticmethod
    def _should_meter_usage(tenant_id: int | None) -> bool:
        return tenant_id is not None and tenant_id > PLATFORM_TENANT_ID

    @staticmethod
    def _should_record_call_log(tenant_id: int | None) -> bool:
        return tenant_id is not None

    @staticmethod
    def _resolve_call_user_type(
        tenant_id: int | None,
        user_type: str | None = None,
    ) -> str | None:
        if user_type:
            return user_type
        if tenant_id is None:
            return None
        if tenant_id == PLATFORM_TENANT_ID:
            return LogUserTypeEnum.ADMIN.value
        return LogUserTypeEnum.TENANT_ADMIN.value

    _elapsed_milliseconds = staticmethod(elapsed_milliseconds)
    _normalize_turn_record_payload = staticmethod(normalize_turn_record_payload)
    _normalize_string_list = staticmethod(normalize_string_list)
    _pick_first_bool = staticmethod(pick_first_bool)
    _normalize_context_sources = staticmethod(normalize_context_sources)
    _normalize_fallback_history = staticmethod(normalize_fallback_history)
    _inject_turn_diagnostics = staticmethod(inject_turn_diagnostics)

    async def check_rate_and_quota(
        self,
        tenant_id: int,
        model_id: int,
        ai_model: AIModel,
        estimated_tokens: int,
    ) -> UsageMeteringContext:
        """
        Atomic rate limit + quota check (executed only for tenant calls). / 原子检查速率限制 + 配额（仅企业调用时执行）。

        Rate limit priority: tenant custom > model default.
        速率限制优先级：企业自定义 > 模型默认值。
        """
        current_time = int(time.time())
        metering_context = UsageMeteringContext(
            request_minute_key=current_time // 60,
            request_stat_date=date.today(),
        )

        # Determine effective rate limits: prioritize tenant-specific config / 确定有效的速率限制：优先使用企业专属配置
        rpm_limit = ai_model.rpm_limit
        tpm_limit = ai_model.tpm_limit

        if tenant_id:
            from app.services.ai.tenant_rate_limit_service import TenantRateLimitService

            rate_svc = TenantRateLimitService(self.db, tenant_id)
            effective = await rate_svc.get_effective_rate_limits(model_id)
            rpm_limit = effective["rpm_limit"]
            tpm_limit = effective["tpm_limit"]

        rate_limit_reservation: RateLimitReservation | None = None
        try:
            rate_limit_reservation = await RateLimiter.check_and_record(
                tenant_id=tenant_id,
                model_id=model_id,
                rpm_limit=rpm_limit,
                tpm_limit=tpm_limit,
                estimated_tokens=estimated_tokens,
                current_time=current_time,
            )
        except RateLimitExceeded as e:
            logger.warning(
                "Rate limit blocked: tenant={} error={}",
                tenant_id,
                str(e),
            )
            raise

        try:
            quota_check = await self.quota_manager.check_quota(
                tenant_id=tenant_id,
                model_id=model_id,
                estimated_tokens=estimated_tokens,
                request_stat_date=metering_context.request_stat_date,
            )
        except QuotaExceeded as e:
            await RateLimiter.rollback_precharge(
                reservation=rate_limit_reservation,
                estimated_tokens=estimated_tokens,
            )
            logger.warning(
                "Quota blocked: tenant={} error={}",
                tenant_id,
                str(e),
            )
            raise

        return dataclasses.replace(
            metering_context,
            quota_check=quota_check,
            rate_limit_reservation=rate_limit_reservation,
        )

    async def record_usage_and_adjust(
        self,
        tenant_id: int,
        model_id: int,
        request_type: str,
        input_tokens: int,
        output_tokens: int,
        total_tokens: int,
        cost: float,
        estimated_input: int,
        latency_ms: int,
        user_id: int | None = None,
        metering_context: UsageMeteringContext | None = None,
    ) -> None:
        """
        Adjust TPM/quota from estimated to actual. / 将 TPM/配额从预估调整为实际。
        """
        del request_type, input_tokens, output_tokens, cost, latency_ms, user_id
        context = metering_context or UsageMeteringContext(
            request_minute_key=int(time.time()) // 60,
            request_stat_date=date.today(),
        )

        if estimated_input > 0 or total_tokens > 0:
            await RateLimiter.adjust_tpm_after_response(
                tenant_id=tenant_id,
                model_id=model_id,
                estimated_tokens=estimated_input,
                actual_tokens=total_tokens,
                request_minute_key=context.request_minute_key,
            )

        await self.quota_manager.adjust_usage(
            tenant_id=tenant_id,
            model_id=model_id,
            estimated_tokens=estimated_input,
            actual_tokens=total_tokens,
            quota_result=context.quota_check,
            stat_date=context.request_stat_date,
        )

    async def log_call_failure(
        self,
        error: Exception,
        start_time: float,
        provider: AIProvider,
        model: str,
        model_id: int,
        messages: list[ChatMessage],
        temperature: float,
        max_tokens: int | None,
        top_p: float,
        tools: list[dict] | None,
        request_type: str,
        tool_choice: str | None = None,
        selected_tool_names: list[str] | None = None,
        all_tool_names: list[str] | None = None,
        tool_use_policy_family: str | None = None,
        tool_use_policy_mode: str | None = None,
        allowed_tool_names: list[str] | None = None,
        breach_retry_result: str | None = None,
        tenant_id: int | None = None,
        user_id: int | None = None,
        user_type: str | None = None,
        agent_id: int | None = None,
        conversation_id: int | None = None,
        billing_context: dict[str, Any] | None = None,
        routed_model_id: int | None = None,
        route_reason: str | None = None,
        turn_record: dict[str, Any] | None = None,
        protocol_path: str | None = None,
        context_sources: list[dict[str, Any]] | None = None,
        metering_context: UsageMeteringContext | None = None,
        call_type: str = CallTypeEnum.MAIN_CHAT.value,
    ) -> None:
        """
        记录失败调用日志到 DB（用于审计追踪）/ Log failed call to DB (for audit trail).
        """
        _ = model
        del metering_context
        if not self._should_record_call_log(tenant_id):
            return
        try:
            assert tenant_id is not None
            latency_ms = self._elapsed_milliseconds(start_time)
            request_data = {
                "messages": messages_to_dicts(messages),
                "temperature": temperature,
                "max_tokens": max_tokens,
                "top_p": top_p,
                "tools": tools,
                "tool_choice": tool_choice,
                "runtime_identity": get_runtime_identity_tag(),
                "selected_tool_names": selected_tool_names or [],
                "all_tool_names": all_tool_names or selected_tool_names or [],
                "tool_use_policy": {
                    "family": tool_use_policy_family or "none",
                    "mode": tool_use_policy_mode or ("auto" if tools else "none"),
                    "allowed_tool_names": allowed_tool_names or [],
                },
            }
            if breach_retry_result:
                request_data["breach_retry_result"] = breach_retry_result
            request_data = self._inject_turn_diagnostics(
                request_data,
                status=CallStatusEnum.FAILED.value,
                default_termination_reason="error",
                selected_tool_names=selected_tool_names,
                selected_skill_names=self._normalize_string_list(
                    (turn_record or {}).get("selected_skill_names")
                    if isinstance(turn_record, dict)
                    else []
                ),
                turn_record=turn_record,
                protocol_path=protocol_path,
                context_sources=context_sources,
                fallback_history=(
                    (turn_record or {}).get("fallback_history")
                    if isinstance(turn_record, dict)
                    else None
                ),
                sync_rescue=(
                    (turn_record or {}).get("metadata", {}).get("sync_rescue")
                    if isinstance((turn_record or {}).get("metadata"), dict)
                    else None
                ),
                should_record_call_log=True,
            )
            await self.call_log_service.log_call_async(
                tenant_id=tenant_id,
                model_id=model_id,
                provider_id=provider.id,
                request_type=request_type,
                request_data=request_data,
                response_data={"error": str(error)},
                input_tokens=0,
                output_tokens=0,
                total_tokens=0,
                cost=0,
                latency_ms=latency_ms,
                status=CallStatusEnum.FAILED.value,
                error_message=str(error),
                user_id=user_id,
                user_type=self._resolve_call_user_type(tenant_id, user_type),
                agent_id=agent_id,
                conversation_id=conversation_id,
                billing_context=billing_context,
                routed_model_id=routed_model_id,
                route_reason=route_reason,
                call_type=call_type,
                turn_record=turn_record,
                protocol_path=protocol_path,
                context_sources=context_sources,
                selected_tool_names=self._normalize_string_list(
                    request_data.get("selected_tool_names")
                ),
                selected_skill_names=self._normalize_string_list(
                    request_data.get("selected_skill_names")
                ),
                fallback_history=request_data.get("fallback_history"),
                sync_rescue=request_data.get("sync_rescue"),
                should_record_call_log=True,
            )
        except Exception as log_err:
            logger.error("Record usage failed: {}", str(log_err))

    async def on_stream_complete(
        self,
        provider: AIProvider,
        api_key: ProviderApiKey,
        model: str,
        input_tokens: int,
        output_tokens: int,
        total_tokens: int,
        cost: float = 0,
        tenant_id: int | None = None,
        user_id: int | None = None,
        user_type: str | None = None,
        model_id: int = 0,
        estimated_input: int = 0,
        latency_ms: int = 0,
        agent_id: int | None = None,
        conversation_id: int | None = None,
        billing_context: dict[str, Any] | None = None,
        routed_model_id: int | None = None,
        route_reason: str | None = None,
        turn_record: dict[str, Any] | None = None,
        protocol_path: str | None = None,
        context_sources: list[dict[str, Any]] | None = None,
        metering_context: UsageMeteringContext | None = None,
        request_data: dict[str, Any] | None = None,
        call_type: str = CallTypeEnum.MAIN_CHAT.value,
    ) -> None:
        """
        流式响应完成回调 / Stream response completion callback.

        Records logs, updates usage stats, adjusts TPM/quota.
        记录日志、更新使用统计、调整 TPM/配额。
        """
        should_meter_usage = self._should_meter_usage(tenant_id)
        should_record_call_log = self._should_record_call_log(tenant_id)

        # 与 gateway.chat 一致：先租户计量（失败则不增加 Key），再 Key；Celery 日志 best-effort
        if should_meter_usage:
            assert tenant_id is not None
            await self.record_usage_and_adjust(
                tenant_id=tenant_id,
                model_id=model_id,
                request_type=RequestTypeEnum.CHAT.value,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                cost=cost,
                estimated_input=estimated_input,
                latency_ms=latency_ms,
                user_id=user_id,
                metering_context=metering_context,
            )

        api_key.increment_usage()

        if should_record_call_log:
            try:
                assert tenant_id is not None
                request_payload = self._inject_turn_diagnostics(
                    request_data or {"_stream": True},
                    status=CallStatusEnum.SUCCESS.value,
                    default_termination_reason="completed",
                    selected_tool_names=self._normalize_string_list(
                        (request_data or {}).get("selected_tool_names")
                    ),
                    selected_skill_names=self._normalize_string_list(
                        (request_data or {}).get("selected_skill_names")
                    ),
                    turn_record=turn_record,
                    protocol_path=protocol_path,
                    context_sources=context_sources,
                    fallback_history=(
                        (turn_record or {}).get("fallback_history")
                        if isinstance(turn_record, dict)
                        else None
                    ),
                    sync_rescue=(
                        (turn_record or {}).get("metadata", {}).get("sync_rescue")
                        if isinstance((turn_record or {}).get("metadata"), dict)
                        else None
                    ),
                    should_record_call_log=True,
                )
                await self.call_log_service.log_call_async(
                    tenant_id=tenant_id,
                    model_id=model_id,
                    provider_id=provider.id,
                    request_type=RequestTypeEnum.CHAT.value,
                    request_data=request_payload,
                    response_data={
                        "input_tokens": input_tokens,
                        "output_tokens": output_tokens,
                        "total_tokens": total_tokens,
                    },
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    total_tokens=total_tokens,
                    cost=cost,
                    latency_ms=latency_ms,
                    status=CallStatusEnum.SUCCESS.value,
                    user_id=user_id,
                    user_type=self._resolve_call_user_type(tenant_id, user_type),
                    agent_id=agent_id,
                    conversation_id=conversation_id,
                    billing_context=billing_context,
                    routed_model_id=routed_model_id,
                    route_reason=route_reason,
                    call_type=call_type,
                    turn_record=turn_record,
                    protocol_path=protocol_path,
                    context_sources=context_sources,
                    selected_tool_names=self._normalize_string_list(
                        request_payload.get("selected_tool_names")
                    ),
                    selected_skill_names=self._normalize_string_list(
                        request_payload.get("selected_skill_names")
                    ),
                    fallback_history=request_payload.get("fallback_history"),
                    sync_rescue=request_payload.get("sync_rescue"),
                    should_record_call_log=True,
                )
            except Exception as e:
                logger.error("AI call log enqueue failed: {}", str(e))

        await self.db.commit()

        logger.info(
            "Stream completed: model={} in={} out={} total={} cost={}",
            model,
            input_tokens,
            output_tokens,
            total_tokens,
            cost,
        )

    serialize_response = staticmethod(serialize_chat_response)


__all__ = ["UsageRecorder"]
