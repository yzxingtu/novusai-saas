"""
Execution support mixin for BaseEngine.

Provides shared execution helpers extracted from BaseEngine:
- _prepare_execution
- _call_llm
- _log_tool_contract_diagnostics
- _log_web_research_contract_diagnostics
- _budget_exit_response
"""

from __future__ import annotations

from typing import Any

from app.ai.prompt_contracts import render_prompt_contract
from app.ai.skills.resolver import SkillResolveResult
from app.ai.tools.types import ToolDefinition
from app.ai.types import ChatMessage, ChatResponse
from app.core.logging import LogManager
from app.core.runtime_identity import get_runtime_identity_tag
from app.models.ai.agent import Agent

from .budget_helpers import budget_exit_response as _budget_exit_response_impl
from .llm_call_orchestrator import execute_llm_call
from .prepare_execution_pipeline import (
    prepare_execution_with_defaults as _prepare_execution_with_defaults_impl,
)
from .tool_contract_retry_helpers import (
    log_tool_contract_diagnostics_default as _log_tool_contract_diagnostics_default_impl,
)
from .tool_contract_retry_helpers import (
    log_web_research_contract_diagnostics_default as _log_web_research_contract_diagnostics_default_impl,
)
from .types import (
    ExecutionRequest,
    PreparedExecution,
    ResearchContinuationContext,
    ToolUsePolicy,
)

logger = LogManager.get_logger("ai.engine")


class BaseEngineExecutionSupport:
    """
    Execution support mixin for BaseEngine.

    Expects the owning class to provide:
    - db, gateway, sandbox
    - _attach_intent_plan_to_input_variables(...)
    - _prepare_llm_gateway_call(...)
    - _apply_llm_response_metadata(...)
    """

    async def _prepare_execution(
        self,
        agent: Agent,
        request: ExecutionRequest,
        skill_result: SkillResolveResult | None = None,
    ) -> PreparedExecution:
        """
        Build execution context (shared pre-logic for execute / stream_execute).

        Includes:
        1. Use pre-resolved Skill result (or fallback to internal resolve)
        2. Build message list (system + history)
        3. RAG knowledge base injection
        4. Tool optimization
        5. Tool awareness hint injection

        Args:
            agent: Agent model instance
            request: Execution request
            skill_result: Pre-resolved Skill result (from Dispatcher layer)

        Returns:
            PreparedExecution context
        """
        prep = await _prepare_execution_with_defaults_impl(
            db=self.db,
            base_engine=self,
            sandbox=self.sandbox,
            agent=agent,
            request=request,
            skill_result=skill_result,
            render_contract=render_prompt_contract,
        )
        self._attach_intent_plan_to_input_variables(
            request.input_variables,
            prep.intent_plan,
        )
        return prep

    async def _call_llm(
        self,
        agent: Agent,
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
    ) -> ChatResponse:
        """
        Call LLM.

        Args:
            agent: Agent (with model config)
            messages: Message list
            tools: Tool definition list
            tenant_id: Tenant ID
            user_id: User ID
            route_result: ModelRouter route result (None uses agent's original model)
        """
        del selected_skill_names, context_sources
        return await execute_llm_call(
            db=self.db,
            gateway=self.gateway,
            logger=logger,
            runtime_tag=get_runtime_identity_tag(),
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
            prepare_llm_gateway_call=self._prepare_llm_gateway_call,
            apply_llm_response_metadata=self._apply_llm_response_metadata,
        )

    def _log_tool_contract_diagnostics(
        self,
        *,
        agent: Any,
        messages: list[ChatMessage],
        response: ChatResponse | None,
        tools: list[ToolDefinition],
        policy: ToolUsePolicy,
        conversation_id: int | None,
        breach_type: str,
        retry_result: str,
        continuation: ResearchContinuationContext | None = None,
    ) -> None:
        _ = self
        _log_tool_contract_diagnostics_default_impl(
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

    def _log_web_research_contract_diagnostics(
        self,
        *,
        agent: Any,
        messages: list[ChatMessage],
        response: ChatResponse,
        tools: list[ToolDefinition],
        continuation: ResearchContinuationContext | None,
        conversation_id: int | None,
    ) -> None:
        _ = self
        _log_web_research_contract_diagnostics_default_impl(
            agent=agent,
            messages=messages,
            response=response,
            tools=tools,
            continuation=continuation,
            conversation_id=conversation_id,
        )

    _budget_exit_response = staticmethod(_budget_exit_response_impl)
