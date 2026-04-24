"""Runtime-v2 provider/query-engine bridge for ConversationEngine."""

from __future__ import annotations

import time
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

from app.ai.adapters import AdapterRegistry
from app.ai.failover import FailoverService
from app.ai.routing.routing_contracts import RouteResult
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


@dataclass(frozen=True)
class RuntimeModelFailoverSelection:
    route_result: RouteResult
    metadata: dict[str, Any]


def _turn_record_metadata(
    turn_record: Any | None,
    *,
    create: bool = False,
) -> dict[str, Any] | None:
    if isinstance(turn_record, dict):
        metadata = turn_record.get("metadata")
        if isinstance(metadata, dict):
            return metadata
        if not create:
            return None
        metadata = {}
        turn_record["metadata"] = metadata
        return metadata

    metadata = getattr(turn_record, "metadata", None)
    if isinstance(metadata, dict):
        return metadata
    if not create or turn_record is None:
        return None
    metadata = {}
    try:
        setattr(turn_record, "metadata", metadata)
    except Exception:
        return None
    return metadata


def _turn_record_protocol_path(turn_record: Any | None) -> str:
    if isinstance(turn_record, dict):
        return str(turn_record.get("protocol_path") or "").strip()
    return str(getattr(turn_record, "protocol_path", "") or "").strip()


def _plan_request_log_data(
    plan: Any,
    *,
    create: bool = False,
) -> dict[str, Any]:
    request_log_data = getattr(plan, "request_log_data", None)
    if isinstance(request_log_data, dict):
        return request_log_data
    if not create:
        return {}
    request_log_data = {}
    try:
        setattr(plan, "request_log_data", request_log_data)
    except Exception:
        return {}
    return request_log_data


def _attach_runtime_failure_metadata(
    exc: BaseException,
    *,
    runtime_info: dict[str, Any] | None,
    query_engine: Any | None,
) -> None:
    if isinstance(runtime_info, dict) and runtime_info:
        setattr(exc, "_novusai_runtime_model_info", dict(runtime_info))

    turn_record = (
        getattr(query_engine, "turn_record", None) if query_engine is not None else None
    )
    if turn_record is None:
        return

    setattr(exc, "_novusai_runtime_turn_record", turn_record)
    protocol_path = _turn_record_protocol_path(turn_record)
    if protocol_path:
        setattr(exc, "_novusai_runtime_protocol_path", protocol_path)


async def _resolve_runtime_model_failover(
    engine: Any,
    *,
    runtime_context: ConversationRuntimeContext | None,
    tools: list[ToolDefinition] | None,
    error: BaseException,
    logger: Any | None,
) -> RuntimeModelFailoverSelection | None:
    if runtime_context is None or runtime_context.ai_model is None:
        return None
    if not FailoverService.should_record_runtime_failure(error):
        return None

    provider = runtime_context.provider
    provider_id = int(getattr(provider, "id", 0) or 0)
    model_id = int(getattr(runtime_context.ai_model, "id", 0) or 0)
    failover = FailoverService(engine.db)

    if provider_id > 0:
        await failover.record_provider_runtime_failure(
            provider_id,
            model_id=model_id or None,
            error=error,
        )

    fallback_model = await failover.get_fallback_model(
        model_id,
        needs_vision=bool(runtime_context.is_vision),
        needs_audio=bool(runtime_context.is_audio),
        needs_video=bool(runtime_context.is_video),
        needs_fc=bool(tools),
        min_context_window=int(runtime_context.estimated_input or 0) or None,
    )
    if fallback_model is None or fallback_model.id == model_id:
        return None

    metadata = {
        "from_provider_id": provider_id or None,
        "from_provider_code": getattr(provider, "code", None),
        "from_model_id": model_id or None,
        "from_model_code": runtime_context.model_code,
        "to_provider_id": int(getattr(fallback_model, "provider_id", 0) or 0) or None,
        "to_provider_code": getattr(getattr(fallback_model, "provider", None), "code", None),
        "to_model_id": int(getattr(fallback_model, "id", 0) or 0) or None,
        "to_model_code": getattr(fallback_model, "code", None),
        "trigger_error_type": type(error).__name__,
        "trigger_error_code": str(getattr(error, "error_code", "") or "").strip() or None,
    }
    metadata = {key: value for key, value in metadata.items() if value is not None}

    if logger is not None:
        logger.warning(
            "Runtime-v2 model failover selected: from_provider={} from_model={} to_provider={} to_model={} trigger_error_type={}",
            metadata.get("from_provider_code"),
            metadata.get("from_model_code"),
            metadata.get("to_provider_code"),
            metadata.get("to_model_code"),
            metadata.get("trigger_error_type"),
        )

    return RuntimeModelFailoverSelection(
        route_result=RouteResult(
            provider_code=fallback_model.provider.code,
            model_code=fallback_model.code,
            model_id=fallback_model.id,
            tier=getattr(fallback_model, "tier", None),
            reason="runtime_provider_failover",
            is_overridden=True,
        ),
        metadata=metadata,
    )


