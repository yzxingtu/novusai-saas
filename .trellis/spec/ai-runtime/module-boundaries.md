# Module Boundaries

## Goal

Keep the AI runtime modular enough that protocol work, intent/tool orchestration,
context assembly, and service-facing workflows can evolve independently.

## Governance Limits

- Backend AI production modules should target `<= 600` lines.
- Provider protocol implementation modules should target `<= 400` lines.
- Frontend AI `.vue` shells and sections should target `<= 450` lines.
- Frontend AI `.ts` composables and runtime helpers should target `<= 500` lines.
- Any AI production file `> 1000` lines is treated as blocking governance debt;
  new feature work should split the file first instead of growing it further.

## Runtime Layers (Stable Ownership)

1. Contracts and diagnostics: stable DTOs for intents, budgets, protocol plans,
turn records, and capability bundles used across layers.
2. Intent and tool orchestration: intent planning, tool rounds, recovery
decisions, execution budgets, and unified stream or sync state.
3. Context pipeline: system prompt assembly, RAG injection, compaction, and
memory recall orchestration without direct service or adapter imports.
4. Runtime capability bridge and manifest: runtime-owned seam that assembles
ContextAssembler output, performs service-backed capability lookups, and emits
the runtime capability manifest + summary.
5. Runtime kernel: protocol planning, protocol chain execution, and fallback or
rescue policy for a single provider turn.
6. Adapter and provider layer: protocol-specific request construction and
response mapping for one protocol step.
7. Tool runtime and skills: tool catalog, consent gating, tool execution,
page operations, and web research orchestration.
8. Service layer: business use cases, persistence, memory capture, and read
model projection.
9. Observability and monitoring: diagnostics projection and operator read models.
10. Frontend AI shell: UI composition and state distribution.

## Stable Boundary Contracts

- Protocol planning lives in the runtime kernel. Adapters execute one protocol
path at a time and must not invent fallback chains.
- Context assembly depends on the ContextCapabilityBridge contract. The context
engine must not import runtime or service internals directly.
- ContextCapabilityBridge (runtime-v2) is the only sanctioned runtime/service
seam for capability awareness and runtime manifest emission.
- Model-capability lookup is confined to runtime capability assembly modules
(ContextAssembler + ContextCapabilityBridge), using
`app.services.ai.model_capability_lookup.resolve_runtime_model_capabilities`.
- Tenant capability awareness settings are accessed only inside
ContextCapabilityBridge via
`app.services.ai.capability_awareness_config.get_tenant_capability_awareness_settings`.
- The bridge emits the runtime manifest via `AIRuntimeInventoryService` and
returns `ContextCapabilityFinalization.runtime_manifest` plus
`runtime_capability_summary` for downstream consumers.
- Long-term memory recall uses the LongTermMemoryProvider protocol from the
context layer. The service layer owns the provider factory and may lazy-import
its implementation.
- Public package imports are protected by lazy export facades in `app.ai`,
`app.ai.engine`, `app.ai.context`, `app.ai.runtime`, and tool packages. Heavy
imports must stay out of `__init__` modules.
- Frontend AI runtime and helper public files may remain stable thin facades;
  newly extracted behavior should continue into companion `*-core`,
  `*-support`, `*-contracts`, or sibling domain modules instead of re-growing
  the facade entrypoint.
- Turn diagnostics flow through TurnRecord and CapabilityBundle. No other layer
reconstructs protocol path, fallback history, or context sources.

## Allowed Dependencies

- Runtime kernel -> contracts, runtime types, adapters, tool executor.
- Adapters -> protocol contracts, provider SDKs, capability contract helpers.
- Intent and tool orchestration -> context pipeline, runtime kernel, skills and tools.
- Context pipeline -> contracts, ContextCapabilityBridge interface, RAG and memory provider seams.
- Runtime capability bridge -> ContextAssembler, capability contracts, runtime
manifest builder, and service lookup helpers with no runtime imports.
- Service layer -> orchestration layer, runtime kernel, provider registry.
- Observability -> service read models, contracts.
- Frontend shell -> backend read models and shared UI runtime bridges.

## Forbidden Dependencies

- Adapter or provider code importing engine or service modules.
- Context pipeline selecting protocol paths or reaching into adapter internals.
- Context pipeline importing service lookup modules or runtime manifest builder.
- Service layer bypassing runtime kernel to call adapters directly.
- Intent planner performing retrieval or memory side effects.
- Service layer importing ContextAssembler or ContextCapabilityBridge internals.
- Frontend shell recreating protocol, fallback, or budget semantics locally.

## Prohibited Patterns

- Adapter-local protocol fallback competing with the runtime planner.
- Capability awareness config access performed outside ContextCapabilityBridge.
- New policy embedded in package `__init__` facades.
- Cross-layer imports that bypass published contracts or bridges.
- One file owning protocol planning, tool orchestration, persistence, and UI
projection at the same time.
