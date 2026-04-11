"""Quota adjustment collaborator for AIGateway facade."""

from __future__ import annotations

from app.ai.usage_recorder import UsageMeteringContext, UsageRecorder
from app.models.ai import AIModel


class GatewayQuotaGuard:
    """Small wrapper around usage recorder's quota adjustment path."""

    def __init__(self, usage_recorder: UsageRecorder):
        self._usage_recorder = usage_recorder

    async def record_usage_and_adjust(
        self,
        *,
        tenant_id: int,
        ai_model: AIModel,
        input_tokens: int,
        output_tokens: int,
        total_tokens: int,
        metering_context: UsageMeteringContext | None = None,
        request_id: str | None = None,
    ) -> None:
        await self._usage_recorder.record_usage_and_adjust(
            tenant_id=tenant_id,
            ai_model=ai_model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            metering_context=metering_context,
            request_id=request_id,
        )
