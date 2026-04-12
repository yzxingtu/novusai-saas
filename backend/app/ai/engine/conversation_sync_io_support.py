"""Support helpers for the sync IO adapter."""

from __future__ import annotations

from typing import Any

from app.ai.tools.types import ToolDefinition
from app.ai.types import ChatMessage, ChatResponse

from .base import log_user_type_for_call_log
from .model_policy import build_model_request_overrides
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
    **kwargs: Any,
) -> ToolBatchResult:
    outcome = await engine._handle_tool_calls(
        agent=agent,
        messages=messages,
        response=response,
        tools=tools,
        all_tools=prep.all_tools,
        request=request,
        route_result=prep.route_result,
        tool_consent_modes=prep.tool_consent_modes,
        continuation_context=prep.continuation_context,
        selected_skill_names=selected_skill_names,
        context_sources=context_sources,
        execution_budget=prep.execution_budget,
        **kwargs,
    )
    normalized_response, tool_results, total_tokens, completion_tokens_used = (
        engine._normalize_tool_call_outcome(outcome)
    )
    return ToolBatchResult(
        response=normalized_response,
        tool_results=list(tool_results),
        total_tokens=total_tokens,
        completion_tokens_used=completion_tokens_used,
    )
