"""
AI Usage Recorder. / AI 使用量记录器。

Handles rate/quota checks, usage recording, cost calculation, and call logging.
Extracted from AIGateway to reduce God Object complexity.
负责速率/配额检查、使用量记录、费用计算、调用日志。
从 AIGateway 提取，降低 God Object 复杂度。
"""

from __future__ import annotations

import dataclasses
import time
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.quota import QuotaExceeded, QuotaManager
from app.ai.rate_limiter import RateLimiter, RateLimitExceeded
from app.ai.types import (
    ChatMessage,
    ChatResponse,
    messages_to_dicts,
)
from app.configs.service import PLATFORM_TENANT_ID
from app.core.i18n import _
from app.core.logging import LogManager
from app.enums.ai import CallStatusEnum, RequestTypeEnum
from app.enums.log import UserTypeEnum as LogUserTypeEnum
from app.models.ai import AIModel, AIProvider, ProviderApiKey
from app.services.ai.call_log_service import CallLogService
from app.services.ai.metering_service import MeteringService

logger = LogManager.get_logger("ai")


class UsageRecorder:
    """
    AI Usage Recorder / AI 使用量记录器

    Responsibilities / 职责：
    - Rate limit + quota check / 速率限制 + 配额检查
    - Usage recording + TPM/quota correction / 使用量记录 + TPM/配额校正
    - Call logging (success/failure) / 调用日志（成功/失败）
    - Stream completion callback / 流式完成回调
    - ChatResponse serialization / ChatResponse 序列化
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.metering = MeteringService(db)
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

    async def check_rate_and_quota(
        self,
        tenant_id: int,
        model_id: int,
        ai_model: AIModel,
        estimated_tokens: int,
    ) -> None:
        """
        Atomic rate limit + quota check (executed only for tenant calls). / 原子检查速率限制 + 配额（仅企业调用时执行）。

        Rate limit priority: tenant custom > model default.
        速率限制优先级：企业自定义 > 模型默认值。
        """
        # Determine effective rate limits: prioritize tenant-specific config / 确定有效的速率限制：优先使用企业专属配置
        rpm_limit = ai_model.rpm_limit
        tpm_limit = ai_model.tpm_limit

        if tenant_id:
            from app.services.ai.tenant_rate_limit_service import TenantRateLimitService
            rate_svc = TenantRateLimitService(self.db, tenant_id)
            effective = await rate_svc.get_effective_rate_limits(model_id)
            if effective.get("source") == "tenant":
                rpm_limit = effective["rpm_limit"]
                tpm_limit = effective["tpm_limit"]

        try:
            await RateLimiter.check_and_record(
                tenant_id=tenant_id,
                model_id=model_id,
                rpm_limit=rpm_limit,
                tpm_limit=tpm_limit,
                estimated_tokens=estimated_tokens,
            )
        except RateLimitExceeded as e:
            logger.warning(
                "Rate limit blocked: tenant={} error={}",
                tenant_id, str(e),
            )
            raise

        try:
            await self.quota_manager.check_quota(
                tenant_id=tenant_id,
                model_id=model_id,
                estimated_tokens=estimated_tokens,
            )
        except QuotaExceeded as e:
            logger.warning(
                "Quota blocked: tenant={} error={}",
                tenant_id, str(e),
            )
            raise

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
    ) -> None:
        """
        Record usage + adjust TPM/quota (from estimated to actual). / 记录使用量 + 调整 TPM/配额（从预估调整为实际）。
        """
        await self.metering.record_usage(
            tenant_id=tenant_id,
            model_id=model_id,
            request_type=request_type,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost=cost,
            success=True,
            user_id=user_id,
            latency_ms=latency_ms or None,
        )

        if estimated_input > 0:
            await RateLimiter.adjust_tpm_after_response(
                tenant_id=tenant_id,
                model_id=model_id,
                estimated_tokens=estimated_input,
                actual_tokens=total_tokens,
                request_minute_key=int(time.time()) // 60,
            )
            await self.quota_manager.adjust_usage(
                tenant_id=tenant_id,
                model_id=model_id,
                estimated_tokens=estimated_input,
                actual_tokens=total_tokens,
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
        tenant_id: int | None = None,
        user_id: int | None = None,
        user_type: str | None = None,
        agent_id: int | None = None,
        conversation_id: int | None = None,
        routed_model_id: int | None = None,
        route_reason: str | None = None,
    ) -> None:
        """
        记录失败调用日志到 DB（用于审计追踪）/ Log failed call to DB (for audit trail).
        """
        _ = model
        if not self._should_record_call_log(tenant_id):
            return
        try:
            assert tenant_id is not None
            latency_ms = int((time.time() - start_time) * 1000)
            request_data = {
                "messages": messages_to_dicts(messages),
                "temperature": temperature,
                "max_tokens": max_tokens,
                "top_p": top_p,
                "tools": tools,
            }
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
                user_id=user_id,
                user_type=self._resolve_call_user_type(tenant_id, user_type),
                agent_id=agent_id,
                conversation_id=conversation_id,
                routed_model_id=routed_model_id,
                route_reason=route_reason,
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
        routed_model_id: int | None = None,
        route_reason: str | None = None,
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
            )

        api_key.increment_usage()

        if should_record_call_log:
            try:
                assert tenant_id is not None
                await self.call_log_service.log_call_async(
                    tenant_id=tenant_id,
                    model_id=model_id,
                    provider_id=provider.id,
                    request_type=RequestTypeEnum.CHAT.value,
                    request_data={"_stream": True},
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
                    routed_model_id=routed_model_id,
                    route_reason=route_reason,
                )
            except Exception as e:
                logger.error("AI call log enqueue failed: {}", str(e))

        await self.db.commit()

        logger.info(
            "Stream completed: model={} in={} out={} total={} cost={}",
            model, input_tokens, output_tokens, total_tokens, cost,
        )

    @staticmethod
    def serialize_response(response: ChatResponse) -> dict:
        """
        安全序列化 ChatResponse / Safely serialize ChatResponse.

        Recursively converts Decimal → str, dataclass → dict, excludes raw_response.
        递归处理 Decimal → str、dataclass → dict，排除 raw_response。
        """
        def _safe_value(val: Any) -> Any:
            if isinstance(val, Decimal):
                return str(val)
            if dataclasses.is_dataclass(val) and not isinstance(val, type):
                return {k: _safe_value(v) for k, v in val.__dict__.items()}
            if isinstance(val, dict):
                return {k: _safe_value(v) for k, v in val.items()}
            if isinstance(val, (list, tuple)):
                return [_safe_value(item) for item in val]
            return val

        data = {}
        for key, value in response.__dict__.items():
            if key == "raw_response":
                continue
            data[key] = _safe_value(value)
        return data


__all__ = ["UsageRecorder"]
