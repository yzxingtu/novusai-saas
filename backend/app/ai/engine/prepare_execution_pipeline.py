"""
Facade-friendly orchestration for ``BaseEngine._prepare_execution()``.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from app.ai.skills.activation import execution_tools_for_turn
from app.ai.skills.resolver import SkillResolveResult
from app.ai.tools.types import ToolDefinition
from app.ai.types import ChatMessage
from app.ai.utils.token_estimator import estimate_chat_message_tokens
from app.core.logging import LogManager

from .prepare_execution_runtime_helpers import PreparedExecutionRuntimeState
from .prepare_execution_tool_helpers import PreparedExecutionToolPlan
from .types import ExecutionRequest, PreparedExecution, ResearchContinuationContext

logger = LogManager.get_logger("ai.engine")


@dataclass(frozen=True)
class PrepareExecutionCollaborators:
    get_context_engine: Callable[..., Any]
    plan_execution_tools: Callable[..., PreparedExecutionToolPlan]
    finalize_prepared_execution_runtime: Callable[
        ..., Awaitable[PreparedExecutionRuntimeState]
    ]
    build_prepared_execution: Callable[..., PreparedExecution]
    build_web_research_continuation_context: Callable[..., ResearchContinuationContext]
    apply_execution_trust_policy: Callable[..., dict[str, str]]
    render_contract: Callable[..., str]
    estimate_tokens: Callable[[str], int]
    budget_guard: Any


@dataclass
class PreparedExecutionContextState:
    context_engine: Any
    context_assembly: Any
    messages: list[ChatMessage]
    rag_sources: list[dict[str, Any]] | None
    tools: list[ToolDefinition]
    all_tools: list[ToolDefinition]
    continuation_context: ResearchContinuationContext | None


@dataclass
class PreparedExecutionPipelineState:
    context: PreparedExecutionContextState
    tool_plan: PreparedExecutionToolPlan
    runtime_state: PreparedExecutionRuntimeState

    def apply_request_state(self, *, request: ExecutionRequest) -> None:
        request.tool_use_policy = dataclasses.replace(self.tool_plan.tool_use_policy)

    def build_prepared_execution(self) -> PreparedExecution:
        return self._build_prepared_execution()

    def _build_prepared_execution(self) -> PreparedExecution:
        return self._build_prepared_execution_fn(
            messages=self.context.messages,
            tools=self.tool_plan.tools,
            all_tools=self.context.all_tools,
            continuation_context=self.context.continuation_context,
            tool_use_policy=self.tool_plan.tool_use_policy,
            rag_sources=self.context.rag_sources,
            context_assembly=self.context.context_assembly,
            context_engine=self.context.context_engine,
            tool_planner=self.tool_plan.tool_planner,
            optimize_event=self.tool_plan.optimize_event,
            runtime_state=self.runtime_state,
            intent_plan=self.tool_plan.intent_plan,
            execution_path=self.tool_plan.execution_path,
            execution_budget=self.tool_plan.execution_budget,
            active_intent_id=self.tool_plan.active_intent_id,
        )

    _build_prepared_execution_fn: Callable[..., PreparedExecution] = dataclasses.field(
        repr=False
    )


async def resolve_prepare_execution_skill_result(
    *,
    db: Any,
    agent: Any,
    request: ExecutionRequest,
    skill_result: SkillResolveResult | None,
) -> SkillResolveResult | None:
    if skill_result is not None:
        return skill_result

    from app.ai.skills.resolver import resolve_for_agent

    return await resolve_for_agent(
        db,
        agent,
        tenant_id=request.tenant_id,
        user_role=getattr(request, "user_role", None),
        request=request,
    )


async def build_prepared_execution_context(
    *,
    db: Any,
    base_engine: Any,
    sandbox: Any,
    agent: Any,
    request: ExecutionRequest,
    skill_result: SkillResolveResult | None,
    collaborators: PrepareExecutionCollaborators,
) -> PreparedExecutionContextState:
    context_engine = collaborators.get_context_engine(
        db=db,
        base_engine=base_engine,
    )
    await context_engine.ingest(agent, request)
    context_assembly = await context_engine.assemble(
        agent,
        request,
        skill_result=skill_result,
    )
    await context_engine.compact(agent, request)

    messages = context_assembly.messages
    rag_sources = context_assembly.rag_sources
    tools = list(execution_tools_for_turn(skill_result)) if skill_result else []
    if tools and sandbox is None:
        logger.info(
            "Skip tool exposure because sandbox is unavailable: agent_id={} tool_count={}",
            agent.id,
            len(tools),
        )
        tools = []

    all_tools = list(tools)
    continuation_context = collaborators.build_web_research_continuation_context(
        messages,
        all_tools,
        request.input_variables,
    )
    return PreparedExecutionContextState(
        context_engine=context_engine,
        context_assembly=context_assembly,
        messages=messages,
        rag_sources=rag_sources,
        tools=tools,
        all_tools=all_tools,
        continuation_context=continuation_context,
    )


def register_prepared_execution_budget(
    *,
    collaborators: PrepareExecutionCollaborators,
    context_state: PreparedExecutionContextState,
    tool_plan: PreparedExecutionToolPlan,
) -> None:
    if tool_plan.execution_budget is None:
        return

    estimated_prompt_tokens = context_state.context_assembly.estimated_tokens
    prompt_tokens = (
        int(estimated_prompt_tokens)
        if estimated_prompt_tokens
        else sum(
            estimate_chat_message_tokens(message)
            for message in context_state.messages
        )
    )
    collaborators.budget_guard.register_preparation(
        tool_plan.execution_budget,
        prompt_tokens=prompt_tokens,
        candidate_tools_count=len(tool_plan.candidate_tool_names),
    )


async def build_prepared_execution_pipeline_state(
    *,
    db: Any,
    base_engine: Any,
    sandbox: Any,
    agent: Any,
    request: ExecutionRequest,
    skill_result: SkillResolveResult | None,
    collaborators: PrepareExecutionCollaborators,
) -> PreparedExecutionPipelineState:
    resolved_skill_result = await resolve_prepare_execution_skill_result(
        db=db,
        agent=agent,
        request=request,
        skill_result=skill_result,
    )
    context_state = await build_prepared_execution_context(
        db=db,
        base_engine=base_engine,
        sandbox=sandbox,
        agent=agent,
        request=request,
        skill_result=resolved_skill_result,
        collaborators=collaborators,
    )

    tool_plan = collaborators.plan_execution_tools(
        agent_id=getattr(agent, "id", None),
        conversation_id=request.conversation_id,
        request=request,
        messages=context_state.messages,
        tools=context_state.tools,
        all_tools=context_state.all_tools,
        diagnostics=context_state.context_assembly.diagnostics,
    )
    register_prepared_execution_budget(
        collaborators=collaborators,
        context_state=context_state,
        tool_plan=tool_plan,
    )

    runtime_state = await collaborators.finalize_prepared_execution_runtime(
        db=db,
        agent=agent,
        request=request,
        tools=tool_plan.tools,
        skill_result=resolved_skill_result,
        messages=context_state.messages,
        context_assembly=context_state.context_assembly,
        intent_plan=tool_plan.intent_plan,
        intent_flags=tool_plan.intent_flags,
        explicit_requested_families=tool_plan.explicit_requested_families,
        execution_path=tool_plan.execution_path,
        execution_budget=tool_plan.execution_budget,
        continuation_context=context_state.continuation_context,
        tool_planner=tool_plan.tool_planner,
        candidate_tool_names=tool_plan.candidate_tool_names,
        active_intent_id=tool_plan.active_intent_id,
        sandbox=sandbox,
        apply_execution_trust_policy=collaborators.apply_execution_trust_policy,
        render_contract=collaborators.render_contract,
    )
    return PreparedExecutionPipelineState(
        context=context_state,
        tool_plan=tool_plan,
        runtime_state=runtime_state,
        _build_prepared_execution_fn=collaborators.build_prepared_execution,
    )


async def prepare_execution(
    *,
    db: Any,
    base_engine: Any,
    sandbox: Any,
    agent: Any,
    request: ExecutionRequest,
    skill_result: SkillResolveResult | None,
    collaborators: PrepareExecutionCollaborators,
) -> PreparedExecution:
    state = await build_prepared_execution_pipeline_state(
        db=db,
        base_engine=base_engine,
        sandbox=sandbox,
        agent=agent,
        request=request,
        skill_result=skill_result,
        collaborators=collaborators,
    )
    state.apply_request_state(request=request)
    return state.build_prepared_execution()


def build_default_prepare_execution_collaborators(
    *,
    base_engine: Any,
    render_contract: Callable[..., str],
) -> PrepareExecutionCollaborators:
    from app.ai.context import get_context_engine
    from app.ai.utils.token_estimator import estimate_tokens

    from .budget_guard import BudgetGuard
    from .prepare_execution_runtime_helpers import (
        build_prepared_execution as _build_prepared_execution_impl,
    )
    from .prepare_execution_tool_helpers import (
        finalize_prepared_execution_runtime,
        plan_execution_tools,
    )

    return PrepareExecutionCollaborators(
        get_context_engine=get_context_engine,
        plan_execution_tools=plan_execution_tools,
        finalize_prepared_execution_runtime=finalize_prepared_execution_runtime,
        build_prepared_execution=_build_prepared_execution_impl,
        build_web_research_continuation_context=(
            base_engine._build_web_research_continuation_context
        ),
        apply_execution_trust_policy=base_engine._apply_execution_trust_policy,
        render_contract=render_contract,
        estimate_tokens=estimate_tokens,
        budget_guard=BudgetGuard,
    )


async def prepare_execution_with_defaults(
    *,
    db: Any,
    base_engine: Any,
    sandbox: Any,
    agent: Any,
    request: ExecutionRequest,
    skill_result: SkillResolveResult | None,
    render_contract: Callable[..., str],
) -> PreparedExecution:
    return await prepare_execution(
        db=db,
        base_engine=base_engine,
        sandbox=sandbox,
        agent=agent,
        request=request,
        skill_result=skill_result,
        collaborators=build_default_prepare_execution_collaborators(
            base_engine=base_engine,
            render_contract=render_contract,
        ),
    )
