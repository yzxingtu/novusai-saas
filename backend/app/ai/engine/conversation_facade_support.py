"""
ConversationEngine facade helpers.

Keep conversation.py thin by centralizing delegate/wrapper logic here.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from app.ai.tools.types import ToolDefinition, ToolResult
from app.ai.types import ChatChunk, ChatMessage, ChatResponse
from app.core.logging import LogManager
from app.services.ai.conversation_runtime_accounting import (
    ConversationRuntimeAccounting,
)

from .conversation_runtime_bridge import (
    call_runtime_query_turn as _call_runtime_query_turn_impl,
)
from .conversation_runtime_bridge import (
    prepare_stream_runtime as _prepare_stream_runtime_impl,
)
from .conversation_runtime_bridge import (
    stream_llm_chunks as _stream_llm_chunks_impl,
)
from .conversation_runtime_preflight import (
    ConversationRuntimeContext,
    ConversationRuntimePreflight,
)
from .execution_state_machine import ExecutionStateMachine
from .model_policy import build_model_request_overrides
from .stream_runtime_contract import (
    finalize_completed_turn_output,
    finalize_partial_turn_output,
)
from .tool_execution_helpers import (
    normalize_tool_call_outcome as _normalize_tool_call_outcome_impl,
)
from .tool_execution_helpers import (
    register_tool_failures as _register_tool_failures_impl,
)
from .tool_execution_helpers import (
    synthesize_tool_results_from_calls as _synthesize_tool_results_from_calls_impl,
)
from .turn_executor import (
    assistant_tool_round_count as _assistant_tool_round_count_impl,
)
from .turn_executor import (
    register_tool_round_delta as _register_tool_round_delta_impl,
)
from .types import ToolUsePolicy

logger = LogManager.get_logger("ai.engine.conversation")


def _default_adapter_registry() -> Any:
    from app.ai.adapters import AdapterRegistry

    return AdapterRegistry


def _default_query_engine_cls() -> Any:
    from app.ai.runtime.query_engine import ConversationQueryEngine

    return ConversationQueryEngine


def assistant_tool_round_count(messages: list[ChatMessage]) -> int:
    return _assistant_tool_round_count_impl(messages)


def register_tool_round_delta(
    state: ExecutionStateMachine,
    *,
    before_count: int,
    messages: list[ChatMessage],
) -> None:
    _register_tool_round_delta_impl(
        state,
        before_count=before_count,
        messages=messages,
    )


def register_tool_failures(
    state: ExecutionStateMachine,
    tool_results: list[Any],
) -> None:
    _register_tool_failures_impl(state, tool_results)


def normalize_tool_call_outcome(
    outcome: tuple[Any, ...],
) -> tuple[ChatResponse | None, list[Any], int, int]:
    return _normalize_tool_call_outcome_impl(outcome)


def synthesize_tool_results_from_calls(
    tool_calls: list[dict[str, Any]] | None,
) -> list[ToolResult]:
    return _synthesize_tool_results_from_calls_impl(tool_calls)


def build_runtime_preflight(engine: Any) -> ConversationRuntimePreflight:
    return ConversationRuntimePreflight(
        db=engine.db,
        gateway=engine.gateway,
    )


def build_runtime_accounting(
    engine: Any,
    *,
    cost_calculator: Any | None = None,
) -> ConversationRuntimeAccounting:
    init_kwargs: dict[str, Any] = {
        "gateway": engine.gateway,
        "db": engine.db,
    }
    if cost_calculator is not None:
        init_kwargs["cost_calculator"] = cost_calculator
    return ConversationRuntimeAccounting(**init_kwargs)


async def finalize_partial_output(
    engine: Any,
    *,
    agent: Any,
    request: Any,
    prep: Any,
    messages: list[ChatMessage],
    response: ChatResponse | None,
    state: ExecutionStateMachine,
    tool_results: list[ToolResult],
    reason: str,
    total_tokens: int,
    completion_tokens_used: int,
    selected_skill_names: list[str],
    context_sources: list[Any],
) -> tuple[str, int, int]:
    return await finalize_partial_turn_output(
        agent=agent,
        request=request,
        prep=prep,
        messages=messages,
        response=response,
        state=state,
        tool_results=tool_results,
        reason=reason,
        total_tokens=total_tokens,
        completion_tokens_used=completion_tokens_used,
        selected_skill_names=selected_skill_names,
        context_sources=context_sources,
    )


async def finalize_completed_output(
    engine: Any,
    *,
    agent: Any,
    request: Any,
    prep: Any,
    messages: list[ChatMessage],
    response: ChatResponse | None,
    state: ExecutionStateMachine,
    tool_results: list[ToolResult],
    reason: str,
    total_tokens: int,
    completion_tokens_used: int,
    selected_skill_names: list[str],
    context_sources: list[Any],
) -> tuple[str, int, int]:
    return await finalize_completed_turn_output(
        agent=agent,
        request=request,
        prep=prep,
        messages=messages,
        response=response,
        state=state,
        tool_results=tool_results,
        reason=reason,
        total_tokens=total_tokens,
        completion_tokens_used=completion_tokens_used,
        selected_skill_names=selected_skill_names,
        context_sources=context_sources,
    )


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
    adapter_registry: Any | None = None,
    query_engine_cls: Any | None = None,
    model_request_override_builder: Any | None = None,
    accounting_builder: Any | None = None,
    engine_logger: Any | None = None,
) -> tuple[ChatResponse, Any]:
    return await _call_runtime_query_turn_impl(
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
        selected_skill_names=selected_skill_names,
        context_sources=context_sources,
        execution_path=execution_path,
        extra_kwargs=extra_kwargs,
        skip_metering_preflight=skip_metering_preflight,
        adapter_registry=adapter_registry or _default_adapter_registry(),
        query_engine_cls=query_engine_cls or _default_query_engine_cls(),
        model_request_override_builder=(
            model_request_override_builder or build_model_request_overrides
        ),
        accounting_builder=accounting_builder,
        engine_logger=logger if engine_logger is None else engine_logger,
    )


async def call_llm(
    engine: Any,
    *,
    agent: Any,
    messages: list[ChatMessage],
    tools: list[ToolDefinition] | None = None,
    all_tool_names: list[str] | None = None,
    tool_use_policy: ToolUsePolicy | None = None,
    breach_retry_result: str | None = None,
    tenant_id: int | None = None,
    user_id: int | None = None,
    conversation_id: int | None = None,
    billing_context: dict[str, Any] | None = None,
    route_result: Any | None = None,
    log_user_type: str | None = None,
    selected_skill_names: list[str] | None = None,
    context_sources: list[Any] | None = None,
    execution_path: str | None = None,
    extra_kwargs: dict[str, Any] | None = None,
) -> ChatResponse:
    runtime_call_overrides = dict(extra_kwargs or {})
    if not runtime_call_overrides:
        runtime_call_overrides = build_model_request_overrides(
            execution_path=execution_path,
            tools=tools,
        )
    runtime_response, _runtime_query_engine = await engine._call_runtime_query_turn(
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
        selected_skill_names=selected_skill_names,
        context_sources=context_sources,
        execution_path=execution_path,
        extra_kwargs=runtime_call_overrides,
        skip_metering_preflight=False,
    )
    return runtime_response


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
    skip_metering_preflight: bool = False,
    adapter_registry: Any | None = None,
    query_engine_cls: Any | None = None,
    model_request_override_builder: Any | None = None,
    accounting_builder: Any | None = None,
    engine_logger: Any | None = None,
) -> AsyncIterator[ChatChunk]:
    async for chunk in _stream_llm_chunks_impl(
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
        selected_skill_names=selected_skill_names,
        context_sources=context_sources,
        tool_use_policy=tool_use_policy,
        breach_retry_result=breach_retry_result,
        skip_metering_preflight=skip_metering_preflight,
        adapter_registry=adapter_registry or _default_adapter_registry(),
        query_engine_cls=query_engine_cls or _default_query_engine_cls(),
        model_request_override_builder=(
            model_request_override_builder or build_model_request_overrides
        ),
        accounting_builder=accounting_builder,
        engine_logger=logger if engine_logger is None else engine_logger,
    ):
        yield chunk


async def prepare_stream_runtime(
    engine: Any,
    *,
    agent: Any,
    messages: list[ChatMessage],
    tenant_id: int | None,
    route_result: Any | None = None,
    skip_metering_preflight: bool = False,
) -> ConversationRuntimeContext:
    return await _prepare_stream_runtime_impl(
        engine,
        agent=agent,
        messages=messages,
        tenant_id=tenant_id,
        route_result=route_result,
        skip_metering_preflight=skip_metering_preflight,
    )


__all__ = [
    "assistant_tool_round_count",
    "build_runtime_accounting",
    "build_runtime_preflight",
    "call_llm",
    "call_runtime_query_turn",
    "finalize_completed_output",
    "finalize_partial_output",
    "normalize_tool_call_outcome",
    "prepare_stream_runtime",
    "register_tool_failures",
    "register_tool_round_delta",
    "stream_llm_chunks",
    "synthesize_tool_results_from_calls",
]
