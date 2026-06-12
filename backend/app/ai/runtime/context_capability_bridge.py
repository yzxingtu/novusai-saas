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
from app.ai.engine.system_prompt_intent_helpers import is_capability_reporting_query
from app.ai.memory_policy import resolve_memory_runtime_policy
from app.ai.runtime.capabilities import CapabilityContext, CapabilityRegistry
from app.ai.runtime.context_assembler import (
    ContextAssembler,
    ContextAssemblerState,
    ContextCapabilityBundleProjection,
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


def _last_user_text(request: Any) -> str:
    messages = list(getattr(request, "messages", None) or [])
    for message in reversed(messages):
        if str(getattr(message, "role", "") or "").strip() != "user":
            continue
        text = str(getattr(message, "content", "") or "").strip()
        if text:
            return text
    return ""


def _binding_kb_id(binding: dict[str, Any]) -> int:
    try:
        return int(binding.get("knowledge_base_id") or binding.get("kb_id") or 0)
    except (TypeError, ValueError):
        return 0


def _coerce_non_negative_int(value: Any) -> int:
    try:
        return max(int(value), 0)
    except (TypeError, ValueError):
        return 0


def _knowledge_context_from_bindings(
    *,
    kb_bindings: list[dict[str, Any]],
    knowledge_base_ids: list[int],
    rag_attempted: bool,
    rag_retrieval_status: str | None,
    rag_no_hit_reason: str | None,
    rag_matched_chunk_count: int,
) -> dict[str, Any] | None:
    effective_ids = {int(kb_id) for kb_id in knowledge_base_ids if int(kb_id) > 0}
    knowledge_bases: list[dict[str, Any]] = []
    seen_ids: set[int] = set()
    for binding in kb_bindings:
        kb_id = _binding_kb_id(binding)
        if kb_id <= 0 or kb_id not in effective_ids or kb_id in seen_ids:
            continue
        name = str(binding.get("kb_name") or "").strip()
        if not name:
            continue
        seen_ids.add(kb_id)
        knowledge_bases.append(
            {
                "id": kb_id,
                "name": name,
                "description": str(binding.get("kb_description") or "").strip(),
                "document_count": _coerce_non_negative_int(
                    binding.get("kb_document_count")
                ),
            }
        )
    if not knowledge_bases and not knowledge_base_ids:
        return None
    return {
        "knowledge_bases": knowledge_bases,
        "knowledge_base_ids": list(knowledge_base_ids or []),
        "knowledge_base_names": [item["name"] for item in knowledge_bases],
        "retrieval": {
            "attempted": bool(rag_attempted),
            "status": str(rag_retrieval_status or "").strip() or None,
            "source_count": max(int(rag_matched_chunk_count or 0), 0),
            "matched_chunk_count": max(int(rag_matched_chunk_count or 0), 0),
            "no_hit_reason": str(rag_no_hit_reason or "").strip() or None,
        },
    }


@dataclass
class DefaultContextCapabilityBridge(ContextCapabilityBridge):
    context_assembler: ContextAssembler
    bundle_projection: ContextCapabilityBundleProjection

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
                ContextAssembler._collect_knowledge_capabilities(capability_context),
                ContextAssembler._collect_runtime_model_capabilities(
                    capability_context
                ),
            )
            for fragment in fragments:
                if fragment is None:
                    continue
                CapabilityRegistry._merge_fragment(bundle, fragment)
            ContextAssembler._apply_skill_result_selection_contract(
                bundle=bundle,
                skill_result=skill_result,
            )
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
        rag_attempted: bool,
        rag_retrieval_status: str | None,
        rag_no_hit_reason: str | None,
        rag_matched_chunk_count: int,
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
            capability_reporting_query = is_capability_reporting_query(
                _last_user_text(request),
            )
            has_bound_kb = bool(
                intent_flags.get("has_bound_kb") or knowledge_base_ids
            )
            include_kb_context = bool(
                (has_bound_kb or capability_reporting_query) and knowledge_base_ids
            )
            kb_bindings: list[dict[str, Any]] = []
            if include_kb_context:
                from app.services.ai.agent_kb_binding_service import (
                    AgentKBBindingService,
                )

                kb_service = AgentKBBindingService(db, request.tenant_id)
                raw_bindings = await kb_service.get_agent_kb_bindings_with_metadata(
                    agent.id,
                    merge_platform_bindings=True,
                )
                effective_kb_ids = {int(kb_id) for kb_id in knowledge_base_ids}
                kb_bindings = [
                    binding
                    for binding in raw_bindings
                    if _binding_kb_id(binding) in effective_kb_ids
                ]
                awareness.knowledge_context = _knowledge_context_from_bindings(
                    kb_bindings=kb_bindings,
                    knowledge_base_ids=knowledge_base_ids,
                    rag_attempted=rag_attempted,
                    rag_retrieval_status=rag_retrieval_status,
                    rag_no_hit_reason=rag_no_hit_reason,
                    rag_matched_chunk_count=rag_matched_chunk_count,
                )
            if not awareness.enabled or (
                intent_flags.get("should_skip_bound_kb_rag", False)
                and not capability_reporting_query
            ):
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

            include_kb_awareness = bool(
                (has_bound_kb or capability_reporting_query) and knowledge_base_ids
            )
            if include_kb_awareness:
                kb_description = capability_builder.build_knowledge_base_descriptions(
                    kb_bindings
                )
                if kb_description:
                    capability_descriptions.append(kb_description)

            memory_policy = resolve_memory_runtime_policy(request)
            include_memory_awareness = bool(
                intent_flags.get("memory_context_enabled")
                or (
                    capability_reporting_query
                    and (
                        memory_policy.session_memory_runtime_enabled
                        or memory_policy.long_term_memory_runtime_enabled
                    )
                )
            )
            if include_memory_awareness:
                memory_description = capability_builder.build_memory_description(
                    memory_enabled=request.memory_enabled,
                    long_term_memory_enabled=long_term_memory_enabled,
                    memory_policy=memory_policy.to_dict(),
                )
                if memory_description:
                    capability_descriptions.append(memory_description)

            awareness.categories = _stable_unique_categories(capability_descriptions)
            awareness.sections = capability_builder.build_prompt_sections(
                capability_descriptions,
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
        del intent_flags
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
            self.bundle_projection.apply_to_skill_result(
                skill_result=skill_result,
                bundle=capability_bundle,
            )
            diagnostics.update(
                self.bundle_projection.to_diagnostics(capability_bundle),
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
            kb_context_injected = any(
                str(source.kind or "").strip() == "knowledge_base"
                and (
                    _coerce_non_negative_int(
                        (source.metadata or {}).get("rag_source_count")
                    )
                    > 0
                    or str(
                        (source.metadata or {}).get("rag_retrieval_status") or ""
                    ).strip()
                    == "injected"
                )
                for source in capability_bundle.context_sources
            )
            decision["kb_injected"] = bool(
                decision.get("kb_injected") or kb_context_injected
            )
            decision["memory_injected"] = bool(
                decision.get("memory_injected")
                or "session_memory" in context_source_kinds
                or "long_term_memory" in context_source_kinds
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
                runtime_manifest
            ),
        )


_DEFAULT_CONTEXT_CAPABILITY_BRIDGE: DefaultContextCapabilityBridge | None = None


def get_context_capability_bridge() -> DefaultContextCapabilityBridge:
    global _DEFAULT_CONTEXT_CAPABILITY_BRIDGE
    if _DEFAULT_CONTEXT_CAPABILITY_BRIDGE is None:
        _DEFAULT_CONTEXT_CAPABILITY_BRIDGE = DefaultContextCapabilityBridge(
            context_assembler=get_context_assembler(),
            bundle_projection=ContextCapabilityBundleProjection(),
        )
    return _DEFAULT_CONTEXT_CAPABILITY_BRIDGE


__all__ = [
    "DefaultContextCapabilityBridge",
    "get_context_capability_bridge",
]
