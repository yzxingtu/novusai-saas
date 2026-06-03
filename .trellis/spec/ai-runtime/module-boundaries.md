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

## Refactor-First Rule For Broken Live Paths

### 1. Scope / Trigger

- Trigger: an AI dialogue live-path bug exposes duplicated policy, unclear
  ownership, repeated incident-specific patches, or a compatibility branch that
  keeps a known-bad behavior alive.
- Applies to runtime orchestration, protocol fallback, tool/skill routing,
  recovery evidence, diagnostics projection, memory/context governance, and
  frontend AI shell state derived from runtime facts.
- This is a new-system boundary. Prefer direct internal contract refactors over
  preserving broken behavior for backward compatibility.

### 2. Signatures

- Public surfaces that may remain stable as thin facades:
  - Python package imports from `app.ai`, `app.ai.engine`, `app.ai.runtime`,
    `app.ai.context`, and service facades.
  - API route paths, CLI command names/options, and persisted diagnostic field
    names used by operators.
- Internal seams that should be refactored when they are wrong:
  - duplicated fallback policy
  - per-call-site evidence trust checks
  - read-model repairs that compensate for producer-side bad state
  - root-cause or diagnostics reinterpretation that hides a producer bug
  - legacy compatibility branches that only exist to keep incorrect live output
    classified as successful

### 3. Contracts

- One runtime fact must have one owner. If several layers independently decide
  the same truth, move the decision into the owning runtime contract and make
  callers consume that contract.
- Thin facades may preserve public imports/routes/commands, but new behavior
  belongs behind the facade in the focused owner module.
- Do not add compatibility flags, fallback branches, temporary exceptions, or
  read-model-only patches that keep retired behavior alive in new-system AI
  dialogue live paths. Thin public facades may preserve stable imports, routes,
  and commands, but live behavior must move to the canonical owner contract.
- Diagnostics and monitoring may expose producer facts; they must not convert a
  bad producer result into success by reinterpreting evidence downstream.
- Historical data repair is read-only unless an explicit migration/repair
  command is designed. Read-model repair must not become the canonical live
  producer path.

### 4. Validation & Error Matrix

| Condition | Expected Action |
|---|---|
| Repeated bug appears in the same policy across CLI, monitoring, and runtime | Refactor the policy into one owner; update all callers to consume it |
| A read-model patch is needed to display old records | Keep it read-only and separately fix the producer path |
| A diagnostic projector can hide the symptom by changing classification | Reject as the primary fix; fix the upstream producer/contract |
| Public import, route, or CLI command is already used externally | Keep a thin facade while moving internal behavior |
| Compatibility branch only preserves incorrect new-system behavior | Remove or replace it with the canonical contract |

### 5. Good/Base/Bad Cases

- Good: retired online-search recovery branches are removed from the runtime
  owner, while CLI and read models keep only thin historical diagnostic readers.
- Base: a facade keeps `ConversationService` or a CLI command stable, but the
  actual query/projection logic moves to focused support modules.
- Bad: root-cause marks a turn successful because a downstream projector ignores
  unfinished tool evidence that the producer wrongly finalized.
- Bad: a read-model patch becomes the only place where a bad runtime result is
  corrected for new conversations.

### 6. Tests Required

- Add a known-bug regression test before closing the bug when the issue was
  reported by a user or observed in a real conversation.
- Behavioral tests must exercise the owning contract, not only the downstream
  facade or diagnostics projection.
- Keep a route/CLI/read-model sentinel only as secondary coverage for stable
  public contracts.
- For AI dialogue live paths, follow `testing-discipline.md`: annotate test
  type, avoid self-fulfilling mocks, and document whether any browser validation
  is read-only or a real-dialogue smoke.

### 7. Wrong vs Correct

#### Wrong

- Add one more branch in CLI/monitoring/root-cause to reinterpret a malformed
  runtime result as success.
- Keep a compatibility flag that lets the old broken path continue producing
  final answers.
- Fix only historical display while leaving the live producer path unchanged.

#### Correct

- Move the decision to the owning runtime contract, delete or bypass the broken
  internal path, and update all callers.
- Preserve public routes/imports/commands through a thin facade only when the
  external surface is stable.
- Record any unavoidable public-contract migration path as governance debt with
  a removal trigger; it must not preserve retired live behavior.

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
7. Tool runtime and skills: tool catalog, consent gating, and tool execution.
Online search/web research and page operations are retired from AI dialogue
live paths.
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
- Frontend shell -> backend read models and explicit domain APIs.

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
