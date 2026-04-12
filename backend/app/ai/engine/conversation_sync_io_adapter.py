"""Sync ConversationEngine IO adapter that delegates to runtime contracts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.ai.tools.types import ToolDefinition, ToolResult
from app.ai.types import ChatMessage, ChatResponse
from app.models.ai.agent import Agent

from .base import log_user_type_for_call_log
from .execution_state_machine import ExecutionStateMachine
from .model_policy import build_model_request_overrides
from .turn_executor import ModelRoundResult, ToolBatchResult
from .types import ExecutionRequest, ToolUsePolicy


@dataclass
class _SyncIOAdapter:
    engine: Any
    agent: Agent
    request: ExecutionRequest
    prep: Any
    selected_skill_names: list[str]
    context_sources: list[Any]
    runtime_contract: Any

    async def call_llm(
        self,
        *,
        messages: list[ChatMessage],
        tools: list[ToolDefinition] | None,
        tool_use_policy: ToolUsePolicy,
        **kwargs: Any,
    ) -> ModelRoundResult:
        runtime_call_overrides = build_model_request_overrides(
            execution_path=getattr(self.prep, "execution_path", None),
            tools=tools,
        )
        response = await self.engine._call_llm(
            agent=self.agent,
            messages=messages,
            tools=tools,
            all_tool_names=[tool.name for tool in self.prep.all_tools],
            tool_use_policy=tool_use_policy,
            tenant_id=self.request.tenant_id,
            user_id=self.request.user_id,
            conversation_id=self.request.conversation_id,
            billing_context=self.request.billing_context,
            route_result=self.prep.route_result,
            log_user_type=log_user_type_for_call_log(self.request.user_role),
            selected_skill_names=self.selected_skill_names,
            context_sources=self.context_sources,
            execution_path=getattr(self.prep, "execution_path", None),
            extra_kwargs=runtime_call_overrides or None,
            **kwargs,
        )
        total_tokens = int(response.total_tokens or 0)
        completion_tokens_used = int(
            response.output_tokens
            if response.output_tokens is not None
            else total_tokens
        )
        return ModelRoundResult(
            response=response,
            total_tokens=total_tokens,
            completion_tokens_used=completion_tokens_used,
        )

    async def handle_tool_calls(
        self,
        *,
        response: ChatResponse,
        tools: list[ToolDefinition],
        messages: list[ChatMessage],
        **kwargs: Any,
    ) -> ToolBatchResult:
        outcome = await self.engine._handle_tool_calls(
            agent=self.agent,
            messages=messages,
            response=response,
            tools=tools,
            all_tools=self.prep.all_tools,
            request=self.request,
            route_result=self.prep.route_result,
            tool_consent_modes=self.prep.tool_consent_modes,
            continuation_context=self.prep.continuation_context,
            selected_skill_names=self.selected_skill_names,
            context_sources=self.context_sources,
            execution_budget=self.prep.execution_budget,
            **kwargs,
        )
        normalized_response, tool_results, total_tokens, completion_tokens_used = (
            self.engine._normalize_tool_call_outcome(outcome)
        )
        return ToolBatchResult(
            response=normalized_response,
            tool_results=list(tool_results),
            total_tokens=total_tokens,
            completion_tokens_used=completion_tokens_used,
        )

    async def finalize_partial_output(
        self,
        *,
        messages: list[ChatMessage],
        response: ChatResponse | None,
        state: ExecutionStateMachine,
        tool_results: list[ToolResult],
        reason: str,
        total_tokens: int,
        completion_tokens_used: int,
    ) -> tuple[str, int, int]:
        return await self.runtime_contract.finalize_partial_output(
            agent=self.agent,
            request=self.request,
            prep=self.prep,
            messages=messages,
            response=response,
            state=state,
            tool_results=tool_results,
            reason=reason,
            total_tokens=total_tokens,
            completion_tokens_used=completion_tokens_used,
            selected_skill_names=self.selected_skill_names,
            context_sources=self.context_sources,
        )

    async def finalize_completed_output(
        self,
        *,
        messages: list[ChatMessage],
        response: ChatResponse | None,
        state: ExecutionStateMachine,
        tool_results: list[ToolResult],
        reason: str,
        total_tokens: int,
        completion_tokens_used: int,
    ) -> tuple[str, int, int]:
        return await self.runtime_contract.finalize_completed_output(
            agent=self.agent,
            request=self.request,
            prep=self.prep,
            messages=messages,
            response=response,
            state=state,
            tool_results=tool_results,
            reason=reason,
            total_tokens=total_tokens,
            completion_tokens_used=completion_tokens_used,
            selected_skill_names=self.selected_skill_names,
            context_sources=self.context_sources,
        )

    def should_retry_tool_contract_breach(
        self,
        *,
        response: ChatResponse | None,
        current_policy: ToolUsePolicy,
        tools: list[ToolDefinition],
        input_variables: dict[str, Any] | None,
    ) -> tuple[bool, ToolUsePolicy | None, str]:
        return self.runtime_contract.should_retry_tool_contract_breach(
            response=response,
            current_policy=current_policy,
            tools=tools,
            input_variables=input_variables,
        )

    def should_retry_web_research_contract_breach(
        self,
        *,
        messages: list[ChatMessage],
        response: ChatResponse | None,
        current_policy: ToolUsePolicy,
        tools: list[ToolDefinition],
        input_variables: dict[str, Any] | None,
        continuation: Any,
    ) -> tuple[bool, ToolUsePolicy | None, str]:
        return self.runtime_contract.should_retry_web_research_contract_breach(
            messages=messages,
            response=response,
            current_policy=current_policy,
            tools=tools,
            input_variables=input_variables,
            continuation=continuation,
        )

    def analyze_post_tool_contract_breach(
        self,
        *,
        messages: list[ChatMessage],
        response: ChatResponse | None,
        current_policy: ToolUsePolicy,
        tools: list[ToolDefinition],
        input_variables: dict[str, Any] | None,
    ) -> tuple[str | None, ToolUsePolicy | None, dict[str, Any]]:
        if response is None:
            return None, None, {}
        return self.runtime_contract.analyze_post_tool_contract_breach(
            messages=messages,
            response=response,
            current_policy=current_policy,
            tools=tools,
            input_variables=input_variables,
        )

    def restrict_tools_to_names(
        self,
        tools: list[ToolDefinition],
        allowed_tool_names: list[str] | None,
    ) -> list[ToolDefinition]:
        return self.runtime_contract.restrict_tools_to_names(tools, allowed_tool_names)

    def log_tool_contract_diagnostics(
        self,
        *,
        agent: Agent,
        messages: list[ChatMessage],
        response: ChatResponse | None,
        tools: list[ToolDefinition],
        policy: ToolUsePolicy,
        conversation_id: int | None,
        breach_type: str,
        retry_result: str,
        continuation: Any,
    ) -> None:
        self.runtime_contract.log_tool_contract_diagnostics(
            agent=agent,
            messages=messages,
            response=response,
            tools=tools,
            policy=policy,
            conversation_id=conversation_id,
            breach_type=breach_type,
            retry_result=retry_result,
            continuation=continuation,
        )

    async def emit_chunk(self, text: str) -> None:
        _ = text


__all__ = ["_SyncIOAdapter"]
