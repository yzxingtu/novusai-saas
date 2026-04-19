from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.ai.engine.prepare_execution_pipeline import (
    PrepareExecutionCollaborators,
    build_prepared_execution_context,
    prepare_execution,
)
from app.ai.engine.prepare_execution_runtime_helpers import (
    PreparedExecutionRuntimeState,
)
from app.ai.engine.prepare_execution_tool_helpers import PreparedExecutionToolPlan
from app.ai.engine.types import (
    ExecutionRequest,
    PreparedExecution,
    ResearchContinuationContext,
    ToolUsePolicy,
)
from app.ai.skills.resolver import SkillResolveResult
from app.ai.tools.types import ToolDefinition
from app.ai.types import ChatMessage


class _FakeContextEngine:
    def __init__(self, assembly):
        self._assembly = assembly
        self.calls: list[str] = []

    async def ingest(self, agent, request):
        _ = agent, request
        self.calls.append("ingest")

    async def assemble(self, agent, request, skill_result=None):
        _ = agent, request, skill_result
        self.calls.append("assemble")
        return self._assembly

    async def compact(self, agent, request):
        _ = agent, request
        self.calls.append("compact")


def _build_assembly(**overrides):
    payload = {
        "messages": [ChatMessage(role="user", content="hello")],
        "rag_sources": [{"kb_id": 1}],
        "diagnostics": {},
        "estimated_tokens": 12,
        "rag_source_kinds": [],
        "compact_summary": None,
        "prune_stats": None,
        "memory_recall_slice": None,
        "context_compacted": False,
        "memory_flush_triggered": False,
        "memory_recalled": False,
        "system_prompt_additions": [],
        "capability_bundle": None,
    }
    payload.update(overrides)
    return SimpleNamespace(**payload)


def _build_request() -> ExecutionRequest:
    return ExecutionRequest(
        agent_id=1,
        tenant_id=7,
        user_id=9,
        conversation_id=11,
        messages=[ChatMessage(role="user", content="hello")],
        input_variables={},
    )


def _build_agent() -> SimpleNamespace:
    return SimpleNamespace(id=1, name="Researcher")


def _build_tool_plan(tool_name: str = "web_search") -> PreparedExecutionToolPlan:
    return PreparedExecutionToolPlan(
        tools=[ToolDefinition(name=tool_name, description="Search the web")],
        candidate_tool_names=[tool_name],
        tool_use_policy=ToolUsePolicy(
            family="web_research",
            mode="required",
            allowed_tool_names=[tool_name],
            reason="intent:web_research",
        ),
        tool_planner={"intent": "web_research"},
        optimize_event={"selected": 1, "total": 1},
        intent_plan=[],
        intent_flags={
            "has_knowledge_intent": False,
            "has_page_intent": False,
            "has_memory_intent": False,
            "memory_context_enabled": False,
        },
        explicit_requested_families=["web_research"],
        execution_path="normal",
        execution_budget=None,
        active_intent_id="intent-1",
    )


def _build_collaborators(*, context_engine, tool_plan, runtime_state):
    budget_guard = SimpleNamespace(register_preparation=MagicMock())
    finalize_runtime = AsyncMock(return_value=runtime_state)

    def _get_context_engine(**_kwargs):
        return context_engine

    def _plan_execution_tools(**_kwargs):
        return tool_plan

    def _build_prepared_execution(**kwargs):
        return PreparedExecution(
            messages=kwargs["messages"],
            tools=kwargs["tools"],
            all_tools=kwargs["all_tools"],
            continuation_context=kwargs["continuation_context"],
            tool_use_policy=kwargs["tool_use_policy"],
        )

    def _build_continuation_context(*_args, **_kwargs):
        return ResearchContinuationContext(
            current_user_text="hello",
            research_target_text="hello",
        )

    def _apply_execution_trust_policy(**_kwargs):
        return {}

    def _render_contract(*_args, **_kwargs):
        return "[PROMPT]"

    collaborators = PrepareExecutionCollaborators(
        get_context_engine=_get_context_engine,
        plan_execution_tools=_plan_execution_tools,
        finalize_prepared_execution_runtime=finalize_runtime,
        build_prepared_execution=_build_prepared_execution,
        build_web_research_continuation_context=_build_continuation_context,
        apply_execution_trust_policy=_apply_execution_trust_policy,
        render_contract=_render_contract,
        estimate_tokens=len,
        budget_guard=budget_guard,
    )
    return collaborators, finalize_runtime, budget_guard


@pytest.mark.asyncio
async def test_prepare_execution_pipeline_resolves_skill_result_and_applies_request_state() -> (
    None
):
    request = _build_request()
    agent = _build_agent()
    assembly = _build_assembly()
    context_engine = _FakeContextEngine(assembly)
    tool_plan = _build_tool_plan()
    runtime_state = PreparedExecutionRuntimeState(
        capability_injection_decision={},
        tool_consent_modes={"web_search": "auto"},
    )
    collaborators, finalize_runtime, budget_guard = _build_collaborators(
        context_engine=context_engine,
        tool_plan=tool_plan,
        runtime_state=runtime_state,
    )
    resolved_skill_result = SkillResolveResult(
        tools=[ToolDefinition(name="web_search", description="Search the web")]
    )

    with patch(
        "app.ai.skills.resolver.resolve_for_agent",
        new=AsyncMock(return_value=resolved_skill_result),
    ):
        prep = await prepare_execution(
            db=MagicMock(),
            base_engine=SimpleNamespace(),
            sandbox=MagicMock(),
            agent=agent,
            request=request,
            skill_result=None,
            collaborators=collaborators,
        )

    assert context_engine.calls == ["ingest", "assemble", "compact"]
    assert prep.tool_use_policy.family == "web_research"
    assert request.tool_use_policy == tool_plan.tool_use_policy
    assert request.tool_use_policy is not tool_plan.tool_use_policy
    assert finalize_runtime.await_args.kwargs["skill_result"] is resolved_skill_result
    budget_guard.register_preparation.assert_not_called()


@pytest.mark.asyncio
async def test_build_prepared_execution_context_skips_tool_exposure_without_sandbox() -> (
    None
):
    request = _build_request()
    assembly = _build_assembly()
    context_engine = _FakeContextEngine(assembly)
    tool_plan = _build_tool_plan()
    runtime_state = PreparedExecutionRuntimeState(
        capability_injection_decision={},
        tool_consent_modes={},
    )
    collaborators, _, _ = _build_collaborators(
        context_engine=context_engine,
        tool_plan=tool_plan,
        runtime_state=runtime_state,
    )
    skill_result = SkillResolveResult(
        tools=[ToolDefinition(name="web_search", description="Search the web")]
    )

    context_state = await build_prepared_execution_context(
        db=MagicMock(),
        base_engine=SimpleNamespace(),
        sandbox=None,
        agent=_build_agent(),
        request=request,
        skill_result=skill_result,
        collaborators=collaborators,
    )

    assert context_engine.calls == ["ingest", "assemble", "compact"]
    assert context_state.tools == []
    assert context_state.all_tools == []
    assert context_state.continuation_context is not None
