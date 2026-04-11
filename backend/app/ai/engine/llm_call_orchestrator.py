"""LLM call orchestration helpers for the BaseEngine facade."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from app.ai.tools.types import ToolDefinition
from app.ai.types import ChatMessage, ChatResponse
from app.models.ai.agent import Agent

from .llm_call_helpers import PreparedLLMCall
from .types import ToolUsePolicy

PrepareLLMGatewayCall = Callable[..., Awaitable[PreparedLLMCall]]
ApplyLLMResponseMetadata = Callable[..., ChatResponse]


async def execute_llm_call(
    *,
    db: Any,
    gateway: Any,
    logger: Any,
    runtime_tag: str,
    agent: Agent,
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
    prepare_llm_gateway_call: PrepareLLMGatewayCall,
    apply_llm_response_metadata: ApplyLLMResponseMetadata,
) -> ChatResponse:
    prepared_call = await prepare_llm_gateway_call(
        db=db,
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
    )

    logger.info(
        "LLM call entry: runtime={} agent_id={} conversation_id={} provider={} model={} family={} mode={} allowed_tool_names={} tool_count={}",
        runtime_tag,
        getattr(agent, "id", None),
        conversation_id,
        prepared_call.llm_call_context.provider_code,
        prepared_call.llm_call_context.model_code,
        prepared_call.effective_policy.family,
        prepared_call.effective_policy.mode,
        prepared_call.effective_policy.allowed_tool_names,
        len(tools or []),
    )
    response = await gateway.chat(
        **prepared_call.gateway_kwargs,
    )
    return apply_llm_response_metadata(
        response,
        llm_call_context=prepared_call.llm_call_context,
    )
