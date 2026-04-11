# Frontend AI Shell

## Goal

Frontend AI surfaces should compose state from focused composables and avoid
re-implementing backend orchestration semantics.

## Required Split

- public entry facades
  - stable route/component/composable paths may stay thin wrappers so imports
    and route registration do not churn
- shell/core implementations
  - `*-shell.vue` and `*-core.ts` files own the real rendering and workflow
    logic behind those stable facades
- focused helpers
  - split repeated state domains or formatting helpers into co-located files
    when the seam is real (`history`, `variables`, page capability/policy,
    monitoring identity, etc.)
- shared contracts
  - message view model
  - tool-call view model
  - error surface
  - diagnostics surface

## Rules

- thin public wrappers should only forward props/events/exports; do not put new
  workflow branches back into them
- page and drawer shells should own layout + orchestration, then keep pushing
  repeated sections into child units or helper modules instead of re-growing the
  route entry file
- composables should expose one dominant state domain when a split seam is real;
  do not create fake micro-hooks that only forward a few local refs
- frontend must consume backend read models when available instead of rebuilding
  them from raw metadata across multiple places
- message rendering, diagnostics rendering, and error rendering should be
  separate components
- route-level pages should delegate to shell/components instead of embedding all
  sections inline
- page runtime state should come from the shared UI Runtime bridge and shared AI
  policy helpers, not from page-local registration registries

## Current Implementation Notes (2026-04, Transitional)

- `frontend/apps/web-antd/src/components/business/ai-chat-panel/use-ai-chat-core.ts`
  still hosts the primary chat state machine; treat it as the current canonical
  entrypoint until the composable split is complete.
- `frontend/apps/web-antd/src/components/business/ai-chat-panel/ChatMessageItem.vue`
  remains the main message render surface; new message subcomponents should
  target a future split rather than extending the monolith.

## Prohibited Patterns

- re-growing thin facades such as `use-ai-chat.ts`, `use-ai-operations.ts`,
  route entry SFCs, or shell forwarding components into new orchestration hubs
- one `use-ai-chat-core.ts` or `*-shell.vue` becoming the excuse to reintroduce
  unrelated product flows forever; keep extracting repeated seams instead of
  treating the first split as the last split
- frontend-only guesses about runtime protocol/fallback semantics
- reviving legacy page-AI registration or page-operation registry flows after
  the shared UI Runtime bridge became the canonical path
