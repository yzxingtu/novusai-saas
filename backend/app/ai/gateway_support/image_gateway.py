"""Image generation entrypoint helper for the AI gateway facade."""

from __future__ import annotations

import time
from typing import Any

from app.ai.gateway_support.adapter_support import build_adapter_extra
from app.ai.gateway_support.call_log_bridge import GatewayCallLogBridge
from app.ai.types import ImageGenerationResponse
from app.core.i18n import _
from app.core.logging import LogManager
from app.enums.ai import CallStatusEnum, CallTypeEnum, RequestTypeEnum
from app.exceptions import NotFoundException

logger = LogManager.get_logger("ai")


async def execute_image_generation(
    gateway: Any,
    *,
    provider_code: str,
    prompt: str,
    model: str,
    size: str = "1024x1024",
    quality: str = "standard",
    style: str = "vivid",
    n: int = 1,
    tenant_id: int | None = None,
    user_id: int | None = None,
    user_type: str | None = None,
    agent_id: int | None = None,
    conversation_id: int | None = None,
    billing_context: dict | None = None,
    call_type: str = CallTypeEnum.MAIN_CHAT.value,
    cost_calculator: Any,
    **kwargs: Any,
) -> ImageGenerationResponse:
    """Execute the image generation call chain for AIGateway.generate_image()."""
    start_time = time.time()

    provider, api_key = await gateway.get_provider_and_key(provider_code, tenant_id)
    ai_model = await gateway._get_model(model, provider.id)

    if not ai_model:
        raise NotFoundException(message=_("ai.error.model_not_found"))

    model_id = ai_model.id
    should_meter_usage = GatewayCallLogBridge.should_meter_usage(tenant_id)
    should_record_call_log = GatewayCallLogBridge.should_record_call_log(tenant_id)
    call_user_type = GatewayCallLogBridge.resolve_call_user_type(tenant_id, user_type)
    resolved_billing_context = GatewayCallLogBridge.resolve_billing_context(
        tenant_id,
        user_id=user_id,
        user_type=call_user_type,
        billing_context=billing_context,
    )

    estimated_input = 0
    metering_context = None
    if should_meter_usage:
        estimated_input = 1000 * n
        metering_context = await gateway.usage_recorder.check_rate_and_quota(
            tenant_id,
            model_id,
            ai_model,
            estimated_input,
        )

    response, _retry_count, used_api_key = await gateway._execute_with_retry(
        provider=provider,
        api_key=api_key,
        model=model,
        call_fn=lambda adapter: adapter.generate_image(
            prompt=prompt,
            model=model,
            size=size,
            quality=quality,
            style=style,
            n=n,
            **kwargs,
        ),
        tenant_id=tenant_id,
        log_key="ai.log.gateway_image_call",
        adapter_extra={
            **build_adapter_extra(
                db=gateway.db,
                ai_model=ai_model,
                tenant_id=tenant_id,
            ),
        },
    )
    GatewayCallLogBridge.attach_runtime_metadata(
        response,
        provider=provider,
        ai_model=ai_model,
    )

    latency_ms = int((time.time() - start_time) * 1000)

    input_tokens = estimated_input
    output_tokens = 0
    total_tokens = input_tokens

    cost = cost_calculator.calculate_cost(ai_model, input_tokens, output_tokens)

    if should_meter_usage:
        assert tenant_id is not None
        await gateway.usage_recorder.record_usage_and_adjust(
            tenant_id=tenant_id,
            model_id=model_id,
            request_type=RequestTypeEnum.IMAGE.value,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            cost=cost,
            estimated_input=estimated_input,
            latency_ms=latency_ms,
            user_id=user_id,
            metering_context=metering_context,
        )

    used_api_key.increment_usage()

    if should_record_call_log:
        try:
            assert tenant_id is not None
            request_data = {
                "prompt": prompt[:200],
                "size": size,
                "quality": quality,
                "n": n,
            }

            await gateway.usage_recorder.call_log_service.log_call_async(
                tenant_id=tenant_id,
                model_id=model_id,
                provider_id=provider.id,
                request_type=RequestTypeEnum.IMAGE.value,
                request_data=request_data,
                response_data={
                    "image_count": len(response.images),
                    "revised_prompt": response.revised_prompt,
                },
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                cost=cost,
                latency_ms=latency_ms,
                status=CallStatusEnum.SUCCESS.value,
                user_id=user_id,
                user_type=call_user_type,
                agent_id=agent_id,
                conversation_id=conversation_id,
                billing_context=GatewayCallLogBridge.merge_model_provider_snapshots(
                    resolved_billing_context,
                    provider=provider,
                    ai_model=ai_model,
                ),
                call_type=call_type,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("AI call log enqueue failed: {}", str(exc))

    await gateway.db.commit()

    return response


__all__ = ["execute_image_generation"]
