"""
Initial assembly support for context engine.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

from app.ai.runtime.contracts import (
    ContextCapabilityBridge,
    ContextCapabilityInputs,
)
from app.ai.runtime.types import CapabilityBundle
from app.ai.skills.activation import apply_turn_skill_activation
from app.ai.types import ChatMessage


class PromptBridge(Protocol):
    def _build_system_message(
        self,
        agent: Any,
        input_variables: dict[str, Any] | None,
    ) -> ChatMessage: ...


KbBindingLoader = Callable[
    [Any, int, int | None],
    Awaitable[tuple[list[int] | None, dict[int, float]]],
]
IntentPlanCallable = Callable[..., list[Any]]
IntentFlagResolver = Callable[[list[Any], Any | None], dict[str, bool]]


@dataclass(frozen=True)
class KnowledgeBaseSelection:
    requested_kb_ids: list[int] = field(default_factory=list)
    merged_kb_ids: list[int] = field(default_factory=list)
    dropped_kb_ids: list[int] = field(default_factory=list)
    agent_kb_weights: dict[int, float] = field(default_factory=dict)


@dataclass
class InitialContextAssemblyResult:
    messages: list[ChatMessage] = field(default_factory=list)
    kb_selection: KnowledgeBaseSelection = field(default_factory=KnowledgeBaseSelection)
    runtime_model_capabilities: dict[str, Any] = field(default_factory=dict)
    provisional_capability_inputs: ContextCapabilityInputs = field(
        default_factory=ContextCapabilityInputs
    )
    provisional_bundle: CapabilityBundle = field(default_factory=CapabilityBundle)
    provisional_continuation_context: Any = None
    intent_plan: list[Any] = field(default_factory=list)
    intent_flags: dict[str, bool] = field(default_factory=dict)
    capability_injection_decision: dict[str, Any] = field(default_factory=dict)


def build_system_and_request_messages(
    *,
    prompt_bridge: PromptBridge,
    agent: Any,
    request: Any,
) -> list[ChatMessage]:
    messages: list[ChatMessage] = [
        prompt_bridge._build_system_message(
            agent,
            getattr(request, "input_variables", None),
        )
    ]
    raw_messages = list(getattr(request, "messages", None) or [])
    if raw_messages:
        messages.extend(raw_messages)
    return messages


def resolve_knowledge_base_selection(
    *,
    request_kb_ids: list[int] | None,
    agent_kb_ids: list[int] | None,
    agent_kb_weights: dict[int, float] | None,
) -> KnowledgeBaseSelection:
    requested_kb_ids = [
        int(kb_id) for kb_id in (request_kb_ids or []) if str(kb_id).strip()
    ]
    resolved_agent_kb_ids = list(agent_kb_ids or [])
    if requested_kb_ids:
        selected = set(requested_kb_ids)
        merged_kb_ids = [kid for kid in resolved_agent_kb_ids if kid in selected]
        if not merged_kb_ids:
            merged_kb_ids = list(resolved_agent_kb_ids)
    else:
        merged_kb_ids = list(resolved_agent_kb_ids)
    dropped_kb_ids = [
        kb_id for kb_id in requested_kb_ids if kb_id not in set(merged_kb_ids)
    ]
    return KnowledgeBaseSelection(
        requested_kb_ids=requested_kb_ids,
        merged_kb_ids=merged_kb_ids,
        dropped_kb_ids=dropped_kb_ids,
        agent_kb_weights=dict(agent_kb_weights or {}),
    )


def build_capability_injection_decision(
    intent_flags: dict[str, bool],
) -> dict[str, Any]:
    return {
        "all_shortcircuit": bool(intent_flags.get("all_shortcircuit", False)),
        "skills_injected": False,
        "kb_injected": False,
        "memory_injected": False,
        "bypass_reason": (
            "all_shortcircuit"
            if bool(intent_flags.get("all_shortcircuit", False))
            else None
        ),
    }


async def assemble_initial_context_state(
    *,
    db: Any,
    agent: Any,
    request: Any,
    skill_result: Any | None,
    prompt_bridge: PromptBridge,
    capability_bridge: ContextCapabilityBridge,
    load_agent_kb_bindings_fn: KbBindingLoader,
    intent_plan_callable: IntentPlanCallable,
    intent_flag_resolver: IntentFlagResolver,
) -> InitialContextAssemblyResult:
    messages = build_system_and_request_messages(
        prompt_bridge=prompt_bridge,
        agent=agent,
        request=request,
    )
    agent_kb_ids, agent_kb_weights = await load_agent_kb_bindings_fn(
        db,
        agent.id,
        request.tenant_id,
    )
    kb_selection = resolve_knowledge_base_selection(
        request_kb_ids=getattr(request, "knowledge_base_ids", None),
        agent_kb_ids=agent_kb_ids,
        agent_kb_weights=agent_kb_weights,
    )
    runtime_model_capabilities = (
        await capability_bridge.resolve_runtime_model_capabilities(agent=agent)
    )
    provisional_capability_inputs = ContextCapabilityInputs(
        knowledge_base_ids=list(kb_selection.merged_kb_ids or []),
        requested_knowledge_base_ids=list(kb_selection.requested_kb_ids or []),
        dropped_knowledge_base_ids=list(kb_selection.dropped_kb_ids or []),
        runtime_model_capabilities=dict(runtime_model_capabilities or {}),
    )
    provisional_bundle = capability_bridge.build_provisional_bundle(
        agent=agent,
        request=request,
        skill_result=skill_result,
        capability_inputs=provisional_capability_inputs,
    )
    provisional_continuation_context = None
    intent_plan = intent_plan_callable(
        messages=messages,
        tools=list(provisional_bundle.tools),
        input_variables=getattr(request, "input_variables", None),
        continuation_context=provisional_continuation_context,
        capability_bundle=provisional_bundle,
    )
    intent_flags = intent_flag_resolver(intent_plan, request)
    if skill_result is not None:
        apply_turn_skill_activation(
            skill_result=skill_result,
            request=request,
            intent_flags=intent_flags,
        )
        provisional_bundle = capability_bridge.build_provisional_bundle(
            agent=agent,
            request=request,
            skill_result=skill_result,
            capability_inputs=provisional_capability_inputs,
        )
        provisional_continuation_context = None
        intent_plan = intent_plan_callable(
            messages=messages,
            tools=list(provisional_bundle.tools),
            input_variables=getattr(request, "input_variables", None),
            continuation_context=provisional_continuation_context,
            capability_bundle=provisional_bundle,
        )
        intent_flags = intent_flag_resolver(intent_plan, request)
    return InitialContextAssemblyResult(
        messages=messages,
        kb_selection=kb_selection,
        runtime_model_capabilities=dict(runtime_model_capabilities or {}),
        provisional_capability_inputs=provisional_capability_inputs,
        provisional_bundle=provisional_bundle,
        provisional_continuation_context=provisional_continuation_context,
        intent_plan=list(intent_plan or []),
        intent_flags=dict(intent_flags or {}),
        capability_injection_decision=build_capability_injection_decision(intent_flags),
    )


__all__ = [
    "InitialContextAssemblyResult",
    "KbBindingLoader",
    "KnowledgeBaseSelection",
    "PromptBridge",
    "assemble_initial_context_state",
    "build_capability_injection_decision",
    "build_system_and_request_messages",
    "resolve_knowledge_base_selection",
]
