# Frontend AI Shell

## Goal

Frontend AI surfaces must compose state from focused composables and shared
runtime bridges, not re-implement backend orchestration semantics.

## Stable Page-AI Chain (Executable)

The page AI policy and runtime context flow is fixed and must remain a single
chain:

1. Route meta defines page AI policy at `route.meta.ai`.
2. `useCurrentPageAIPolicy()` normalizes and enforces the policy
   (`frontend/apps/web-antd/src/composables/use-ai-page-policy.ts`).
3. `layouts/basic.vue` is the only global layout that wires the policy into the
   AI panel and initializes the runtime bridge
   (`frontend/apps/web-antd/src/layouts/basic.vue`).
4. `AIChatSlidePanel` forwards policy props to `AIChatSlidePanelShell`, which
   uses `usePageAICapability` and passes runtime page context into `useAIChat`
   (`frontend/apps/web-antd/src/components/business/ai-slide-panel/AIChatSlidePanel.vue`,
   `frontend/apps/web-antd/src/components/business/ai-slide-panel/AIChatSlidePanelShell.vue`,
   `frontend/apps/web-antd/src/components/business/ai-slide-panel/use-page-ai-capability.ts`).
5. `usePageAICapability` reads the runtime bridge (`getRuntimeThinPageContext`,
   `getRuntimePageContextDiagnostics`) and filters operations by the policy
   (`frontend/apps/web-antd/src/components/business/ai-runtime/runtime-bridge.ts`).

No page-level component or composable may introduce an alternate policy parser.

## Required Split

- Public entry facades remain thin wrappers for stable imports and routes.
- Shell or core implementations own layout and workflow logic.
- Focused helpers own a single, real state domain such as history or variables.
- Shared view models define message, tool-call, error, and diagnostics surfaces.

## Stable Contracts

- The chat entry composable is the single orchestration surface and composes
  focused helpers for streaming, history, attachments, memory, variables,
  interactions, and export.
- `AIChatSlidePanel.vue` remains the public wrapper, while
  `AIChatSlidePanelShell.vue` is now a thin composition shell over
  `use-ai-chat-slide-panel-shell.ts`,
  `use-ai-chat-slide-panel-shell-bindings.ts`, and focused watcher/helpers such
  as `use-rich-text-task-orchestration-watchers.ts`. New slide-panel behavior
  belongs in those focused companions, not back in the shell SFC.
- Chat message rendering is decomposed into a shell plus focused blocks
  (assistant/user/error/tool-call/diagnostics) to keep the shell layout-only.
- User chat route shells now follow `index.vue -> index-shell.vue ->
  page-local composables/context -> focused workspace sections`.
  `UserAIChatWorkspace.vue` is a thin shell over
  `use-user-ai-chat-workspace.ts`,
  `user-ai-chat-workspace-context.ts`, and section components such as
  `UserAIChatWorkspaceHeader.vue`,
  `UserAIChatWorkspaceMessages.vue`, and
  `UserAIChatWorkspaceComposer.vue`.
- Page context and page operations flow through the shared AI runtime bridge;
  page key normalization and page-operation types come from the shared runtime.
- Shared AI chat API calls live in the shared API module so UI surfaces do not
  embed their own requestClient flows.
- Monitoring and admin AI pages now follow the same wrapper-to-shell rule:
  thin route/SFC wrappers forward to `*Shell.vue`, and the shell delegates
  focused cards or panels rather than embedding one long page template.
- Heavy AI admin forms follow `wrapper -> shell/content -> schema/value helper`
  seams. The admin skill form keeps `form.vue` as the wrapper, while
  `SkillFormShell.vue`, `SkillFormContent.vue`, `skill-form-schema*.ts`,
  `skill-form-values.ts`, and `SkillFormToolPanels.vue` own the actual form
  behavior.

## Responsibility Boundaries

- Route/page shell: only declares `route.meta.ai` and stays thin. It does not
  parse policy and does not read DOM/page runtime directly.
- Policy composable: `useCurrentPageAIPolicy()` is the single interpreter of
  `route.meta.ai`, merging RBAC, default mode, and policy normalization.
  It owns `currentPageAIExecutionPolicy` and `currentRouteAISecurityPolicy`.
- Layout shell: `layouts/basic.vue` binds the policy to `AIChatSlidePanel`,
  calls `ensureGlobalUIRuntime({ getRoute })`, and passes `pageContextKey` to
  the AI panel. It does not re-map policy values.
- AI panel shell: `AIChatSlidePanelShell` composes `usePageAICapability` and
  `useAIChat`, and uses the runtime-provided `PageContext` as a read-model.
  It does not infer page policy from route meta.
  Slide-panel shell state should further delegate to page-local shell helpers
  (`use-ai-chat-slide-panel-shell.ts` and related companions) rather than
  re-growing orchestration inline.
- Runtime bridge: `runtime-bridge.ts` is the only owner of DOM-driven page
  context assembly (snapshot, form state, page key, security policy).
  It provides read-only accessors for `PageContext` and diagnostics, and it is
  the canonical frontend owner for compact navigation metadata
  (`page_data.navigation_catalog` / `page_data.navigation_context`) carried in
  thin page context.
- AI panel display helpers and policy filters must not re-emit legacy
  non-`ui_` page-operation names. Live page-operation chips, pending-op state,
  and navigation-only allowlists recognize only canonical `ui_*` runtime tools.
- Read-model: `PageContext` and related structures (from shared API types)
  are treated as read-models. UI code must not reconstruct or mutate them
  outside the runtime bridge.
- Page-local workspace or form shells may use typed local context seams and
  colocated composables when the state is route-owned and not reused across
  surfaces. They should not promote route-only state into shared global stores
  just to avoid passing focused refs/actions.

## Rules

- Thin facades only forward props, events, or exports.
- Shell pages own orchestration, then extract repeated sections into companions.
- Composables should expose one dominant domain; avoid micro-hooks that only
forward local refs.
- Once a shell has been reduced to layout plus composition, new feature work
  must continue in its extracted companions (`*Shell.ts`, `*Content.vue`,
  `*Panel.vue`, `*Card.vue`, `*-schema.ts`, `*-values.ts`) instead of adding
  another branch back into the wrapper or shell.
- Frontend should consume backend read models where available instead of
rebuilding them from raw metadata in multiple places.
- Route-level pages delegate to shell components instead of embedding full
workflows inline.
- Page-AI policy flows through `route.meta.ai` and `useCurrentPageAIPolicy()`.
Do not create a second policy surface for a single page, a page-local registry,
or a parallel policy composable.
- Page runtime state comes from the shared UI runtime bridge, not from
page-local registries.
- `usePageAICapability` and the AI panel only consume `pageContextKey` and the
runtime read-model; they must not parse `route.meta.ai` or infer policy.

## Transitional Notes

- Wrapper pattern is canonical, but internal shell granularity is still in
motion. Avoid freezing helper or companion file names as global rules.
- CRUD-specific AI overrides are a narrow compatibility seam and must not
replace route-level AI policy.

## Prohibited Patterns

- Re-growing thin facades into new orchestration hubs.
- Moving one 900-line shell into a differently named 900-line shell or content
  file without introducing a real responsibility split.
- Frontend-only guesses about protocol or fallback semantics.
- Inventing a second page-AI policy surface beside `route.meta.ai`.
- Reviving legacy page-AI registration flows outside the shared UI runtime
bridge.
