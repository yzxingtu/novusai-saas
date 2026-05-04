"""
Helpers for tool planning inside BaseEngine._prepare_execution().
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.ai.runtime.context_assembler import (
    ContextAssemblerState,
    ContextCapabilityBundleProjection,
)
from app.ai.runtime.manifest import AIRuntimeInventoryService
from app.ai.runtime.types import project_capability_bundle_to_tools
from app.ai.tools.types import ToolDefinition
from app.ai.types import ChatMessage
from app.core.logging import LogManager
from app.core.runtime_identity import get_runtime_identity_tag

from .budget_guard import BudgetGuard
from .path_selector import PathSelector
from .prepare_execution_runtime_helpers import (
    PreparedExecutionRuntimeState,
)
from .prepare_execution_runtime_helpers import (
    apply_prepared_execution_diagnostics as _apply_prepared_execution_diagnostics_impl,
)
from .prepare_execution_runtime_helpers import (
    apply_runtime_capability_injection as _apply_runtime_capability_injection_impl,
)
from .prepare_execution_runtime_helpers import (
    resolve_runtime_execution_state as _resolve_runtime_execution_state_impl,
)
from .system_prompt_helpers import (
    deserialize_intent_plan as _deserialize_intent_plan_impl,
)
from .system_prompt_helpers import (
    inject_runtime_summary as _inject_runtime_summary_impl,
)
from .system_prompt_helpers import (
    intent_completion_signals as _intent_completion_signals_impl,
)
from .system_prompt_helpers import (
    intent_plan_gating_flags as _intent_plan_gating_flags_impl,
)
from .system_prompt_helpers import (
    is_capability_reporting_query as _is_capability_reporting_query_impl,
)
from .system_prompt_helpers import (
    resolve_capability_injection_decision as _resolve_capability_injection_decision_impl,
)
from .system_prompt_helpers import (
    should_skip_capability_summary as _should_skip_capability_summary_impl,
)
from .tool_policy_helpers import (
    allowed_tool_names_for_families as _allowed_tool_names_for_families_impl,
)
from .tool_policy_helpers import (
    allowed_tool_names_for_family as _allowed_tool_names_for_family_impl,
)
from .tool_policy_helpers import (
    ensure_explicit_family_coverage as _ensure_explicit_family_coverage_impl,
)
from .tool_policy_helpers import (
    ensure_web_research_tool_pair as _ensure_web_research_tool_pair_impl,
)
from .tool_policy_helpers import (
    ordered_requested_families_from_intents as _ordered_requested_families_from_intents_impl,
)
from .tool_policy_helpers import (
    restore_explicit_family_tools as _restore_explicit_family_tools_impl,
)
from .tool_policy_helpers import (
    restrict_tools_to_names as _restrict_tools_to_names_impl,
)
from .tool_router import ToolRouter
from .turn_research_helpers import (
    extract_last_user_text as _extract_last_user_text_impl,
)
from .types import (
    ExecutionBudget,
    ExecutionRequest,
    IntentPlan,
    ResearchContinuationContext,
    ToolUsePolicy,
)

logger = LogManager.get_logger("ai.engine")


def _rebuild_runtime_capability_diagnostics(
    *,
    agent: Any,
    request: ExecutionRequest,
    context_assembly: Any,
) -> None:
    bundle = getattr(context_assembly, "capability_bundle", None)
    if bundle is None:
        return

    diagnostics = getattr(context_assembly, "diagnostics", None)
    if not isinstance(diagnostics, dict):
        diagnostics = {}
        context_assembly.diagnostics = diagnostics
    diagnostics.update(ContextCapabilityBundleProjection.to_diagnostics(bundle))

    knowledge_feedback = (
        dict(getattr(request, "knowledge_base_feedback", {}) or {})
        if isinstance(getattr(request, "knowledge_base_feedback", None), dict)
        else {}
    )
    runtime_model_capabilities = diagnostics.get("runtime_model_capabilities")
    if not isinstance(runtime_model_capabilities, dict):
        runtime_model_capabilities = {}
        input_variables = getattr(request, "input_variables", None)
        if isinstance(input_variables, dict):
            raw_model_caps = input_variables.get("runtime_model_capabilities")
            if isinstance(raw_model_caps, dict):
                runtime_model_capabilities = dict(raw_model_caps)

    state = ContextAssemblerState(
        knowledge_base_ids=[
            int(kb_id)
            for kb_id in (
                diagnostics.get("effective_knowledge_base_ids")
                or knowledge_feedback.get("effective_knowledge_base_ids")
                or []
            )
            if str(kb_id).strip()
        ],
        requested_knowledge_base_ids=[
            int(kb_id)
            for kb_id in (diagnostics.get("requested_knowledge_base_ids") or [])
            if str(kb_id).strip()
        ],
        dropped_knowledge_base_ids=[
            int(kb_id)
            for kb_id in (
                diagnostics.get("dropped_knowledge_base_ids")
                or knowledge_feedback.get("dropped_knowledge_base_ids")
                or []
            )
            if str(kb_id).strip()
        ],
        rag_sources=list(getattr(context_assembly, "rag_sources", None) or []),
        rag_source_kinds=list(getattr(context_assembly, "rag_source_kinds", []) or []),
        memory_recalled=bool(getattr(context_assembly, "memory_recalled", False)),
        session_memory_injected=bool(
            getattr(request, "session_memory_injected", False)
        ),
        memory_recall_slice=dict(
            getattr(context_assembly, "memory_recall_slice", None) or {}
        ),
        runtime_model_capabilities=dict(runtime_model_capabilities or {}),
    )
    capability_injection_decision = dict(
        diagnostics.get("capability_injection_decision") or {}
    )
    manifest = AIRuntimeInventoryService.build_manifest(
        agent=agent,
        request=request,
        bundle=bundle,
        state=state,
        capability_injection_decision=capability_injection_decision,
    )
    diagnostics["runtime_capability_manifest"] = manifest.to_dict()
    diagnostics["runtime_capability_summary"] = (
        AIRuntimeInventoryService.build_compact_summary(
            manifest,
        )
    )


@dataclass
class PreparedExecutionToolPlan:
    tools: list[ToolDefinition]
    candidate_tool_names: list[str]
    tool_use_policy: ToolUsePolicy
    tool_planner: dict[str, Any] | None
    optimize_event: dict[str, Any] | None
    intent_plan: list[IntentPlan]
    intent_flags: dict[str, bool]
    explicit_requested_families: list[str]
    execution_path: str
    execution_budget: ExecutionBudget | None
    active_intent_id: str | None


def plan_execution_tools(
    *,
    agent_id: int | None,
    conversation_id: int | None,
    request: ExecutionRequest,
    messages: list[ChatMessage],
    tools: list[ToolDefinition],
    all_tools: list[ToolDefinition],
    diagnostics: dict[str, Any],
) -> PreparedExecutionToolPlan:
    raw_intent_plan = diagnostics.get("intent_plan")
    intent_plan = _deserialize_intent_plan_impl(raw_intent_plan)
    intent_flags = _intent_plan_gating_flags_impl(intent_plan, request=request)

    explicit_requested_families = _ordered_requested_families_from_intents_impl(
        intents=intent_plan
    )
    execution_path = PathSelector.select(intent_plan)
    execution_budget = BudgetGuard.build_default(
        execution_path,
        intent_count=len(intent_plan),
    )

    tool_planner: dict[str, Any] | None = None
    optimize_event: dict[str, Any] | None = None
    tool_use_policy = ToolUsePolicy()
    candidate_tool_names = [tool.name for tool in tools]
    active_intent_id: str | None = None

    if all_tools and intent_plan:
        user_query = _extract_last_user_text_impl(messages)
        routing = ToolRouter.route(
            intents=intent_plan,
            tools=all_tools,
            budget=execution_budget,
            input_variables=request.input_variables,
            user_text=user_query,
        )
        selected_tools = list(routing.candidate_tools)
        selected_tools, _ = _ensure_explicit_family_coverage_impl(
            selected_tools=selected_tools,
            all_tools=all_tools,
            explicit_requested_families=explicit_requested_families,
            input_variables=request.input_variables,
        )
        selected_tools, _ = _ensure_web_research_tool_pair_impl(
            selected_tools=selected_tools,
            all_tools=all_tools,
            explicit_requested_families=explicit_requested_families,
            policy=ToolUsePolicy(
                family=(
                    "web_research"
                    if "web_research" in explicit_requested_families
                    else "none"
                ),
                allowed_tool_names=_allowed_tool_names_for_family_impl(
                    "web_research",
                    all_tools,
                    request.input_variables,
                )
                if "web_research" in explicit_requested_families
                else [],
            ),
        )
        tool_candidates = selected_tools
        candidate_tool_names = [tool.name for tool in tool_candidates]
        actionable_intents = [
            intent
            for intent in intent_plan
            if intent.family != "none" and intent.requires_tools
        ]
        for intent in intent_plan:
            intent.metadata = dict(intent.metadata or {})
            allowed = list(routing.intent_allowed_tools.get(intent.intent_id, []))
            preferred = list(
                routing.intent_preferred_tools.get(intent.intent_id, allowed)
            )
            intent.allowed_tool_names = allowed
            intent.preferred_tool_names = preferred
            intent.completion_signals = _intent_completion_signals_impl(
                intent.family,
                intent_kind=intent.kind,
                allowed_tool_names=allowed,
                preferred_tool_names=preferred,
                intent_metadata=intent.metadata,
            )
            if intent.family == "none" or not intent.requires_tools:
                intent.status = "completed"
        if not tool_candidates and actionable_intents:
            fallback_allowed_names = _allowed_tool_names_for_families_impl(
                explicit_requested_families,
                all_tools,
                request.input_variables,
            ) or _allowed_tool_names_for_family_impl(
                actionable_intents[0].family,
                all_tools,
                request.input_variables,
            )
            if execution_budget is not None:
                fallback_allowed_names = fallback_allowed_names[
                    : execution_budget.max_candidate_tools
                ]
            tool_candidates = _restrict_tools_to_names_impl(
                all_tools,
                fallback_allowed_names,
            )
            candidate_tool_names = [tool.name for tool in tool_candidates]
            first_actionable = actionable_intents[0]
            first_actionable.allowed_tool_names = list(candidate_tool_names)
            first_actionable.preferred_tool_names = list(candidate_tool_names)
            first_actionable.completion_signals = _intent_completion_signals_impl(
                first_actionable.family,
                intent_kind=first_actionable.kind,
                allowed_tool_names=list(candidate_tool_names),
                preferred_tool_names=list(candidate_tool_names),
                intent_metadata=first_actionable.metadata,
            )
        active_intent = next(
            (
                intent
                for intent in intent_plan
                if intent.status != "completed" and intent.allowed_tool_names
            ),
            None,
        )
        if active_intent is not None:
            allowed_tool_names = (
                candidate_tool_names
                if len(actionable_intents) > 1
                else list(active_intent.allowed_tool_names)
            )
            tool_use_policy = ToolUsePolicy(
                family=active_intent.family,
                mode="required",
                allowed_tool_names=allowed_tool_names,
                retry_on_contract_breach=True,
                reason=f"intent:{active_intent.kind}",
            )
            restored_tools, restored_explicit_family = (
                _restore_explicit_family_tools_impl(
                    selected_tools=tool_candidates,
                    all_tools=all_tools,
                    policy=tool_use_policy,
                )
            )
            tool_candidates = restored_tools
            if restored_explicit_family:
                candidate_tool_names = [tool.name for tool in tool_candidates]
                tool_use_policy.allowed_tool_names = (
                    candidate_tool_names
                    if len(actionable_intents) > 1
                    else [
                        name
                        for name in tool_use_policy.allowed_tool_names
                        if name in candidate_tool_names
                    ]
                )
        tool_planner = {
            "intent": (
                active_intent.kind if active_intent is not None else "direct_reply"
            ),
            "family": active_intent.family if active_intent is not None else "none",
            "allow_no_tool": not bool(tool_candidates),
            "allow_family_continuation": bool(len(actionable_intents) > 1),
            "reason": "structured_intent_plan",
            "confidence_band": "high",
            "execution_path": execution_path,
            "intent_plan": [intent.to_dict() for intent in intent_plan],
        }
        optimize_event = {
            "total": len(all_tools),
            "selected": len(tool_candidates),
            "execution_path": execution_path,
        }
        logger.info(
            "Prepare execution intent plan: runtime={} agent_id={} conversation_id={} execution_path={} intent_plan={} candidate_tool_names={} active_intent_id={}",
            get_runtime_identity_tag(),
            agent_id,
            conversation_id,
            execution_path,
            [intent.to_dict() for intent in intent_plan],
            candidate_tool_names,
            active_intent_id,
        )
        logger.info(
            "Prepare execution tool policy: runtime={} agent_id={} conversation_id={} family={} mode={} allowed_tool_names={} all_tool_count={} selected_tool_count={}",
            get_runtime_identity_tag(),
            agent_id,
            conversation_id,
            tool_use_policy.family,
            tool_use_policy.mode,
            tool_use_policy.allowed_tool_names,
            len(all_tools),
            len(tool_candidates),
        )
        tools = tool_candidates
        if active_intent is not None:
            active_intent_id = active_intent.intent_id
        else:
            active_intent_id = None
    elif intent_plan:
        tool_planner = {
            "intent": intent_plan[0].kind if intent_plan else "direct_reply",
            "family": intent_plan[0].family if intent_plan else "none",
            "allow_no_tool": not bool(tools),
            "allow_family_continuation": bool(
                len(
                    [
                        intent
                        for intent in intent_plan
                        if intent.family != "none" and intent.requires_tools
                    ]
                )
                > 1
            ),
            "reason": "structured_intent_plan",
            "confidence_band": "high",
            "execution_path": execution_path,
            "intent_plan": [intent.to_dict() for intent in intent_plan],
        }

    return PreparedExecutionToolPlan(
        tools=tools,
        candidate_tool_names=candidate_tool_names,
        tool_use_policy=tool_use_policy,
        tool_planner=tool_planner,
        optimize_event=optimize_event,
        intent_plan=intent_plan,
        intent_flags=intent_flags,
        explicit_requested_families=explicit_requested_families,
        execution_path=execution_path,
        execution_budget=execution_budget,
        active_intent_id=active_intent_id,
    )


async def finalize_prepared_execution_runtime(
    *,
    db: Any,
    agent: Any,
    request: ExecutionRequest,
    tools: list[ToolDefinition],
    skill_result: Any,
    messages: list[ChatMessage],
    context_assembly: Any,
    intent_plan: list[IntentPlan],
    intent_flags: dict[str, bool],
    explicit_requested_families: list[str],
    execution_path: str,
    execution_budget: ExecutionBudget | None,
    continuation_context: ResearchContinuationContext | None,
    tool_planner: dict[str, Any] | None,
    candidate_tool_names: list[str],
    active_intent_id: str | None,
    sandbox: Any,
    apply_execution_trust_policy: Callable[..., dict[str, str]],
    render_contract: Callable[..., str],
) -> PreparedExecutionRuntimeState:
    """
    Finish runtime-tail work for `_prepare_execution`:
    capability injection + routing + diagnostics projection.
    """
    force_capability_summary = _is_capability_reporting_query_impl(
        _extract_last_user_text_impl(messages)
    )
    if tools:
        context_assembly.capability_bundle = project_capability_bundle_to_tools(
            getattr(context_assembly, "capability_bundle", None),
            tools,
        )
    context_assembly.diagnostics = dict(context_assembly.diagnostics or {})
    context_assembly.diagnostics["intent_flags"] = dict(intent_flags or {})
    _rebuild_runtime_capability_diagnostics(
        agent=agent,
        request=request,
        context_assembly=context_assembly,
    )
    context_sources = (
        context_assembly.capability_bundle.context_sources
        if context_assembly.capability_bundle is not None
        else None
    )
    runtime_capability_summary = (
        dict(context_assembly.diagnostics.get("runtime_capability_summary") or {})
        if isinstance(
            context_assembly.diagnostics.get("runtime_capability_summary"), dict
        )
        else None
    )
    _apply_runtime_capability_injection_impl(
        diagnostics=context_assembly.diagnostics,
        intent_flags=intent_flags,
        force_capability_summary=force_capability_summary,
        context_sources=context_sources,
        tools=tools,
        runtime_capability_summary=runtime_capability_summary,
        ordered_requested_families=explicit_requested_families,
        intent_plan=intent_plan,
        execution_path=execution_path,
        should_skip_capability_summary=_should_skip_capability_summary_impl,
        inject_runtime_summary=lambda **kwargs: _inject_runtime_summary_impl(
            messages=messages,
            render_contract=render_contract,
            **kwargs,
        ),
        resolve_capability_injection_decision=_resolve_capability_injection_decision_impl,
    )
    _rebuild_runtime_capability_diagnostics(
        agent=agent,
        request=request,
        context_assembly=context_assembly,
    )
    runtime_state = await _resolve_runtime_execution_state_impl(
        db=db,
        agent=agent,
        request=request,
        tools=tools,
        skill_result=skill_result,
        messages=messages,
        sandbox=sandbox,
        apply_execution_trust_policy=apply_execution_trust_policy,
    )
    _apply_prepared_execution_diagnostics_impl(
        diagnostics=context_assembly.diagnostics,
        tool_planner=tool_planner,
        candidate_tool_names=candidate_tool_names,
        active_intent_id=active_intent_id,
        continuation_context=continuation_context,
        intent_plan=intent_plan,
        execution_path=execution_path,
        execution_budget=execution_budget,
    )
    return runtime_state
