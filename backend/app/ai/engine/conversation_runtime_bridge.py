"""Runtime-v2 provider/query-engine bridge for ConversationEngine."""

from __future__ import annotations

import time
from collections.abc import AsyncIterator
from typing import Any

from app.ai.adapters import AdapterRegistry
from app.ai.runtime import ConversationQueryEngine
from app.ai.tools.types import ToolDefinition
from app.ai.types import ChatChunk, ChatMessage, ChatResponse
from app.core.runtime_identity import get_runtime_identity_tag

from .conversation_helpers import await_if_needed as _await_if_needed
from .conversation_runtime_context_builder import (
    build_runtime_query_entrypoint_plan,
    build_runtime_stream_entrypoint_plan,
)
from .conversation_runtime_entrypoint_runner import (
    iterate_runtime_stream_entrypoint,
    run_runtime_query_entrypoint,
)
from .conversation_runtime_preflight import ConversationRuntimeContext
from .model_policy import build_model_request_overrides
from .types import ToolUsePolicy


async def call_runtime_query_turn(
    engine: Any,
    *,
    agent: Any,
    messages: list[ChatMessage],
    tools: list[ToolDefinition] | None,
    all_tool_names: list[str] | None,
    tool_use_policy: ToolUsePolicy | None,
    breach_retry_result: str | None,
    tenant_id: int | None,
    user_id: int | None,
    conversation_id: int | None,
    billing_context: dict[str, Any] | None,
    route_result: Any | None,
    log_user_type: str | None,
    selected_skill_names: list[str] | None,
    context_sources: list[Any] | None,
    execution_path: str | None,
    extra_kwargs: dict[str, Any] | None,
    adapter_registry: Any = AdapterRegistry,
    query_engine_cls: Any = ConversationQueryEngine,
    model_request_override_builder: Any = build_model_request_overrides,
    engine_logger: Any = None,
) -> tuple[ChatResponse, ConversationQueryEngine]:
    del model_request_override_builder
    plan = await build_runtime_query_entrypoint_plan(
        engine,
        agent=agent,
        messages=messages,
        tools=tools,
        all_tool_names=all_tool_names,
        tool_use_policy=tool_use_policy,
        breach_retry_result=breach_retry_result,
        tenant_id=tenant_id,
        user_id=user_id,
        conversation_id=conversation_id,
        billing_context=billing_context,
        route_result=route_result,
        log_user_type=log_user_type,
        context_sources=context_sources,
        execution_path=execution_path,
        extra_kwargs=extra_kwargs,
        runtime_preparer=prepare_stream_runtime,
        adapter_registry=adapter_registry,
        query_engine_cls=query_engine_cls,
    )
    runtime_context = plan.runtime_context
    provider = runtime_context.provider
    model_code = runtime_context.model_code
    call_start = time.perf_counter()

    try:
        response = await run_runtime_query_entrypoint(
            plan=plan,
            agent=agent,
            selected_skill_names=list(selected_skill_names or []),
        )
    except Exception as exc:  # noqa: BLE001
        engine_logger = engine_logger or getattr(engine, "logger", None)
        if engine_logger is not None:
            engine_logger.error(
                "Runtime-v2 non-stream call failed: provider={} model={} conversation={} error={}",
                provider.code,
                model_code,
                conversation_id,
                str(exc),
                exc_info=True,
            )
        await plan.accounting.log_failure(
            error=exc,
            start_time=call_start,
            runtime_context=runtime_context,
            request_context=plan.request_context,
            audit_context=plan.audit_context,
            turn_record=plan.query_engine.turn_record,
            failure_log_message="Runtime-v2 non-stream failure audit log failed",
        )
        raise

    metadata = dict(getattr(response, "metadata", {}) or {})
    metadata.setdefault("runtime_model_info", runtime_context.runtime_info)
    metadata["runtime_turn_record"] = plan.query_engine.turn_record
    response.metadata = metadata

    usage_summary = await plan.accounting.finalize_success(
        runtime_context=runtime_context,
        request_context=plan.request_context,
        audit_context=plan.audit_context,
        output_text=response.message.content or "",
        input_tokens=response.input_tokens,
        output_tokens=response.output_tokens,
        total_tokens=response.total_tokens,
        start_time=call_start,
        turn_record=plan.query_engine.turn_record,
        success_log_message="Runtime-v2 non-stream call log failed",
    )
    response.input_tokens = usage_summary.input_tokens
    response.output_tokens = usage_summary.output_tokens
    response.total_tokens = usage_summary.total_tokens
    response.metadata["usage_mode"] = usage_summary.usage_mode

    await _await_if_needed(engine.db.commit())
    return response, plan.query_engine


