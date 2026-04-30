"""Tool call loop support extracted from BaseEngine."""

from __future__ import annotations

from typing import Any

from app.ai.tools.types import ToolDefinition, ToolResult
from app.ai.types import ChatMessage, ChatResponse
from app.models.ai.agent import Agent

from .base_identity_support import log_user_type_for_call_log
from .tool_call_loop_callbacks_factory import build_tool_call_loop_callbacks
from .tool_call_loop_policy import ToolCallLoopPolicy
from .tool_call_loop_runtime import ToolCallLoopRuntime, run_tool_call_loop
from .types import (
    ExecutionBudget,
    ExecutionRequest,
    ResearchContinuationContext,
    ToolUsePolicy,
)


class BaseToolLoopSupport:
    async def _handle_tool_calls(
        self,
        agent: Agent,
        messages: list[ChatMessage],
        response: ChatResponse,
        tools: list[ToolDefinition],
        all_tools: list[ToolDefinition] | None,
        request: ExecutionRequest,
        skip_final_call: bool = False,
        route_result: Any | None = None,
        tool_consent_modes: dict[str, str] | None = None,
        continuation_context: ResearchContinuationContext | None = None,
        selected_skill_names: list[str] | None = None,
        context_sources: list[Any] | None = None,
        tool_use_policy: ToolUsePolicy | None = None,
        execution_budget: ExecutionBudget | None = None,
        starting_total_tokens: int | None = None,
        starting_completion_tokens: int | None = None,
    ) -> tuple[ChatResponse | None, list[ToolResult], int, int]:
        """
        Handle tool call loop.

        When LLM returns tool_calls, executes tools and appends results to messages,
        then calls LLM again until no more tool_calls or max rounds reached.

        Args:
            agent: Agent
            messages: Current message list (will be modified)
            response: LLM response
            tools: Tool definition list
            request: Original request
            skip_final_call: Skip final LLM call (for streaming path, caller handles streaming)
            route_result: ModelRouter route result (maintains model consistency within tool call loop)

        Returns:
            (final_response, all_tool_results, total_tokens, completion_tokens)
            final_response is None when skip_final_call=True
        """
        async def _call_followup_llm(
            round_tools: list[ToolDefinition],
            round_policy: ToolUsePolicy,
        ) -> ChatResponse:
            return await self._call_llm(
                agent=agent,
                messages=messages,
                tools=round_tools,
                all_tool_names=[tool.name for tool in (all_tools or tools or [])],
                tool_use_policy=round_policy,
                tenant_id=request.tenant_id,
                user_id=request.user_id,
                conversation_id=request.conversation_id,
                billing_context=request.billing_context,
                route_result=route_result,
                log_user_type=log_user_type_for_call_log(request.user_role),
                selected_skill_names=selected_skill_names,
                context_sources=context_sources,
            )

        runtime = ToolCallLoopRuntime(
            sandbox=self.sandbox,
            agent=agent,
            messages=messages,
            response=response,
            tools=tools,
            all_tools=all_tools,
            request=request,
            skip_final_call=skip_final_call,
            tool_consent_modes=tool_consent_modes or {},
            continuation_context=continuation_context,
            tool_use_policy=tool_use_policy,
            execution_budget=execution_budget,
            starting_total_tokens=starting_total_tokens,
            starting_completion_tokens=starting_completion_tokens,
        )
        policy = ToolCallLoopPolicy(
            messages_have_blocking_pending_interaction=self._messages_have_blocking_pending_interaction,
            first_incomplete_requested_family=self._first_incomplete_requested_family,
            allowed_tool_names_for_family=self._allowed_tool_names_for_family,
            build_ordered_capability_hint=self._build_ordered_capability_hint,
            needs_fetch_url_before_summary=self._needs_fetch_url_before_summary,
            apply_fetch_url_only_gate=self._apply_fetch_url_only_gate,
            restrict_tools_to_names=self._restrict_tools_to_names,
        )
        callbacks = build_tool_call_loop_callbacks(
            policy=policy,
            ordered_requested_families_from_intents=self._ordered_requested_families_from_intents,
            keep_tool_calls_for_round=self._keep_tool_calls_for_round,
            mark_multi_family_progress=self._mark_multi_family_progress,
            budget_exit_response=self._budget_exit_response,
            call_followup_llm=_call_followup_llm,
        )
        return await run_tool_call_loop(runtime=runtime, callbacks=callbacks)


__all__ = ["BaseToolLoopSupport"]
