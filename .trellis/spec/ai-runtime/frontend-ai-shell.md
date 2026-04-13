# Frontend AI Shell

## Goal

Frontend AI surfaces must compose state from focused composables and shared
runtime bridges, not re-implement backend orchestration semantics.

## Required Split

- Public entry facades remain thin wrappers for stable imports and routes.
- Shell or core implementations own layout and workflow logic.
- Focused helpers own a single, real state domain such as history or variables.
- Shared view models define message, tool-call, error, and diagnostics surfaces.

## Stable Contracts

- The chat entry composable is the single orchestration surface and composes
  focused helpers for streaming, history, attachments, memory, variables,
  interactions, and export.
- Chat message rendering is decomposed into a shell plus focused blocks
  (assistant/user/error/tool-call/diagnostics) to keep the shell layout-only.
- Page context and page operations flow through the shared AI runtime bridge;
  page key normalization and page-operation types come from the shared runtime.
- Shared AI chat API calls live in the shared API module so UI surfaces do not
  embed their own requestClient flows.

## Rules

- Thin facades only forward props, events, or exports.
- Shell pages own orchestration, then extract repeated sections into companions.
- Composables should expose one dominant domain; avoid micro-hooks that only
forward local refs.
- Frontend should consume backend read models where available instead of
rebuilding them from raw metadata in multiple places.
- Route-level pages delegate to shell components instead of embedding full
workflows inline.
- Page-AI policy flows through `route.meta.ai` and the shared policy parser.
Do not create a second policy surface for a single page.
- Page runtime state comes from the shared UI runtime bridge, not from
page-local registries.

## Transitional Notes

- Wrapper pattern is canonical, but internal shell granularity is still in
motion. Avoid freezing helper or companion file names as global rules.
- CRUD-specific AI overrides are a narrow compatibility seam and must not
replace route-level AI policy.

## Prohibited Patterns

- Re-growing thin facades into new orchestration hubs.
- Frontend-only guesses about protocol or fallback semantics.
- Inventing a second page-AI policy surface beside `route.meta.ai`.
- Reviving legacy page-AI registration flows outside the shared UI runtime
bridge.
