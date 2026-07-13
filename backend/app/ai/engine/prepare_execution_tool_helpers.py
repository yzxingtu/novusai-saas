"""
Helpers for tool planning inside BaseEngine._prepare_execution().

After ReAct loop adoption (#55), the LLM autonomously selects tools via
function calling. This module retains only deterministic shortcircuits
(confirmation replay / rejection) and capability diagnostics.
"""

from __future__ import annotations

import json
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

from .budget_guard import BudgetGuard
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
    inject_runtime_summary as _inject_runtime_summary_impl,
)
from .system_prompt_helpers import (
    resolve_capability_injection_decision as _resolve_capability_injection_decision_impl,
)
from .types import (
    ExecutionBudget,
    ExecutionRequest,
    IntentPlan,
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
    # ── Confirmation Replay Shortcircuit ─────────────────────────────────────
    # Only shortcircuit when THIS turn's interaction_updates contain an approved
    # pending_confirmation (not rejected). We must NOT match historical resolved
    # confirmations from earlier turns – resolved=True is persisted in message
    # metadata forever, so we gate on the live interaction_updates signal.
    _has_current_confirmation_approval = any(
        str(u.get("kind") or "") == "pending_confirmation"
        and not bool(u.get("rejected"))
        for u in (getattr(request, "interaction_updates", None) or [])
        if isinstance(u, dict)
    )
    if _has_current_confirmation_approval:
        from .tool_processor_messages import find_resolved_pending_confirmation

        resolved_replay = find_resolved_pending_confirmation(messages)
    else:
        resolved_replay = None
    if resolved_replay:
        replay_tool_name = str(resolved_replay.get("name") or "").strip()
        replay_tool = next(
            (t for t in all_tools if t.name == replay_tool_name),
            None,
        )
        if replay_tool is not None:
            replay_intent = IntentPlan(
                intent_id="intent-confirm-replay",
                kind="confirmation_replay",
                family="internal_ops",
                order=1,
                user_visible_label="confirmation_replay",
                source_text="",
                requires_tools=True,
                shortcircuit=True,
                allowed_tool_names=[replay_tool_name],
                preferred_tool_names=[replay_tool_name],
                metadata={
                    "routing_mode": "deterministic_shortcircuit",
                    "confirmation_replay": {
                        "name": resolved_replay["name"],
                        "arguments": json.dumps(
                            resolved_replay["arguments"], ensure_ascii=False
                        ),
                        "tool_call_id": resolved_replay["tool_call_id"],
                    },
                },
            )
            shortcircuit_policy = ToolUsePolicy(
                family="internal_ops",
                mode="required",
                allowed_tool_names=[replay_tool_name],
                retry_on_contract_breach=False,
                reason="confirmation_replay",
            )
            return PreparedExecutionToolPlan(
                tools=[replay_tool],
                candidate_tool_names=[replay_tool_name],
                tool_use_policy=shortcircuit_policy,
                tool_planner={
                    "intent": "confirmation_replay",
                    "family": "internal_ops",
                    "reason": "deterministic_shortcircuit",
                },
                optimize_event={
                    "total": len(all_tools),
                    "selected": 1,
                    "execution_path": "fast",
                },
                intent_plan=[replay_intent],
                intent_flags={"all_shortcircuit": True},
                explicit_requested_families=["internal_ops"],
                execution_path="fast",
                execution_budget=BudgetGuard.build_default("fast", intent_count=1),
                active_intent_id="intent-confirm-replay",
            )
    # ── End Confirmation Replay Shortcircuit ──────────────────────────────────

    # ── Confirmation Rejection Shortcircuit ───────────────────────────────────
    _has_current_confirmation_rejection = any(
        str(u.get("kind") or "") == "pending_confirmation" and bool(u.get("rejected"))
        for u in (getattr(request, "interaction_updates", None) or [])
        if isinstance(u, dict)
    )
    if _has_current_confirmation_rejection:
        rejection_intent = IntentPlan(
            intent_id="intent-confirm-reject",
            kind="direct_reply",
            family="none",
            order=1,
            user_visible_label="cancellation_acknowledgement",
            source_text="",
            requires_tools=False,
            shortcircuit=True,
            allowed_tool_names=[],
            preferred_tool_names=[],
            metadata={"routing_mode": "rejection_shortcircuit"},
        )
        rejection_policy = ToolUsePolicy(
            family="none",
            mode="auto",
            allowed_tool_names=[],
            retry_on_contract_breach=False,
            reason="confirmation_rejection",
        )
        return PreparedExecutionToolPlan(
            tools=[],
            candidate_tool_names=[],
            tool_use_policy=rejection_policy,
            tool_planner={
                "intent": "direct_reply",
                "family": "none",
                "reason": "rejection_shortcircuit",
            },
            optimize_event={
                "total": len(all_tools),
                "selected": 0,
                "execution_path": "fast",
            },
            intent_plan=[rejection_intent],
            intent_flags={"all_shortcircuit": True},
            explicit_requested_families=[],
            execution_path="fast",
            execution_budget=BudgetGuard.build_default("fast", intent_count=1),
            active_intent_id="intent-confirm-reject",
        )
    # ── End Confirmation Rejection Shortcircuit ───────────────────────────────

    # ── Default: pass all tools to ReAct loop ────────────────────────────────
    # The LLM autonomously selects tools via function calling.
    # No intent planning or tool routing is performed.
    candidate_tool_names = [tool.name for tool in tools]
    all_tool_names = [t.name for t in all_tools]
    default_policy = ToolUsePolicy(
        family="auto",
        mode="auto",
        allowed_tool_names=all_tool_names,
        retry_on_contract_breach=False,
        reason="react_autonomous_tool_selection",
    )
    # ReAct autonomous path: no candidate tool limit, LLM chooses freely
    execution_path = "react"
    execution_budget = BudgetGuard.build_for_react()
    return PreparedExecutionToolPlan(
        tools=tools,
        candidate_tool_names=candidate_tool_names,
        tool_use_policy=default_policy,
        tool_planner=None,
        optimize_event={
            "total": len(all_tools),
            "selected": len(tools),
            "execution_path": execution_path,
        },
        intent_plan=[],
        intent_flags={},
        explicit_requested_families=[],
        execution_path=execution_path,
        execution_budget=execution_budget,
        active_intent_id=None,
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
        context_sources=context_sources,
        tools=tools,
        runtime_capability_summary=runtime_capability_summary,
        ordered_requested_families=explicit_requested_families,
        intent_plan=intent_plan,
        execution_path=execution_path,
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
        intent_plan=intent_plan,
        execution_path=execution_path,
        execution_budget=execution_budget,
    )
    return runtime_state
