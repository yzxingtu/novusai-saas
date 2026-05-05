"""
Helpers for the runtime/trust/capability tail of BaseEngine._prepare_execution().
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.ai.tools.types import ToolDefinition
from app.ai.types import ChatMessage
from app.core.logging import LogManager
from app.exceptions import BusinessException

from .types import (
    ExecutionBudget,
    ExecutionPath,
    IntentPlan,
    PreparedExecution,
    ToolUsePolicy,
)

logger = LogManager.get_logger("ai.engine")


@dataclass
class PreparedExecutionRuntimeState:
    capability_injection_decision: dict[str, Any]
    tool_consent_modes: dict[str, str]
    route_result: Any | None = None
    runtime_model_capabilities: dict[str, bool] | None = None


def apply_prepared_execution_diagnostics(
    *,
    diagnostics: dict[str, Any],
    tool_planner: dict[str, Any] | None,
    candidate_tool_names: list[str],
    active_intent_id: str | None,
    intent_plan: list[IntentPlan],
    execution_path: ExecutionPath,
    execution_budget: ExecutionBudget | None,
) -> None:
    if tool_planner is not None:
        diagnostics["tool_planner"] = dict(tool_planner)
    diagnostics["candidate_tool_names"] = list(candidate_tool_names)
    diagnostics["active_intent_id"] = active_intent_id
    if intent_plan:
        diagnostics["intent_plan"] = [intent.to_dict() for intent in intent_plan]
        diagnostics["execution_path"] = execution_path
    if execution_budget is not None:
        diagnostics["execution_budget"] = execution_budget.snapshot()


def apply_runtime_capability_injection(
    *,
    diagnostics: dict[str, Any],
    intent_flags: dict[str, bool],
    force_capability_summary: bool,
    context_sources: list[dict[str, Any]] | None,
    tools: list[Any],
    runtime_capability_summary: dict[str, Any] | None,
    ordered_requested_families: list[str],
    intent_plan: list[Any],
    execution_path: str,
    should_skip_capability_summary: Callable[..., bool],
    inject_runtime_summary: Callable[..., bool],
    resolve_capability_injection_decision: Callable[..., dict[str, Any]],
) -> dict[str, Any]:
    skip_capability_summary = should_skip_capability_summary(
        diagnostics=diagnostics,
        intent_flags=intent_flags,
        force_capability_summary=force_capability_summary,
    )
    diagnostics["capability_reporting_query"] = force_capability_summary
    capability_summary_injected = inject_runtime_summary(
        tools=tools,
        runtime_capability_summary=runtime_capability_summary,
        ordered_requested_families=ordered_requested_families,
        skip_capability_summary=skip_capability_summary,
        intent_plan=intent_plan,
        execution_path=execution_path,
    )
    capability_injection_decision = resolve_capability_injection_decision(
        diagnostics=diagnostics,
        intent_flags=intent_flags,
        context_sources=context_sources,
        capability_summary_injected=capability_summary_injected,
    )
    diagnostics["capability_injection_decision"] = capability_injection_decision
    return capability_injection_decision


async def resolve_runtime_execution_state(
    *,
    db: Any,
    agent: Any,
    request: Any,
    tools: list[Any],
    skill_result: Any,
    messages: list[Any],
    sandbox: Any,
    apply_execution_trust_policy: Callable[..., dict[str, str]],
) -> PreparedExecutionRuntimeState:
    tool_consent_modes = skill_result.tool_consent_modes if skill_result else {}
    selected_tool_names = {tool.name for tool in tools}
    if selected_tool_names:
        tool_consent_modes = {
            name: mode
            for name, mode in (tool_consent_modes or {}).items()
            if name in selected_tool_names
        }
    tool_consent_modes = apply_execution_trust_policy(
        tools=tools,
        input_variables=request.input_variables,
        tool_consent_modes=tool_consent_modes,
        trust_policy_ref=request.trust_policy_ref,
        interaction_mode=request.interaction_mode,
    )

    route_result = None
    try:
        from app.ai.routing.router import ModelRouter
        from app.ai.runtime.usage_metrics import TokenCounter

        estimated_tokens = TokenCounter.count_messages_tokens(
            [{"content": m.content or "", "name": m.name or ""} for m in messages]
        )
        router = ModelRouter(db)
        route_result = await router.route(agent, request, estimated_tokens, tools=tools)
    except BusinessException:
        raise
    except Exception as routing_exc:
        logger.warning("ModelRouter integration failed: {}", str(routing_exc))

    runtime_model_capabilities: dict[str, bool] | None = None
    try:
        if route_result is not None and getattr(route_result, "is_overridden", False):
            model_id = int(getattr(route_result, "model_id", 0) or 0)
            route_model_obj = None
            if model_id:
                from app.repositories.ai.model_repository import AIModelRepository

                model_repo = AIModelRepository(db)
                route_model_obj = await model_repo.get_active_with_provider(model_id)
            if route_model_obj is not None:
                runtime_model_capabilities = {
                    "supports_audio": bool(
                        getattr(route_model_obj, "supports_audio", False)
                    ),
                    "supports_video": bool(
                        getattr(route_model_obj, "supports_video", False)
                    ),
                    "supports_vision": bool(
                        getattr(route_model_obj, "supports_vision", False)
                    ),
                }
        elif agent.model is not None:
            runtime_model_capabilities = {
                "supports_audio": bool(getattr(agent.model, "supports_audio", False)),
                "supports_video": bool(getattr(agent.model, "supports_video", False)),
                "supports_vision": bool(getattr(agent.model, "supports_vision", False)),
            }
    except Exception as capability_exc:
        logger.warning(
            "Resolve runtime model capabilities failed: {}", str(capability_exc)
        )

    if runtime_model_capabilities:
        request.input_variables = {
            **(request.input_variables or {}),
            "runtime_model_capabilities": runtime_model_capabilities,
        }
        if sandbox is not None:
            sandbox.input_variables = {
                **(sandbox.input_variables or {}),
                "runtime_model_capabilities": runtime_model_capabilities,
            }

    return PreparedExecutionRuntimeState(
        capability_injection_decision={},
        tool_consent_modes=tool_consent_modes,
        route_result=route_result,
        runtime_model_capabilities=runtime_model_capabilities,
    )


def build_prepared_execution(
    *,
    messages: list[ChatMessage],
    tools: list[ToolDefinition],
    all_tools: list[ToolDefinition],
    tool_use_policy: ToolUsePolicy,
    rag_sources: list[dict[str, Any]] | None,
    context_assembly: Any,
    context_engine: Any,
    tool_planner: dict[str, Any] | None,
    optimize_event: dict[str, Any] | None,
    runtime_state: PreparedExecutionRuntimeState,
    intent_plan: list[IntentPlan],
    execution_path: ExecutionPath,
    execution_budget: ExecutionBudget | None,
    active_intent_id: str | None,
) -> PreparedExecution:
    return PreparedExecution(
        messages=messages,
        tools=tools,
        all_tools=all_tools,
        continuation_context=None,
        tool_use_policy=tool_use_policy,
        rag_sources=rag_sources,
        rag_source_kinds=context_assembly.rag_source_kinds,
        context_engine=context_engine,
        compact_summary=context_assembly.compact_summary,
        prune_stats=context_assembly.prune_stats,
        memory_recall_slice=context_assembly.memory_recall_slice,
        context_compacted=context_assembly.context_compacted,
        memory_flush_triggered=context_assembly.memory_flush_triggered,
        memory_recalled=context_assembly.memory_recalled,
        system_prompt_additions=context_assembly.system_prompt_additions,
        diagnostics=context_assembly.diagnostics,
        tool_planner=dict(tool_planner) if tool_planner is not None else None,
        capability_bundle=context_assembly.capability_bundle,
        optimize_event=optimize_event,
        route_result=runtime_state.route_result,
        intent_plan=intent_plan,
        execution_path=execution_path,
        execution_budget=execution_budget,
        active_intent_id=active_intent_id,
        tool_consent_modes=runtime_state.tool_consent_modes,
    )
