"""Rate-limit guard collaborator for AIGateway facade."""

from __future__ import annotations

from typing import Any

from app.ai.usage_recorder_context import UsageMeteringContext
from app.ai.usage_recorder_core import UsageRecorder
from app.configs.service import PLATFORM_TENANT_ID


class GatewayRateLimitGuard:
    """Encapsulate when/how metering checks should run."""

    def __init__(self, usage_recorder: UsageRecorder):
        self._usage_recorder = usage_recorder

    @staticmethod
    def should_meter_usage(tenant_id: int | None) -> bool:
        return tenant_id is not None and tenant_id > PLATFORM_TENANT_ID

    @staticmethod
    def should_record_call_log(tenant_id: int | None) -> bool:
        return tenant_id is not None

    async def check(
        self,
        *,
        tenant_id: int,
        model_code: str,
        provider_code: str,
        user_id: int | None,
        user_type: str | None,
    ) -> UsageMeteringContext:
        return await self._usage_recorder.check_rate_and_quota(
            tenant_id=tenant_id,
            model_code=model_code,
            provider_code=provider_code,
            user_id=user_id,
            user_type=user_type,
        )

    async def apply_stream_delta(self, **kwargs: Any) -> None:
        await self._usage_recorder.on_stream_complete(**kwargs)
