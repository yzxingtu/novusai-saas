"""
Context capability bridge.

Owns runtime/service-backed capability assembly so the context engine can
consume a single published contract instead of reaching into runtime and
services internals directly.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.ai.capabilities import CapabilityDescriptionBuilder
from app.ai.runtime.capabilities import CapabilityContext, CapabilityRegistry
from app.ai.runtime.context_assembler import (
    ContextAssembler,
    ContextAssemblerState,
    LegacyContextAssemblerAdapter,
    get_context_assembler,
)
from app.ai.runtime.contracts import (
    ContextCapabilityAwareness,
    ContextCapabilityBridge,
    ContextCapabilityFinalization,
    ContextCapabilityInputs,
)
from app.ai.runtime.manifest import AIRuntimeInventoryService
from app.ai.runtime.types import CapabilityBundle
from app.core.logging import LogManager
from app.schemas.ai.agent_chat import PAGE_CONTEXT_KEY
from app.services.ai.capability_awareness_config import (
    get_tenant_capability_awareness_settings,
)
from app.services.ai.model_capability_lookup import resolve_runtime_model_capabilities

logger = LogManager.get_logger("ai.context_capability_bridge")


def _capability_description_category(description: Any) -> str:
    if isinstance(description, dict):
        raw_category = description.get("category")
    else:
        raw_category = getattr(description, "category", None)
    return str(raw_category or "").strip()


def _stable_unique_categories(descriptions: list[Any]) -> list[str]:
    seen: set[str] = set()
    categories: list[str] = []
    for description in descriptions:
        category = _capability_description_category(description)
        if not category or category in seen:
            continue
        seen.add(category)
        categories.append(category)
    return categories


def _to_context_assembler_state(
    capability_inputs: ContextCapabilityInputs,
) -> ContextAssemblerState:
    state_payload = capability_inputs.to_state_dict()
    return ContextAssemblerState(**state_payload)


@dataclass
class DefaultContextCapabilityBridge(ContextCapabilityBridge):
    context_assembler: ContextAssembler
    context_assembler_adapter: LegacyContextAssemblerAdapter

    async def resolve_runtime_model_capabilities(
        self,
        *,
        agent: Any,
    ) -> dict[str, Any]:
        try:
            return await resolve_runtime_model_capabilities(
                model=getattr(agent, "model", None),
            )
        except Exception as exc:
            logger.warning(
                "Resolve runtime model capabilities degraded during provisional planning: agent_id={} err={}",
                getattr(agent, "id", None),
                str(exc),
            )
            return {}

    def build_provisional_bundle(
        self,
        *,
        agent: Any,
        request: Any,
        skill_result: Any | None,
        capability_inputs: ContextCapabilityInputs,
    ) -> CapabilityBundle:
        try:
            assembler_state = _to_context_assembler_state(capability_inputs)
            capability_context = CapabilityContext(
                agent=agent,
                request=request,
                skill_result=skill_result,
                state=assembler_state.to_state_dict(),
            )
            bundle = CapabilityBundle()
            fragments = (
                ContextAssembler._collect_skill_capabilities(capability_context),
                ContextAssembler._collect_page_context_capabilities(
                    capability_context
                ),
                ContextAssembler._collect_knowledge_capabilities(capability_context),
                ContextAssembler._collect_runtime_model_capabilities(
                    capability_context
                ),
            )
            for fragment in fragments:
                if fragment is None:
                    continue
                CapabilityRegistry._merge_fragment(bundle, fragment)
            return bundle
        except Exception as exc:
            logger.warning(
                "Provisional capability bundle degraded: agent_id={} err={}",
                getattr(agent, "id", None),
                str(exc),
            )
            return CapabilityBundle()

    async def compute_awareness(
        self,
        *,
        db: Any,
        agent: Any,
        request: Any,
        skill_result: Any | None,
        intent_flags: dict[str, bool],
        knowledge_base_ids: list[int],
        long_term_memory_enabled: bool,
    ) -> ContextCapabilityAwareness:
        try:
            settings = await get_tenant_capability_awareness_settings(
                db,
                request.tenant_id,
            )
            awareness = ContextCapabilityAwareness(
                enabled=bool(settings.enable_dynamic_capability_awareness),
            )
            if not awareness.enabled or intent_flags.get("all_shortcircuit", False):
                return awareness

            capability_builder = CapabilityDescriptionBuilder(
                style=settings.capability_description_style,
                max_items_per_category=settings.max_capability_items_per_category,
            )
            capability_descriptions = []

            if skill_result:
                capability_descriptions.extend(
                    capability_builder.build_skill_descriptions(skill_result)
                )

            if intent_flags.get("has_knowledge_intent") and knowledge_base_ids:
                from app.services.ai.agent_kb_binding_service import (
                    AgentKBBindingService,
                )

                kb_service = AgentKBBindingService(db, request.tenant_id)
                kb_bindings = await kb_service.get_agent_kb_bindings_with_metadata(
                    agent.id,
                    merge_platform_bindings=True,
                )
                effective_kb_ids = set(knowledge_base_ids)
                kb_bindings = [
                    binding
                    for binding in kb_bindings
                    if int(binding.get("knowledge_base_id") or binding.get("kb_id") or 0)
                    in effective_kb_ids
                ]
                kb_description = capability_builder.build_knowledge_base_descriptions(
                    kb_bindings
                )
                if kb_description:
                    capability_descriptions.append(kb_description)

            if intent_flags.get("has_page_intent"):
                page_context = None
                if isinstance(request.input_variables, dict):
                    page_context = request.input_variables.get(PAGE_CONTEXT_KEY)
                page_description = capability_builder.build_page_context_description(
                    page_context
                )
                if page_description:
                    capability_descriptions.append(page_description)

            if intent_flags.get("has_memory_intent"):
                memory_description = capability_builder.build_memory_description(
                    memory_enabled=request.memory_enabled,
                    long_term_memory_enabled=long_term_memory_enabled,
                )
                if memory_description:
                    capability_descriptions.append(memory_description)

            awareness.categories = _stable_unique_categories(
                capability_descriptions
            )
            return awareness
        except Exception as exc:
            logger.warning(
                "Dynamic capability awareness degraded: agent_id={} tenant_id={} err={}",
                getattr(agent, "id", None),
                request.tenant_id,
                str(exc),
            )
            return ContextCapabilityAwareness(
                enabled=False,
                error=str(exc),
            )

    async def finalize_capabilities(
        self,
        *,
        agent: Any,
        request: Any,
        skill_result: Any | None,
        intent_plan: list[Any],
        intent_flags: dict[str, bool],
        capability_inputs: ContextCapabilityInputs,
        capability_injection_decision: dict[str, Any],
    ) -> ContextCapabilityFinalization:
        diagnostics: dict[str, Any] = {}
        decision = dict(capability_injection_decision or {})
        capability_bundle: CapabilityBundle | None = None
        assembler_state = _to_context_assembler_state(capability_inputs)

        try:
            capability_bundle = await self.context_assembler.assemble_bundle(
                agent=agent,
                request=request,
                skill_result=skill_result,
                state=assembler_state,
                intent_plan=intent_plan,
            )
            self.context_assembler_adapter.apply_to_skill_result(
                skill_result=skill_result,
                bundle=capability_bundle,
            )
            diagnostics.update(
                self.context_assembler_adapter.to_diagnostics(capability_bundle),
            )
            if not diagnostics.get("selected_skill_names"):
                fallback_skill_names = list(
                    getattr(skill_result, "selected_skill_names", []) or []
                )
                if fallback_skill_names:
                    diagnostics["selected_skill_names"] = list(
                        dict.fromkeys(
                            str(name).strip()
                            for name in fallback_skill_names
                            if str(name).strip()
                        )
                    )
            if capability_inputs.runtime_model_capabilities:
                diagnostics["runtime_model_capabilities"] = dict(
                    capability_inputs.runtime_model_capabilities
                )

            context_source_kinds = {
                str(source.kind or "").strip()
                for source in capability_bundle.context_sources
                if bool(getattr(source, "active", True))
            }
            decision["kb_injected"] = bool(
                decision.get("kb_injected") or "knowledge_base" in context_source_kinds
            )
            decision["memory_injected"] = bool(
                decision.get("memory_injected")
                or "session_memory" in context_source_kinds
                or "long_term_memory" in context_source_kinds
            )
            decision["page_injected"] = bool(
                decision.get("page_injected") or "page_context" in context_source_kinds
            )
        except Exception as exc:
            diagnostics["capability_bundle_error"] = str(exc)
            logger.warning(
                "Context capability assembly degraded: agent_id={} err={}",
                getattr(agent, "id", None),
                str(exc),
            )

        manifest_bundle = capability_bundle or CapabilityBundle()
        runtime_manifest = AIRuntimeInventoryService.build_manifest(
            agent=agent,
            request=request,
            bundle=manifest_bundle,
            state=assembler_state,
            capability_injection_decision=decision,
        )
        return ContextCapabilityFinalization(
            capability_bundle=capability_bundle,
            diagnostics=diagnostics,
            capability_injection_decision=decision,
            runtime_manifest=runtime_manifest.to_dict(),
            runtime_capability_summary=AIRuntimeInventoryService.build_compact_summary(
                runtime_manifest,
                include_knowledge_base_hint=intent_flags.get(
                    "has_knowledge_intent",
                    False,
                ),
                include_page_context_hint=intent_flags.get("has_page_intent", False),
                include_memory_hint=intent_flags.get("has_memory_intent", False),
            ),
        )


_DEFAULT_CONTEXT_CAPABILITY_BRIDGE: DefaultContextCapabilityBridge | None = None


def get_context_capability_bridge() -> DefaultContextCapabilityBridge:
    global _DEFAULT_CONTEXT_CAPABILITY_BRIDGE
    if _DEFAULT_CONTEXT_CAPABILITY_BRIDGE is None:
        _DEFAULT_CONTEXT_CAPABILITY_BRIDGE = DefaultContextCapabilityBridge(
            context_assembler=get_context_assembler(),
            context_assembler_adapter=LegacyContextAssemblerAdapter(),
        )
    return _DEFAULT_CONTEXT_CAPABILITY_BRIDGE


__all__ = [
    "DefaultContextCapabilityBridge",
    "get_context_capability_bridge",
]
