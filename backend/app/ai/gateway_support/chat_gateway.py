"""Chat entrypoint helper for the AI gateway facade."""

from __future__ import annotations

import time
from typing import Any

from app.ai.exceptions import AIGatewayError
from app.ai.gateway_support.adapter_support import build_adapter_extra
from app.ai.gateway_support.call_log_bridge import GatewayCallLogBridge
from app.ai.gateway_support.failover_orchestrator import (
    build_gateway_fallback_requirements,
    scrub_gateway_failover_runtime_kwargs,
)
from app.ai.types import ChatMessage, ChatResponse, messages_to_dicts
from app.ai.usage_mode import resolve_chat_usage
from app.core.i18n import _
from app.core.logging import LogManager
from app.enums.ai import CallStatusEnum, CallTypeEnum, RequestTypeEnum
from app.exceptions import BusinessException, NotFoundException

logger = LogManager.get_logger("ai")


async def execute_chat(
    gateway: Any,
    *,
    provider_code: str,
    messages: list[ChatMessage],
    model: str,
    temperature: float = 0.7,
    max_tokens: int | None = None,
    top_p: float = 1.0,
    stream: bool = False,
    tools: list[dict] | None = None,
    tool_choice: str | None = None,
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
    billing_context: dict | None = None,
    routed_model_id: int | None = None,
    route_reason: str | None = None,
    call_type: str = CallTypeEnum.MAIN_CHAT.value,
    adapter_registry: Any,
    token_counter: Any,
    cost_calculator: Any,
    usage_recorder_cls: Any,
    response_cache: Any,
    settings_obj: Any,
    **kwargs: Any,
) -> ChatResponse:
    """Execute the chat call chain for AIGateway.chat()."""
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

    use_cache = temperature == 0 and not stream
    cache_key = None

    if use_cache:
        cache_key = response_cache._generate_cache_key(
            provider_code=provider_code,
            model=model,
            messages=messages_to_dicts(messages),
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
            tools=tools,
            tool_choice=tool_choice,
        )

        cached_response = await response_cache.get(cache_key)
        if cached_response:
            logger.info("Cache hit: key={}", cache_key)
            api_key.mark_last_used()
            await gateway.db.flush()
            return ChatResponse(**cached_response)

    estimated_input = 0
    metering_context = None
    if should_meter_usage or should_record_call_log:
        estimated_input = token_counter.count_messages_tokens(
            messages_to_dicts(messages)
        )
    if should_meter_usage:
        metering_context = await gateway.usage_recorder.check_rate_and_quota(
            tenant_id,
            model_id,
            ai_model,
            estimated_input,
        )

    GatewayCallLogBridge.warn_policy_not_loaded(
        tools=tools,
        tool_choice=tool_choice,
        conversation_id=conversation_id,
        agent_id=agent_id,
    )
    try:
        response, retry_count, used_api_key = await gateway._execute_with_retry(
            provider=provider,
            api_key=api_key,
            model=model,
            call_fn=lambda adapter: gateway._call_chat_adapter(
                adapter=adapter,
                provider=provider,
                messages=messages,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=top_p,
                stream=stream,
                tools=tools,
                tool_choice=tool_choice,
                extra_kwargs=kwargs,
            ),
            tenant_id=tenant_id,
            adapter_extra={
                **build_adapter_extra(
                    db=gateway.db,
                    ai_model=ai_model,
                    tenant_id=tenant_id,
                ),
            },
        )
    except AIGatewayError as original_error:
        await gateway.failover.record_provider_runtime_failure(
            provider.id,
            model_id=model_id,
            error=original_error,
        )
        fallback_model = await gateway.failover.get_fallback_model(
            model_id,
            **build_gateway_fallback_requirements(
                messages=messages,
                tools=tools,
                estimated_input=estimated_input,
            ),
        )
        if not fallback_model:
            await gateway.usage_recorder.log_call_failure(
                error=original_error,
                start_time=start_time,
                provider=provider,
                model=model,
                model_id=model_id,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=top_p,
                tools=tools,
                tool_choice=tool_choice,
                selected_tool_names=[
                    ((tool.get("function", {}) or {}).get("name"))
                    for tool in (tools or [])
                    if isinstance(tool, dict)
                ],
                all_tool_names=all_tool_names,
                tool_use_policy_family=tool_use_policy_family,
                tool_use_policy_mode=tool_use_policy_mode,
                allowed_tool_names=allowed_tool_names,
                breach_retry_result=breach_retry_result,
                request_type=RequestTypeEnum.CHAT.value,
                tenant_id=tenant_id,
                user_id=user_id,
                user_type=call_user_type,
                agent_id=agent_id,
                conversation_id=conversation_id,
                billing_context=GatewayCallLogBridge.merge_model_provider_snapshots(
                    resolved_billing_context,
                    provider=provider,
                    ai_model=ai_model,
                ),
                routed_model_id=routed_model_id,
                route_reason=route_reason,
                call_type=call_type,
            )
            raise

        logger.info(
            "Fallback attempt: original_model={} fallback_model={}",
            model,
            fallback_model.code,
        )

        try:
            fallback_extra_kwargs = scrub_gateway_failover_runtime_kwargs(kwargs)
            fb_provider, fb_api_key = await gateway.get_provider_and_key(
                fallback_model.provider.code, tenant_id
            )
            response, retry_count, used_api_key = await gateway._execute_with_retry(
                provider=fb_provider,
                api_key=fb_api_key,
                model=fallback_model.code,
                call_fn=lambda adapter: gateway._call_chat_adapter(
                    adapter=adapter,
                    provider=fb_provider,
                    messages=messages,
                    model=fallback_model.code,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    top_p=top_p,
                    stream=stream,
                    tools=tools,
                    tool_choice=tool_choice,
                    extra_kwargs=fallback_extra_kwargs,
                ),
                tenant_id=tenant_id,
                adapter_extra={
                    **build_adapter_extra(
                        db=gateway.db,
                        ai_model=fallback_model,
                        tenant_id=tenant_id,
                    ),
                },
            )
            provider = fb_provider
            api_key = fb_api_key
            ai_model = fallback_model
            model_id = fallback_model.id
            model = fallback_model.code
            logger.info("Fallback succeeded: fallback_model={}", fallback_model.code)
        except (AIGatewayError, NotFoundException, BusinessException):
            logger.warning(
                "Fallback failed: fallback_model={}",
                fallback_model.code,
            )
            await gateway.usage_recorder.log_call_failure(
                error=original_error,
                start_time=start_time,
                provider=provider,
                model=model,
                model_id=model_id,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=top_p,
                tools=tools,
                tool_choice=tool_choice,
                selected_tool_names=[
                    ((tool.get("function", {}) or {}).get("name"))
                    for tool in (tools or [])
                    if isinstance(tool, dict)
                ],
                all_tool_names=all_tool_names,
                tool_use_policy_family=tool_use_policy_family,
                tool_use_policy_mode=tool_use_policy_mode,
                allowed_tool_names=allowed_tool_names,
                breach_retry_result=breach_retry_result,
                request_type=RequestTypeEnum.CHAT.value,
                tenant_id=tenant_id,
                user_id=user_id,
                user_type=call_user_type,
                agent_id=agent_id,
                conversation_id=conversation_id,
                billing_context=GatewayCallLogBridge.merge_model_provider_snapshots(
                    resolved_billing_context,
                    provider=provider,
                    ai_model=ai_model,
                ),
                routed_model_id=routed_model_id,
                route_reason=route_reason,
                call_type=call_type,
            )
            raise original_error from None

    latency_ms = int((time.time() - start_time) * 1000)

    usage = resolve_chat_usage(
        messages=messages,
        output_text=response.message.content or "",
        input_tokens=response.input_tokens,
        output_tokens=response.output_tokens,
        total_tokens=response.total_tokens,
        estimated_input=estimated_input,
    )
    input_tokens = usage.input_tokens
    output_tokens = usage.output_tokens
    total_tokens = usage.total_tokens

    cost = cost_calculator.calculate_cost(ai_model, input_tokens, output_tokens)
    GatewayCallLogBridge.attach_runtime_metadata(
        response,
        provider=provider,
        ai_model=ai_model,
    )
    response.metadata["usage_mode"] = usage.usage_mode

    if should_meter_usage:
        assert tenant_id is not None
        await gateway.usage_recorder.record_usage_and_adjust(
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

    used_api_key.increment_usage()

    if should_record_call_log:
        try:
            assert tenant_id is not None
            request_data = GatewayCallLogBridge.build_request_log_data(
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=top_p,
                tools=tools,
                tool_choice=tool_choice,
                all_tool_names=all_tool_names,
                retry_count=retry_count,
                tool_use_policy_family=tool_use_policy_family,
                tool_use_policy_mode=tool_use_policy_mode,
                allowed_tool_names=allowed_tool_names,
                breach_retry_result=breach_retry_result,
            )

            await gateway.usage_recorder.call_log_service.log_call_async(
                tenant_id=tenant_id,
                model_id=model_id,
                provider_id=provider.id,
                request_type=RequestTypeEnum.CHAT.value,
                request_data=request_data,
                response_data=usage_recorder_cls.serialize_response(response),
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
                routed_model_id=routed_model_id,
                route_reason=route_reason,
                call_type=call_type,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("AI call log enqueue failed: {}", str(exc))

    await gateway.db.commit()

    if use_cache and cache_key:
        try:
            await response_cache.set(
                cache_key=cache_key,
                response_data=usage_recorder_cls.serialize_response(response),
                ttl=settings_obj.AI_CACHE_TTL,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("Cache set failed: {}", str(exc))

    return response


__all__ = ["execute_chat"]
