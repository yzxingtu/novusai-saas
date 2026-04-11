"""Native web-search execution collaborator for AIGateway facade."""

from __future__ import annotations

import asyncio
import time
from typing import Any

from app.ai.exceptions import AIGatewayError
from app.ai.web_search.types import (
    PROVIDER_MODE_NATIVE,
    STATUS_UNSUPPORTED,
    STATUS_UPSTREAM_ERROR,
    SearchProviderRun,
)
from app.ai.types import ChatMessage, messages_to_dicts
from app.core.i18n import _
from app.core.logging import LogManager
from app.enums.ai import RequestTypeEnum
from app.exceptions import BusinessException, NotFoundException

logger = LogManager.get_logger("ai")


def _build_native_search_run(
    *,
    provider: str | None,
    backend_key: str,
    status: str,
    failure_reason: str,
    latency_ms: int,
    native_attempted: bool,
) -> SearchProviderRun:
    return SearchProviderRun(
        provider=provider,
        provider_mode=PROVIDER_MODE_NATIVE,
        backend_key=backend_key,
        status=status,
        items=[],
        failure_reason=failure_reason,
        latency_ms=latency_ms,
        attempted_backends=[backend_key],
        native_attempted=native_attempted,
    )


async def execute_native_web_search(
    gateway: Any,
    *,
    provider_code: str,
    model: str,
    query: str,
    max_results: int,
    locale: str | None = None,
    timeout_seconds: int = 20,
    tenant_id: int | None = None,
    user_id: int | None = None,
    user_type: str | None = None,
    agent_id: int | None = None,
    conversation_id: int | None = None,
    billing_context: dict | None = None,
    provider_label: str | None = None,
    backend_key: str | None = None,
    call_type: str,
    adapter_registry: Any,
    token_counter: Any,
    cost_calculator: Any,
    provider_timeout_error_cls: Any,
) -> SearchProviderRun:
    """Execute provider-hosted native web search with gateway governance."""

    start_time = time.time()
    request_messages = [ChatMessage(role="user", content=query)]
    effective_backend_key = (
        str(backend_key or "").strip()
        or f"native:{str(provider_label or provider_code or 'provider').strip() or 'provider'}:{model}"
    )
    effective_provider_label = str(provider_label or provider_code or "").strip() or None

    try:
        provider, api_key = await gateway.get_provider_and_key(provider_code, tenant_id)
    except NotFoundException:
        return _build_native_search_run(
            provider=effective_provider_label,
            backend_key=effective_backend_key,
            status=STATUS_UNSUPPORTED,
            failure_reason="runtime provider unavailable",
            latency_ms=int((time.time() - start_time) * 1000),
            native_attempted=False,
        )
    except BusinessException as exc:
        return _build_native_search_run(
            provider=effective_provider_label,
            backend_key=effective_backend_key,
            status=STATUS_UPSTREAM_ERROR,
            failure_reason=str(exc),
            latency_ms=int((time.time() - start_time) * 1000),
            native_attempted=False,
        )

    ai_model = await gateway._get_model(model, provider.id)
    if not ai_model:
        return _build_native_search_run(
            provider=effective_provider_label
            or str(getattr(provider, "code", "") or provider.type or "").strip()
            or None,
            backend_key=effective_backend_key,
            status=STATUS_UNSUPPORTED,
            failure_reason="runtime model unavailable",
            latency_ms=int((time.time() - start_time) * 1000),
            native_attempted=False,
        )

    effective_provider_label = (
        effective_provider_label
        or str(getattr(provider, "code", "") or provider.type or "").strip()
    )
    adapter_class = adapter_registry.get_adapter(provider.type)
    if adapter_class is None:
        return _build_native_search_run(
            provider=effective_provider_label,
            backend_key=effective_backend_key,
            status=STATUS_UNSUPPORTED,
            failure_reason=f"adapter not registered for provider type {provider.type}",
            latency_ms=int((time.time() - start_time) * 1000),
            native_attempted=False,
        )

    preflight_adapter = adapter_registry.create_adapter(
        provider_type=provider.type,
        api_key=api_key.decrypt_key(),
        base_url=provider.base_url,
        provider_config=provider.config,
        **gateway._build_adapter_extra(
            ai_model=ai_model,
            tenant_id=tenant_id,
        ),
    )
    if not preflight_adapter.supports_native_web_search(model):
        return _build_native_search_run(
            provider=effective_provider_label,
            backend_key=effective_backend_key,
            status=STATUS_UNSUPPORTED,
            failure_reason="adapter/model does not expose native web search",
            latency_ms=int((time.time() - start_time) * 1000),
            native_attempted=False,
        )

    should_meter_usage = gateway._should_meter_usage(tenant_id)
    should_record_call_log = gateway._should_record_call_log(tenant_id)
    call_user_type = gateway._resolve_call_user_type(tenant_id, user_type)
    resolved_billing_context = gateway._resolve_billing_context(
        tenant_id,
        user_id=user_id,
        user_type=call_user_type,
        billing_context=billing_context,
    )
    request_data = gateway._build_request_log_data(
        messages=request_messages,
        temperature=0.0,
        max_tokens=None,
        top_p=1.0,
        tools=[{"type": "function", "function": {"name": "web_search"}}],
        tool_choice="required",
        all_tool_names=["web_search", "fetch_url"],
        tool_use_policy_family="web_research",
        tool_use_policy_mode="required",
        allowed_tool_names=["web_search", "fetch_url"],
    )
    request_data.update(
        {
            "query": query,
            "max_results": max_results,
            "locale": locale,
            "timeout_seconds": timeout_seconds,
            "provider_mode": PROVIDER_MODE_NATIVE,
            "backend_key": effective_backend_key,
        }
    )
    native_retry_limit = 0

    estimated_input = 0
    metering_context = None
    if should_meter_usage or should_record_call_log:
        estimated_input = token_counter.count_messages_tokens(
            messages_to_dicts(request_messages)
        )
    if should_meter_usage:
        metering_context = await gateway.usage_recorder.check_rate_and_quota(
            tenant_id,
            ai_model.id,
            ai_model,
            estimated_input,
        )

    async def _run_native_search_with_retry(adapter: Any) -> SearchProviderRun:
        try:
            run = await asyncio.wait_for(
                adapter.native_web_search(
                    query=query,
                    max_results=max_results,
                    locale=locale,
                    timeout_seconds=timeout_seconds,
                    model=model,
                    provider_label=effective_provider_label,
                    backend_key=effective_backend_key,
                ),
                timeout=max(0.1, float(timeout_seconds)),
            )
        except asyncio.TimeoutError as exc:
            raise provider_timeout_error_cls(
                message=_("ai.error.provider_timeout"),
                provider_code=provider.code,
                model_code=model,
            ) from exc
        return gateway._raise_retryable_native_web_search_failure(
            run,
            provider_code=provider.code,
            model_code=model,
        )

    try:
        run, retry_count, used_api_key = await gateway._execute_with_retry(
            provider=provider,
            api_key=api_key,
            model=model,
            call_fn=_run_native_search_with_retry,
            tenant_id=tenant_id,
            log_key="ai.log.gateway_native_web_search_call",
            adapter_extra={
                **gateway._build_adapter_extra(
                    ai_model=ai_model,
                    tenant_id=tenant_id,
                ),
            },
            max_retries=native_retry_limit,
        )
    except AIGatewayError as exc:
        latency_ms = int((time.time() - start_time) * 1000)
        failure_status = gateway._native_web_search_error_status(exc)
        if should_record_call_log:
            try:
                assert tenant_id is not None
                await gateway.usage_recorder.call_log_service.log_call_async(
                    tenant_id=tenant_id,
                    model_id=ai_model.id,
                    provider_id=provider.id,
                    request_type=RequestTypeEnum.CHAT.value,
                    request_data=request_data,
                    response_data={
                        "status": failure_status,
                        "provider_mode": PROVIDER_MODE_NATIVE,
                        "backend_key": effective_backend_key,
                        "result_count": 0,
                        "_retry_count": native_retry_limit,
                    },
                    input_tokens=0,
                    output_tokens=0,
                    total_tokens=0,
                    cost=0,
                    latency_ms=latency_ms,
                    status=gateway._native_web_search_call_status(failure_status),
                    error_message=str(exc),
                    user_id=user_id,
                    user_type=call_user_type,
                    agent_id=agent_id,
                    conversation_id=conversation_id,
                    billing_context=gateway._merge_model_provider_snapshots(
                        resolved_billing_context,
                        provider=provider,
                        ai_model=ai_model,
                    ),
                    call_type=call_type,
                )
            except Exception as log_exc:  # noqa: BLE001
                logger.error("AI call log enqueue failed: {}", str(log_exc))

        return _build_native_search_run(
            provider=effective_provider_label,
            backend_key=effective_backend_key,
            status=failure_status,
            failure_reason=str(exc),
            latency_ms=latency_ms,
            native_attempted=True,
        )

    run.provider = run.provider or effective_provider_label
    run.provider_mode = run.provider_mode or PROVIDER_MODE_NATIVE
    run.backend_key = run.backend_key or effective_backend_key
    run.attempted_backends = list(run.attempted_backends or [effective_backend_key])
    run.latency_ms = int((time.time() - start_time) * 1000)
    run.native_attempted = True

    cost = cost_calculator.calculate_cost(
        ai_model,
        run.input_tokens,
        run.output_tokens,
    )
    if should_meter_usage:
        assert tenant_id is not None
        await gateway.usage_recorder.record_usage_and_adjust(
            tenant_id=tenant_id,
            model_id=ai_model.id,
            request_type=RequestTypeEnum.CHAT.value,
            input_tokens=run.input_tokens,
            output_tokens=run.output_tokens,
            total_tokens=run.total_tokens,
            cost=cost,
            estimated_input=estimated_input,
            latency_ms=run.latency_ms,
            user_id=user_id,
            metering_context=metering_context,
        )

    used_api_key.increment_usage()

    if should_record_call_log:
        try:
            assert tenant_id is not None
            response_data = {
                "status": run.status,
                "provider_mode": run.provider_mode,
                "backend_key": run.backend_key,
                "result_count": len(run.items),
                "items": [item.to_summary_item() for item in run.items[:max_results]],
                "_retry_count": retry_count,
            }
            if run.failure_reason:
                response_data["failure_reason"] = run.failure_reason
            await gateway.usage_recorder.call_log_service.log_call_async(
                tenant_id=tenant_id,
                model_id=ai_model.id,
                provider_id=provider.id,
                request_type=RequestTypeEnum.CHAT.value,
                request_data=request_data,
                response_data=response_data,
                input_tokens=run.input_tokens,
                output_tokens=run.output_tokens,
                total_tokens=run.total_tokens,
                cost=cost,
                latency_ms=run.latency_ms,
                status=gateway._native_web_search_call_status(run.status),
                user_id=user_id,
                user_type=call_user_type,
                agent_id=agent_id,
                conversation_id=conversation_id,
                billing_context=gateway._merge_model_provider_snapshots(
                    resolved_billing_context,
                    provider=provider,
                    ai_model=ai_model,
                ),
                call_type=call_type,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("AI call log enqueue failed: {}", str(exc))

    await gateway.db.commit()
    return run


__all__ = ["execute_native_web_search"]