def _record_runtime_failover_metadata(plan: Any, metadata: dict[str, Any]) -> None:
    if not isinstance(metadata, dict) or not metadata:
        return

    request_log_data = _plan_request_log_data(plan, create=True)
    request_log_data["runtime_model_failover"] = dict(metadata)

    turn_record = getattr(getattr(plan, "query_engine", None), "turn_record", None)
    turn_record_metadata = _turn_record_metadata(turn_record, create=True)
    if isinstance(turn_record_metadata, dict):
        turn_record_metadata["runtime_model_failover"] = dict(metadata)


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
    skip_metering_preflight: bool,
    adapter_registry: Any = AdapterRegistry,
    query_engine_cls: Any = ConversationQueryEngine,
    model_request_override_builder: Any = build_model_request_overrides,
    accounting_builder: Any = None,
    engine_logger: Any = None,
) -> tuple[ChatResponse, ConversationQueryEngine]:
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
        skip_metering_preflight=skip_metering_preflight,
        runtime_preparer=prepare_stream_runtime,
        adapter_registry=adapter_registry,
        query_engine_cls=query_engine_cls,
        model_request_override_builder=model_request_override_builder,
        accounting_builder=accounting_builder,
    )
    active_logger = engine_logger or getattr(engine, "logger", None)
    failover_attempted = False

    while True:
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
            break
        except Exception as exc:  # noqa: BLE001
            if not failover_attempted:
                failover_selection = await _resolve_runtime_model_failover(
                    engine,
                    runtime_context=runtime_context,
                    tools=tools,
                    error=exc,
                    logger=active_logger,
                )
                if failover_selection is not None:
                    fallback_runtime_context = await prepare_stream_runtime(
                        engine,
                        agent=agent,
                        messages=messages,
                        tenant_id=tenant_id,
                        route_result=failover_selection.route_result,
                        skip_metering_preflight=skip_metering_preflight,
                    )
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
                        route_result=failover_selection.route_result,
                        log_user_type=log_user_type,
                        context_sources=context_sources,
                        execution_path=execution_path,
                        extra_kwargs=extra_kwargs,
                        runtime_context=fallback_runtime_context,
                        skip_metering_preflight=skip_metering_preflight,
                        runtime_preparer=prepare_stream_runtime,
                        adapter_registry=adapter_registry,
                        query_engine_cls=query_engine_cls,
                        model_request_override_builder=model_request_override_builder,
                        accounting_builder=accounting_builder,
                    )
                    _record_runtime_failover_metadata(
                        plan,
                        failover_selection.metadata,
                    )
                    failover_attempted = True
                    continue

            if active_logger is not None:
                active_logger.error(
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

    runtime_context = plan.runtime_context
    metadata = dict(getattr(response, "metadata", {}) or {})
    metadata.setdefault("runtime_model_info", runtime_context.runtime_info)
    metadata["runtime_turn_record"] = plan.query_engine.turn_record
    runtime_failover_metadata = _plan_request_log_data(plan).get(
        "runtime_model_failover"
    )
    if isinstance(runtime_failover_metadata, dict) and runtime_failover_metadata:
        metadata["runtime_model_failover"] = dict(runtime_failover_metadata)
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
    extra_kwargs: dict[str, Any] | None = None,
    user_id: int | None = None,
    log_user_type: str | None = None,
    billing_context: dict[str, Any] | None = None,
    runtime_context: ConversationRuntimeContext | None = None,
    all_tool_names: list[str] | None = None,
    selected_skill_names: list[str] | None = None,
    context_sources: list[Any] | None = None,
    tool_use_policy: ToolUsePolicy | None = None,
    breach_retry_result: str | None = None,
    skip_metering_preflight: bool = False,
    adapter_registry: Any = AdapterRegistry,
    query_engine_cls: Any = ConversationQueryEngine,
    model_request_override_builder: Any = build_model_request_overrides,
    accounting_builder: Any = None,
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
        extra_kwargs=extra_kwargs,
        user_id=user_id,
        log_user_type=log_user_type,
        billing_context=billing_context,
        runtime_context=runtime_context,
        all_tool_names=all_tool_names,
        context_sources=context_sources,
        tool_use_policy=tool_use_policy,
        breach_retry_result=breach_retry_result,
        skip_metering_preflight=skip_metering_preflight,
        runtime_preparer=prepare_stream_runtime,
        adapter_registry=adapter_registry,
        query_engine_cls=query_engine_cls,
        model_request_override_builder=model_request_override_builder,
        accounting_builder=accounting_builder,
        engine_logger=(engine_logger or getattr(engine, "logger", None)),
    )
    total_tokens = 0
    input_tokens = 0
    output_tokens = 0
    streamed_output = ""
    streamed_chunk_count = 0
    failover_attempted = False

    while True:
        runtime_context = plan.runtime_context
        provider = runtime_context.provider
        ai_model = runtime_context.ai_model
        model_code = runtime_context.model_code
        supports_streaming = (
            getattr(ai_model, "supports_streaming", True) if ai_model else True
        )
        runtime_info = runtime_context.runtime_info
        query_engine = plan.query_engine
        runtime_failover_metadata = _plan_request_log_data(plan).get(
            "runtime_model_failover"
        )

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
                streamed_chunk_count += 1
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
                        **(
                            {
                                "runtime_model_failover": dict(
                                    runtime_failover_metadata
                                )
                            }
                            if isinstance(runtime_failover_metadata, dict)
                            else {}
                        ),
                    },
                )
            else:
                try:
                    async for chunk in iterate_runtime_stream_entrypoint(
                        plan=plan,
                        agent=agent,
                        selected_skill_names=list(selected_skill_names or []),
                    ):
                        streamed_chunk_count += 1
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
                        if isinstance(runtime_failover_metadata, dict):
                            chunk.metadata.setdefault(
                                "runtime_model_failover",
                                dict(runtime_failover_metadata),
                            )
                        yield chunk
                except Exception as runtime_stream_exc:  # noqa: BLE001
                    _attach_runtime_failure_metadata(
                        runtime_stream_exc,
                        runtime_info=runtime_info,
                        query_engine=query_engine,
                    )
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
                    if not had_fallback_blocking_chunk_before_error:
                        had_fallback_blocking_chunk_before_error = bool(
                            str(streamed_output or "").strip()
                        )
                    setattr(
                        runtime_stream_exc,
                        "_novusai_stream_failover_blocked",
                        had_fallback_blocking_chunk_before_error,
                    )
                    if had_fallback_blocking_chunk_before_error and query_engine is not None:
                        _plan_request_log_data(plan, create=True)[
                            "runtime_v2_stream_failure_after_chunk"
                        ] = True
                        turn_record_metadata = _turn_record_metadata(
                            query_engine.turn_record,
                            create=True,
                        )
                        if isinstance(turn_record_metadata, dict):
                            turn_record_metadata[
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
            break
        except Exception as exc:  # noqa: BLE001
            _attach_runtime_failure_metadata(
                exc,
                runtime_info=runtime_info,
                query_engine=query_engine,
            )
            failover_blocked = bool(
                getattr(exc, "_novusai_stream_failover_blocked", False)
            )
            if (
                not failover_attempted
                and not failover_blocked
            ):
                failover_selection = await _resolve_runtime_model_failover(
                    engine,
                    runtime_context=runtime_context,
                    tools=tools,
                    error=exc,
                    logger=(engine_logger or getattr(engine, "logger", None)),
                )
                if failover_selection is not None:
                    fallback_runtime_context = await prepare_stream_runtime(
                        engine,
                        agent=agent,
                        messages=messages,
                        tenant_id=tenant_id,
                        route_result=failover_selection.route_result,
                        skip_metering_preflight=skip_metering_preflight,
                    )
                    plan = await build_runtime_stream_entrypoint_plan(
                        engine,
                        agent=agent,
                        messages=messages,
                        tenant_id=tenant_id,
                        conversation_id=conversation_id,
                        route_result=failover_selection.route_result,
                        tools=tools,
                        execution_path=execution_path,
                        extra_kwargs=extra_kwargs,
                        user_id=user_id,
                        log_user_type=log_user_type,
                        billing_context=billing_context,
                        runtime_context=fallback_runtime_context,
                        all_tool_names=all_tool_names,
                        context_sources=context_sources,
                        tool_use_policy=tool_use_policy,
                        breach_retry_result=breach_retry_result,
                        skip_metering_preflight=skip_metering_preflight,
                        runtime_preparer=prepare_stream_runtime,
                        adapter_registry=adapter_registry,
                        query_engine_cls=query_engine_cls,
                        model_request_override_builder=model_request_override_builder,
                        accounting_builder=accounting_builder,
                        engine_logger=(engine_logger or getattr(engine, "logger", None)),
                    )
                    _record_runtime_failover_metadata(
                        plan,
                        failover_selection.metadata,
                    )
                    failover_attempted = True
                    continue
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

    runtime_context = plan.runtime_context
    query_engine = plan.query_engine
    model_code = runtime_context.model_code

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
