"""Streaming chat entrypoint helper for the AI gateway facade."""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator
from typing import Any

from fastapi.responses import StreamingResponse

from app.ai.exceptions import AIGatewayError, is_retryable
from app.ai.retry_service import MAX_RETRIES, RETRY_BASE_DELAY, RETRY_MULTIPLIER
from app.ai.sse import SSEStreamingResponse
from app.ai.types import ChatChunk, ChatMessage, messages_to_dicts
from app.core.i18n import _
from app.core.logging import LogManager
from app.enums.ai import CallTypeEnum, RequestTypeEnum
from app.exceptions import BusinessException, NotFoundException

logger = LogManager.get_logger("ai")


async def execute_stream_chat(
    gateway: Any,
    *,
    provider_code: str,
    messages: list[ChatMessage],
    model: str,
    temperature: float = 0.7,
    max_tokens: int | None = None,
    top_p: float = 1.0,
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
    **kwargs: Any,
) -> StreamingResponse:
    """Execute the streaming chat call chain for AIGateway.stream_chat()."""
    start_time = time.time()

    provider, api_key = await gateway.get_provider_and_key(provider_code, tenant_id)
    ai_model = await gateway._get_model(model, provider.id)

    if not ai_model:
        raise NotFoundException(message=_("ai.error.model_not_found"))
    should_meter_usage = gateway._should_meter_usage(tenant_id)
    call_user_type = gateway._resolve_call_user_type(tenant_id, user_type)
    resolved_billing_context = gateway._resolve_billing_context(
        tenant_id,
        user_id=user_id,
        user_type=call_user_type,
        billing_context=billing_context,
    )

    estimated_input = 0
    metering_context = None
    if should_meter_usage:
        estimated_input = token_counter.count_messages_tokens(
            messages_to_dicts(messages)
        )
        metering_context = await gateway.usage_recorder.check_rate_and_quota(
            tenant_id,
            ai_model.id,
            ai_model,
            estimated_input,
        )
    gateway._warn_policy_not_loaded(
        tools=tools,
        tool_choice=tool_choice,
        conversation_id=conversation_id,
        agent_id=agent_id,
    )

    async def generate_chunks() -> AsyncIterator[ChatChunk]:
        nonlocal api_key, provider, ai_model, model
        current_key = api_key

        try:
            for attempt in range(MAX_RETRIES + 1):
                try:
                    adapter = adapter_registry.create_adapter(
                        provider_type=provider.type,
                        api_key=current_key.decrypt_key(),
                        base_url=provider.base_url,
                        provider_config=provider.config,
                        internal_db=gateway.db,
                        internal_tenant_id=tenant_id,
                        model_config=getattr(ai_model, "config", None),
                    )

                    logger.info(
                        "Gateway stream call: provider={} model={}",
                        provider_code,
                        model,
                    )

                    async for chunk in gateway._stream_chat_adapter(
                        adapter=adapter,
                        provider=provider,
                        messages=messages,
                        model=model,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        top_p=top_p,
                        tools=tools,
                        tool_choice=tool_choice,
                        extra_kwargs=kwargs,
                    ):
                        yield chunk

                    if attempt > 0:
                        logger.info(
                            "Stream retry succeeded: provider={} model={} attempt={}",
                            provider_code,
                            model,
                            attempt,
                        )

                    api_key = current_key
                    return

                except AIGatewayError as exc:
                    if not is_retryable(exc):
                        logger.error(
                            "Non-retryable error: provider={} model={} error_code={} error={}",
                            provider_code,
                            model,
                            exc.error_code,
                            str(exc),
                        )
                        raise

                    if attempt >= MAX_RETRIES:
                        logger.error(
                            "Max retries exhausted: provider={} model={} attempts={} error={}",
                            provider_code,
                            model,
                            attempt + 1,
                            str(exc),
                        )
                        raise

                    delay = RETRY_BASE_DELAY * (RETRY_MULTIPLIER**attempt)
                    if exc.retry_after and exc.retry_after > delay:
                        delay = float(exc.retry_after)

                    logger.warning(
                        "Retrying after error: provider={} model={} attempt={} delay={}s error_code={} error={}",
                        provider_code,
                        model,
                        attempt,
                        delay,
                        exc.error_code,
                        str(exc),
                    )

                    next_key = await gateway.retry_service.get_next_api_key(
                        provider_id=provider.id,
                        current_key_id=current_key.id,
                        tenant_id=tenant_id,
                    )
                    if next_key:
                        logger.info(
                            "Switching API key: provider={} old_key={} new_key={}",
                            provider_code,
                            current_key.id,
                            next_key.id,
                        )
                        current_key = next_key

                    await asyncio.sleep(delay)

        except AIGatewayError as original_error:
            fallback_model = await gateway.failover.get_fallback_model(ai_model.id)
            if not fallback_model:
                await gateway.usage_recorder.log_call_failure(
                    error=original_error,
                    start_time=start_time,
                    provider=provider,
                    model=model,
                    model_id=ai_model.id,
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
                    billing_context=gateway._merge_model_provider_snapshots(
                        resolved_billing_context,
                        provider=provider,
                        ai_model=ai_model,
                    ),
                    routed_model_id=routed_model_id,
                    route_reason=route_reason,
                )
                raise

            logger.info(
                "Fallback attempt: original_model={} fallback_model={}",
                model,
                fallback_model.code,
            )

            try:
                fb_provider, fb_api_key = await gateway.get_provider_and_key(
                    fallback_model.provider.code, tenant_id
                )
                fb_adapter = adapter_registry.create_adapter(
                    provider_type=fb_provider.type,
                    api_key=fb_api_key.decrypt_key(),
                    base_url=fb_provider.base_url,
                    provider_config=fb_provider.config,
                    internal_db=gateway.db,
                    internal_tenant_id=tenant_id,
                    model_config=getattr(fallback_model, "config", None),
                )

                async for chunk in gateway._stream_chat_adapter(
                    adapter=fb_adapter,
                    provider=fb_provider,
                    messages=messages,
                    model=fallback_model.code,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    top_p=top_p,
                    tools=tools,
                    tool_choice=tool_choice,
                    extra_kwargs=kwargs,
                ):
                    yield chunk

                api_key = fb_api_key
                provider = fb_provider
                ai_model = fallback_model
                model = fallback_model.code
                logger.info(
                    "Fallback succeeded: fallback_model={}",
                    fallback_model.code,
                )
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
                    model_id=ai_model.id,
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
                    billing_context=gateway._merge_model_provider_snapshots(
                        resolved_billing_context,
                        provider=provider,
                        ai_model=ai_model,
                    ),
                    routed_model_id=routed_model_id,
                    route_reason=route_reason,
                )
                raise original_error from None

    async def on_complete(
        input_tokens: int, output_tokens: int, total_tokens: int
    ) -> None:
        if provider and api_key and ai_model:
            cost = cost_calculator.calculate_cost(
                ai_model,
                input_tokens,
                output_tokens,
            )
            stream_latency_ms = int((time.time() - start_time) * 1000)

            await gateway.usage_recorder.on_stream_complete(
                provider=provider,
                api_key=api_key,
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                cost=cost,
                tenant_id=tenant_id,
                user_id=user_id,
                user_type=call_user_type,
                model_id=ai_model.id,
                estimated_input=estimated_input,
                latency_ms=stream_latency_ms,
                agent_id=agent_id,
                conversation_id=conversation_id,
                billing_context=gateway._merge_model_provider_snapshots(
                    resolved_billing_context,
                    provider=provider,
                    ai_model=ai_model,
                ),
                routed_model_id=routed_model_id,
                route_reason=route_reason,
                metering_context=metering_context,
                call_type=call_type,
                request_data=gateway._build_request_log_data(
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    top_p=top_p,
                    tools=tools,
                    tool_choice=tool_choice,
                    all_tool_names=all_tool_names,
                    tool_use_policy_family=tool_use_policy_family,
                    tool_use_policy_mode=tool_use_policy_mode,
                    allowed_tool_names=allowed_tool_names,
                    breach_retry_result=breach_retry_result,
                    stream=True,
                ),
            )

    sse_response = SSEStreamingResponse(
        chunk_iterator=generate_chunks(),
        db=gateway.db,
        on_complete=on_complete,
    )

    return sse_response.response()


__all__ = ["execute_stream_chat"]
