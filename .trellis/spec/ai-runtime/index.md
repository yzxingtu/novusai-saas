# AI Runtime Governance

This directory is the canonical governance source for NovusAI AI runtime work.

Use these files whenever the change touches:

- provider protocol selection or fallback
- chat turn orchestration
- streaming and non-streaming execution
- intent classification
- context assembly, memory, or RAG injection
- tool and skill routing
- installable skill-pack metadata, activation, or runtime exposure
- thread/session memory mode, memory pollution, or durable recall boundaries
- runtime diagnostics or monitoring projections
- runtime capability manifest or capability-awareness summaries
- frontend AI shell state boundaries

## Architectural Default

The runtime must stay high-cohesion and low-coupling:

- one owner for protocol planning
- one owner for intent classification
- one owner for context contribution
- one owner for transport assembly
- one owner for application command/query services
- stable contracts between layers instead of cross-layer reach-in

## No Current-Page Runtime

New-system AI dialogue must not rebuild page perception or page operation as a
runtime capability. The rendered browser page is not a source of truth for AI
dialogue.

AI dialogue live paths must not read, infer from, or operate:

- the current DOM, rendered page, route surface, or frontend editor instance
- `page_session`, `page_context`, `page_data`, `page_session_id`, or
  page-runtime sockets
- `ui_*`, `pageop_*`, page-operation registries, UI action channels, DOM
  scanners, page runtime bridges, or active-surface metadata

If future AI features need to analyze business data that happens to be visible
in the UI, expose that data through an explicit backend read-model, query API,
report/export artifact, or permissioned installable skill-pack tool. Do not use
current-page perception as the fallback integration path.

## Runtime Stack Summary

- Intent and tool orchestration owns IntentPlan and execution state.
- Context pipeline owns prompt assembly, RAG injection, and memory recall.
- Runtime capability inventory builds the manifest + compact summary after
context assembly and capability injection decisions.
- Tool and skill governance owns capability-pack activation, deferred or
discoverable tool exposure, and page-tool separation. Retired online-search
capability is unsupported and must not be surfaced as live runtime inventory.
- Memory governance owns capture, recall, and thread-level memory policy; it
must not be encoded in page adapters or prompt-only hints.
- Runtime kernel owns protocol planning, fallback, and guard enforcement.
- Adapters execute one protocol step and map provider responses.
- Service layer owns persistence, memory capture, and read models.

## Files

| File | Purpose |
|---|---|
| `module-boundaries.md` | canonical layer ownership, allowed dependencies, and anti-patterns |
| `provider-contracts.md` | provider capability declarations, protocol planning, and adapter rules |
| `intent-routing.md` | structured intent taxonomy and routing rules |
| `execution-state-machine.md` | shared turn lifecycle for streaming and non-streaming execution |
| `context-budget.md` | context contribution priorities and token-budget rules |
| `memory-rag-pipeline.md` | memory save/recall and RAG pipeline boundaries |
| `recovery-stop-loss.md` | retry, recovery, consent pause, and stop-loss policy |
| `observability.md` | turn diagnostics, trace surfaces, replay, and monitoring requirements |
| `tool-skill-governance.md` | skill routing, tool exposure, current-page runtime boundaries, and online-search removal governance |
| `plugin-runtime-registration.md` | process-local plugin resolver registration contract for AI runtime/CLI cold paths |
| `service-layer.md` | command/query split for AI application services |
| `frontend-ai-shell.md` | frontend shell/state/composable boundaries for AI UI surfaces |
| `testing-discipline.md` | **mandatory** testing-theater prevention: test categorization, mock boundaries, real-dialogue smoke requirements, known-bug-first discipline, four-gate milestone acceptance |

## Canonical Rule

Project rules, hooks, prompts, and implementation guides must reference this
directory instead of copying long AI runtime guidance into multiple places.

## Testing Gate (2026-04)

No AI dialogue change — including any "test pass / regressions green" claim —
may be treated as done without satisfying `testing-discipline.md`. In particular:

- Structural test green alone is not sufficient to claim a milestone or bug fix.
- Behavioral + smoke + known-bug gates are required alongside structural.
- Any PR touching AI dialogue live paths must answer the §7 PR self-check and
  annotate its tests with `structural` / `behavioral` / `smoke`.
