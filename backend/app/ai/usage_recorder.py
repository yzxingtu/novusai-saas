"""
AI 使用量记录器

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
from app.core.i18n import _
from app.core.logging import LogManager
from app.enums.ai import CallStatusEnum, RequestTypeEnum, UserTypeEnum
from app.models.ai import AIModel, AIProvider, ProviderApiKey
from app.services.ai.call_log_service import CallLogService
from app.services.ai.metering_service import MeteringService

logger = LogManager.get_logger("ai")


class UsageRecorder:
    """
    AI 使用量记录器

    职责：
    - 速率限制 + 配额检查
    - 使用量记录 + TPM/配额校正
    - 调用日志（成功/失败）
    - 流式完成回调
    - ChatResponse 序列化
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.metering = MeteringService(db)
        self.quota_manager = QuotaManager(db)
        self.call_log_service = CallLogService(db)

    async def check_rate_and_quota(
        self,
        tenant_id: int,
        model_id: int,
        ai_model: AIModel,
        estimated_tokens: int,
    ) -> None:
        """
        原子检查速率限制 + 配额（仅租户调用时执行）

        速率限制优先级：租户自定义 > 模型默认值
        """
        # 确定有效的速率限制：优先使用租户专属配置
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
                "Rate limit blocked: tenant=%s error=%s",
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
                "Quota blocked: tenant=%s error=%s",
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
        记录使用量 + 调整 TPM/配额（从预估调整为实际）
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
    ) -> None:
        """
        记录失败调用日志到 DB（用于审计追踪）
        """
        _ = model
        if not tenant_id:
            return
        try:
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
                user_type=UserTypeEnum.TENANT_ADMIN.value,
            )
        except Exception as log_err:
            logger.error("Record usage failed: %s", str(log_err))

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
        model_id: int = 0,
        estimated_input: int = 0,
        latency_ms: int = 0,
    ) -> None:
        """
        流式响应完成回调

        记录日志、更新使用统计、调整 TPM/配额
        """
        # 更新 API Key 使用计数
        api_key.increment_usage()

        # 记录使用量（如果提供了 tenant_id）
        if tenant_id:
            try:
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

                # 异步记录调用日志
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
                    user_type=UserTypeEnum.TENANT_ADMIN.value,
                )

            except Exception as e:
                logger.error("Stream usage recording failed: %s", str(e))

        await self.db.commit()

        logger.info(
            "Stream completed: model=%s in=%d out=%d total=%d cost=%.4f",
            model, input_tokens, output_tokens, total_tokens, cost,
        )

    @staticmethod
    def serialize_response(response: ChatResponse) -> dict:
        """
        安全序列化 ChatResponse

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
