# Frontend AI Shell

## Goal

Frontend AI surfaces must compose state from focused composables and shared
runtime bridges, not re-implement backend orchestration semantics.

## Page Awareness Retirement

Page awareness is no longer a frontend AI shell capability. Frontend AI
surfaces must not collect DOM state, build thin `page_context`, join
`page_session` channels, render Page AI rails, or send page-operation data to
AI dialogue APIs.

If AI must analyze data that is currently visible on a page, add a backend
read-model/API/report/export endpoint or a permissioned installable skill-pack
tool. Do not make the rendered page the source of truth.

Route `meta.ai` may remain as compatibility metadata for whether chat is shown,
but it must not be used to reintroduce DOM/page runtime behavior.

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
- AI chat shells render conversation, backend read-models, skill results, and
  explicit rich-text/task state only. They do not treat current DOM/page state
  as model context.
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

- Route/page shell: stays thin and does not read DOM/page runtime for AI.
- Layout shell: `layouts/basic.vue` mounts chat surfaces, but does not initialize
  page runtime bridges or pass page context props to the AI panel.
- AI panel shell: composes chat, history, attachments, memory, variables,
  routing, and rich-text task helpers. It must not compose page-AI capability
  helpers or pass page context into `useAIChat`.
  Slide-panel shell state should further delegate to page-local shell helpers
  (`use-ai-chat-slide-panel-shell.ts` and related companions) rather than
  re-growing orchestration inline.
- Retired page-runtime helpers must not be used as live dependencies. If a
  compatibility module remains, it must be isolated from the AI dialogue shell.
- `turnFlow` is the canonical assistant-process protocol. Live chat state,
  streaming SSE handlers, and history merge/finalize helpers must not mutate
  canonical `turnFlow` back into legacy `thinkingContent`, `optimizingTools`,
  `ragSources`, or `toolCalls` as the primary live truth source. Legacy fields
  may still be read as bounded fallback input for old persisted messages, but
  they are not a live writable truth owner.
- Live tool-result reconciliation inside canonical `turnFlow` must match
  running tool evidence by `tool_call_id` / canonical event `id`. Same-name
  fallback is not a valid live owner path because repeated tool names can exist
  within one turn.
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
- Do not add page-awareness policy surfaces, page-local operation registries,
  DOM scanners, `data-ai*` contracts, or `ui_*` runtime tool UI.
- Retired UI runtime bridge modules must not be treated as live AI shell
  dependencies.

## Transitional Notes

- Wrapper pattern is canonical, but internal shell granularity is still in
  motion. Avoid freezing helper or companion file names as global rules.
- CRUD-specific AI overrides are compatibility metadata only; they must not
  register page-operation capabilities.

## Transcript-first & Diagnostics Gate (2026-04)

- `ChatMessageDiagnostics` and `TurnTimeline` must not expose protocol path,
  selected tools, selected skills, or context-source internals to end users by
  default. Those surfaces are gated by `useDiagnosticsPolicy()` (or an
  equivalent tenant-level flag); default rendering for end-user scopes
  (tenant / user) stays off.
- AI chat surfaces should support a `transcript-first` layout option in which
  the chat transcript is the primary content region and tool-call / reasoning /
  citation blocks render inline with messages. The existing side-panel dock
  remains a valid compact mode but cannot be the only supported layout.
- `use-ai-chat-turn-flow.ts` and related turn-flow ingestion helpers must stay
  under the 500-line composable budget (`module-boundaries.md`). Message merge,
  streaming lifecycle, and tool-call collection belong in a small number of
  focused helpers, not in a sprawl of one-purpose `use-ai-chat-message-merge-*`
  micro-hooks.
- Legacy turn-flow detection helpers (`isLegacyStage`, `dedupeTimelineByStageType`,
  and related `LegacyStageSource` enums) are retired once canonical `turnFlow`
  is the only write path; they must not be kept as live readers.

## Prohibited Patterns

- Re-growing thin facades into new orchestration hubs.
- Moving one 900-line shell into a differently named 900-line shell or content
  file without introducing a real responsibility split.
- Frontend-only guesses about protocol or fallback semantics.
- Inventing page-AI policy surfaces, page-operation registries, or DOM runtime
  bridges for AI dialogue.
- Adding new `use-ai-chat-*` micro-composables whose only job is to forward one
  ref or one helper. New chat behavior goes into the existing bounded set of
  domain composables (core, streaming, turn-flow, history, interactions,
  memory, export).
- Default-enabled diagnostics surfaces that expose protocol / tool / skill /
  context-source internals to end users without a diagnostics policy gate.
