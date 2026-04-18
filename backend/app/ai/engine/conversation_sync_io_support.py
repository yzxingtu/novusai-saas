"""Support helpers for the sync IO adapter."""

from __future__ import annotations

from typing import Any

from app.ai.tools.types import ToolDefinition
from app.ai.types import ChatMessage, ChatResponse

from .base import log_user_type_for_call_log
from .execution_state_machine import get_current_execution_state_machine
from .model_policy import build_model_request_overrides
from .stream_output_projection import build_text_round_response
from .stream_runtime_contract import build_stream_runtime_contract
from .stream_tool_batch_runtime import (
    StreamToolBatchCallbacks,
    StreamToolBatchRuntimeInput,
    run_stream_tool_batch,
)
from .turn_executor import ModelRoundResult, ToolBatchResult
from .types import ExecutionRequest, ToolUsePolicy


def _resolve_token_usage(response: ChatResponse) -> tuple[int, int]:
    total_tokens = int(response.total_tokens or 0)
    completion_tokens_used = int(
        response.output_tokens
        if response.output_tokens is not None
        else total_tokens
    )
    return total_tokens, completion_tokens_used


async def call_sync_llm(
    *,
    engine: Any,
    agent: Any,
    request: ExecutionRequest,
    prep: Any,
    messages: list[ChatMessage],
    tools: list[ToolDefinition] | None,
    tool_use_policy: ToolUsePolicy,
    selected_skill_names: list[str],
    context_sources: list[Any],
    **kwargs: Any,
) -> ModelRoundResult:
    runtime_call_overrides = build_model_request_overrides(
        execution_path=getattr(prep, "execution_path", None),
        tools=tools,
    )
    response = await engine._call_llm(
        agent=agent,
        messages=messages,
        tools=tools,
        all_tool_names=[tool.name for tool in prep.all_tools],
        tool_use_policy=tool_use_policy,
        tenant_id=request.tenant_id,
        user_id=request.user_id,
        conversation_id=request.conversation_id,
        billing_context=request.billing_context,
        route_result=prep.route_result,
        log_user_type=log_user_type_for_call_log(request.user_role),
        selected_skill_names=selected_skill_names,
        context_sources=context_sources,
        execution_path=getattr(prep, "execution_path", None),
        extra_kwargs=runtime_call_overrides or None,
        **kwargs,
    )
    total_tokens, completion_tokens_used = _resolve_token_usage(response)
    return ModelRoundResult(
        response=response,
        total_tokens=total_tokens,
        completion_tokens_used=completion_tokens_used,
    )


async def handle_sync_tool_calls(
    *,
    engine: Any,
    agent: Any,
    request: ExecutionRequest,
    prep: Any,
    response: ChatResponse,
    tools: list[ToolDefinition],
    messages: list[ChatMessage],
    selected_skill_names: list[str],
    context_sources: list[Any],
    runtime_contract: Any | None = None,
    **kwargs: Any,
) -> ToolBatchResult:
    _ = agent, selected_skill_names, context_sources
    active_runtime_contract = runtime_contract or build_stream_runtime_contract(engine)
    tool_calls = list(response.tool_calls or response.message.tool_calls or [])
    tool_calls, _truncated_after_navigation = (
        active_runtime_contract.truncate_tool_calls_after_navigation(tool_calls)
    )

    state = get_current_execution_state_machine()

    async def _emit_event(_payload: dict[str, Any]) -> None:
        return None

    async def _emit_chunk(_text: str) -> None:
        return None

    def _budget_exit_reason() -> str | None:
        if state is None:
            return None
        return state.budget_exit_reason()

    def _register_budget_exit(reason: str | None) -> None:
        if state is None or not reason:
            return
        state.register_provider_failure(
            kind="budget_exit",
            event={"kind": "budget_exit", "reason": reason},
        )

    runtime_outcome = await run_stream_tool_batch(
        runtime=StreamToolBatchRuntimeInput(
            sandbox=engine.sandbox,
            request=request,
            response=response,
            tools=tools,
            all_tools=prep.all_tools,
            tool_consent_modes=prep.tool_consent_modes,
            messages=messages,
            tool_calls=tool_calls,
            starting_total_tokens=int(kwargs.get("starting_total_tokens") or 0),
            starting_completion_tokens=int(
                kwargs.get("starting_completion_tokens") or 0
            ),
            reasoning_content=(
                str(response.message.reasoning_content or response.message.content or "").strip()
                or None
            ),
        ),
        callbacks=StreamToolBatchCallbacks(
            emit_event=_emit_event,
            emit_chunk=_emit_chunk,
            budget_exit_reason=_budget_exit_reason,
            register_budget_exit=_register_budget_exit,
            build_text_round_response=build_text_round_response,
        ),
    )
    return ToolBatchResult(
        response=runtime_outcome.response,
        tool_results=list(runtime_outcome.tool_results),
        total_tokens=int(runtime_outcome.total_tokens or 0),
        completion_tokens_used=int(runtime_outcome.completion_tokens_used or 0),
    )
