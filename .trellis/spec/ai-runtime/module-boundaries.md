# Module Boundaries

## Goal

Keep the AI runtime modular enough that protocol work, intent/tool orchestration,
context assembly, and service-facing workflows can evolve independently.

## Runtime Layers (Stable Ownership)

1. Contracts and diagnostics: stable DTOs for intents, budgets, protocol plans,
turn records, and capability bundles used across layers.
2. Intent and tool orchestration: intent planning, tool rounds, recovery
decisions, execution budgets, and unified stream or sync state.
3. Context pipeline: system prompt assembly, RAG injection, compaction, and
memory recall orchestration without direct service or adapter imports.
4. Runtime kernel: protocol planning, protocol chain execution, and fallback or
rescue policy for a single provider turn.
5. Adapter and provider layer: protocol-specific request construction and
response mapping for one protocol step.
6. Tool runtime and skills: tool catalog, consent gating, tool execution,
page operations, and web research orchestration.
7. Service layer: business use cases, persistence, memory capture, and read
model projection.
8. Observability and monitoring: diagnostics projection and operator read models.
9. Frontend AI shell: UI composition and state distribution.

## Stable Boundary Contracts

- Protocol planning lives in the runtime kernel. Adapters execute one protocol
path at a time and must not invent fallback chains.
- Context assembly depends on the ContextCapabilityBridge contract. The context
engine must not import runtime or service internals directly.
- Long-term memory recall uses the LongTermMemoryProvider protocol from the
context layer. The service layer owns the provider factory and may lazy-import
its implementation.
- Public package imports are protected by lazy export facades in `app.ai`,
`app.ai.engine`, `app.ai.context`, `app.ai.runtime`, and tool packages. Heavy
imports must stay out of `__init__` modules.
- Turn diagnostics flow through TurnRecord and CapabilityBundle. No other layer
reconstructs protocol path, fallback history, or context sources.

## Allowed Dependencies

- Runtime kernel -> contracts, runtime types, adapters, tool executor.
- Adapters -> protocol contracts, provider SDKs, capability contract helpers.
- Intent and tool orchestration -> context pipeline, runtime kernel, skills and tools.
- Context pipeline -> contracts, capability bridge, RAG and memory provider seams.
- Service layer -> orchestration layer, runtime kernel, provider registry.
- Observability -> service read models, contracts.
- Frontend shell -> backend read models and shared UI runtime bridges.

## Forbidden Dependencies

- Adapter or provider code importing engine or service modules.
- Context pipeline selecting protocol paths or reaching into adapter internals.
- Service layer bypassing runtime kernel to call adapters directly.
- Intent planner performing retrieval or memory side effects.
- Frontend shell recreating protocol, fallback, or budget semantics locally.

## Prohibited Patterns

- Adapter-local protocol fallback competing with the runtime planner.
- New policy embedded in package `__init__` facades.
- Cross-layer imports that bypass published contracts or bridges.
- One file owning protocol planning, tool orchestration, persistence, and UI
projection at the same time.