async def stream_llm_chunks(
    engine: Any,
    *,
    agent: Any,
    messages: list[ChatMessage],
    tenant_id: int | None = None,
    conversation_id: int | None = None,
    route_result: Any | None = None,
    tools: list[ToolDefinition] | None = None,
    execution_path: str | None = None,
    user_id: int | None = None,
    log_user_type: str | None = None,
    billing_context: dict[str, Any] | None = None,
    runtime_context: ConversationRuntimeContext | None = None,
    all_tool_names: list[str] | None = None,
    selected_skill_names: list[str] | None = None,
    context_sources: list[Any] | None = None,
    tool_use_policy: ToolUsePolicy | None = None,
    breach_retry_result: str | None = None,
    adapter_registry: Any = AdapterRegistry,
    query_engine_cls: Any = ConversationQueryEngine,
    model_request_override_builder: Any = build_model_request_overrides,
    engine_logger: Any = None,
) -> AsyncIterator[ChatChunk]:
    stream_start = time.perf_counter()
    plan = await build_runtime_stream_entrypoint_plan(
        engine,
        agent=agent,
        messages=messages,
        tenant_id=tenant_id,
        conversation_id=conversation_id,
        route_result=route_result,
        tools=tools,
        execution_path=execution_path,
        user_id=user_id,
        log_user_type=log_user_type,
        billing_context=billing_context,
        runtime_context=runtime_context,
        all_tool_names=all_tool_names,
        context_sources=context_sources,
        tool_use_policy=tool_use_policy,
        breach_retry_result=breach_retry_result,
        runtime_preparer=prepare_stream_runtime,
        adapter_registry=adapter_registry,
        query_engine_cls=query_engine_cls,
        model_request_override_builder=model_request_override_builder,
        engine_logger=(engine_logger or getattr(engine, "logger", None)),
    )
    runtime_context = plan.runtime_context
    provider = runtime_context.provider
    ai_model = runtime_context.ai_model
    model_code = runtime_context.model_code
    supports_streaming = (
        getattr(ai_model, "supports_streaming", True) if ai_model else True
    )
    total_tokens = 0
    input_tokens = 0
    output_tokens = 0
    streamed_output = ""
    runtime_info = runtime_context.runtime_info
    query_engine = plan.query_engine

    try:
        if not supports_streaming:
            active_logger = engine_logger or getattr(engine, "logger", None)
            if active_logger is not None:
                active_logger.info(
                    "Model {} does not support streaming, using runtime-v2 sync turn",
                    model_code,
                )
            response = await run_runtime_query_entrypoint(
                plan=plan,
                agent=agent,
                selected_skill_names=list(selected_skill_names or []),
            )
            total_tokens = response.total_tokens or 0
            input_tokens = response.input_tokens or 0
            output_tokens = response.output_tokens or 0
            streamed_output = response.message.content or ""
            yield ChatChunk(
                delta=response.message.content or "",
                role=response.message.role,
                finish_reason="stop",
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                tool_calls=response.tool_calls or response.message.tool_calls,
                metadata={
                    "runtime_model_info": runtime_info,
                    "runtime_turn_record": query_engine.turn_record,
                },
            )
        else:
            try:
                async for chunk in iterate_runtime_stream_entrypoint(
                    plan=plan,
                    agent=agent,
                    selected_skill_names=list(selected_skill_names or []),
                ):
                    if chunk.total_tokens is not None:
                        total_tokens = chunk.total_tokens
                    if chunk.input_tokens is not None:
                        input_tokens = chunk.input_tokens
                    if chunk.output_tokens is not None:
                        output_tokens = chunk.output_tokens
                    if chunk.delta:
                        streamed_output += chunk.delta
                    chunk.metadata = dict(chunk.metadata or {})
                    chunk.metadata.setdefault("runtime_model_info", runtime_info)
                    chunk.metadata.setdefault(
                        "runtime_turn_record",
                        query_engine.turn_record,
                    )
                    yield chunk
            except Exception as runtime_stream_exc:  # noqa: BLE001
                turn_record_metadata = dict(
                    getattr(
                        getattr(query_engine, "turn_record", None),
                        "metadata",
                        {},
                    )
                    or {}
                )
                had_fallback_blocking_chunk_before_error = bool(
                    turn_record_metadata.get(
                        "stream_failure_blocks_fallback",
                        turn_record_metadata.get(
                            "stream_failure_has_meaningful_chunk",
                        ),
                    ),
                )
                if had_fallback_blocking_chunk_before_error and query_engine is not None:
                    plan.request_log_data["runtime_v2_stream_failure_after_chunk"] = True
                    query_engine.turn_record.metadata[
                        "runtime_v2_stream_failure_after_chunk"
                    ] = True
                active_logger = engine_logger or getattr(engine, "logger", None)
                if active_logger is not None:
                    active_logger.warning(
                        "Runtime-v2 stream failed: runtime={} agent_id={} conversation_id={} had_fallback_blocking_chunk={} error_type={} error={}",
                        get_runtime_identity_tag(),
                        getattr(agent, "id", None),
                        conversation_id,
                        had_fallback_blocking_chunk_before_error,
                        type(runtime_stream_exc).__name__,
                        str(runtime_stream_exc),
                    )
                raise
    except Exception as exc:  # noqa: BLE001
        active_logger = engine_logger or getattr(engine, "logger", None)
        if active_logger is not None:
            active_logger.error(
                "Engine stream upstream failed: provider={} model={} conversation={} error={}",
                provider.code,
                model_code,
                conversation_id,
                str(exc),
                exc_info=True,
            )
        await plan.accounting.log_failure(
            error=exc,
            start_time=stream_start,
            runtime_context=runtime_context,
            request_context=plan.request_context,
            audit_context=plan.audit_context,
            turn_record=(
                query_engine.turn_record if query_engine is not None else None
            ),
            failure_log_message="Engine stream failure audit log failed",
        )
        raise

    try:
        await plan.accounting.finalize_success(
            runtime_context=runtime_context,
            request_context=plan.request_context,
            audit_context=plan.audit_context,
            output_text=streamed_output,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            start_time=stream_start,
            turn_record=(query_engine.turn_record if query_engine is not None else None),
            success_log_message="Engine stream call log failed",
            flush_db=True,
            require_estimated_input_for_metering=True,
        )
    except Exception as tail_exc:  # noqa: BLE001
        active_logger = engine_logger or getattr(engine, "logger", None)
        if active_logger is not None:
            active_logger.error(
                "Stream tail metering/flush failed (stream still completes): model={} error={}",
                model_code,
                str(tail_exc),
            )


async def prepare_stream_runtime(
    engine: Any,
    *,
    agent: Any,
    messages: list[ChatMessage],
    tenant_id: int | None,
    route_result: Any | None = None,
    skip_metering_preflight: bool = False,
) -> ConversationRuntimeContext:
    return await engine._runtime_preflight().prepare(
        agent=agent,
        messages=messages,
        tenant_id=tenant_id,
        route_result=route_result,
        skip_metering_preflight=skip_metering_preflight,
    )
