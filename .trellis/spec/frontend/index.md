# Frontend Development Guidelines

> Actual frontend conventions for the NovusAI Vben Admin monorepo. These docs
> are derived from `.cursor/rules/*.md`, `.cursor/skills/novusai-saas/references/*.md`,
> and the current Vue 3 codebase.

## Stack Summary

- Vue 3.5 + TypeScript + Vben Admin 5.x + Ant Design Vue + Vite + Pinia.
- Three UI surfaces are maintained separately: `admin`, `tenant`, and `user`.
- The dominant page patterns are `useCrudPage` for data-heavy table pages and
  `useCrudList` for card, split-panel, and configuration pages.
- Shared page AI infrastructure is already built into the platform; new pages
  should extend it instead of recreating it.

## Sources Of Truth

- Frontend architecture handbook:
  `frontend/apps/web-antd/src/views`, `src/composables`, `src/store`,
  `src/router`, `src/api`
- CRUD table page example:
  `frontend/apps/web-antd/src/views/admin/system/attachments/index.vue`
- CRUD card/list page example:
  `frontend/apps/web-antd/src/views/admin/ai/agents/index.vue`
- Upload/download contract:
  `frontend/apps/web-antd/src/api/admin/attachment.ts`
- Permission directive:
  `frontend/apps/web-antd/src/directives/access.ts`
- User routing and layout:
  `frontend/apps/web-antd/src/router/routes/user/index.ts`,
  `frontend/apps/web-antd/src/layouts/user.vue`

## Guidelines Index

| Guide | Description | When to Read |
|-------|-------------|--------------|
| [Directory Structure](./directory-structure.md) | Where views, composables, API modules, stores, and shared utilities live | Before adding or moving frontend files |
| [Component Guidelines](./component-guidelines.md) | Page/component patterns, i18n, permissions, uploads, and styling | Before building or editing UI |
| [Hook Guidelines](./hook-guidelines.md) | Composable design, data loading, and page AI extension rules | Before creating or extending a composable |
| [State Management](./state-management.md) | Pinia usage, shared stores, route/domain state, and public config | Before adding store state |
| [Type Safety](./type-safety.md) | API transforms, generics, payload typing, and unsafe patterns to avoid | Before touching types or API wrappers |
| [Quality Guidelines](./quality-guidelines.md) | Linting, tests, browser validation, and release checks | Before merging frontend work |

## Non-Negotiable Rules

- Do not hardcode user-visible text; use `$t()` or `t()`.
- Do not use `console.log`.
- Do not abuse `any`.
- Do not cross-import business code between `admin`, `tenant`, and `user`.
- Keep pages, components, composables, and API adapters high-cohesion: shared
  data logic belongs in shared layers, while page-specific rendering stays in
  the page/component layer.
- Keep frontend modules low-coupling: depend on shared composables, API
  modules, and contracts instead of another surface's business internals.
- Page SFCs must not become business orchestrator hubs. If one page owns API
  transport transforms, permission decisions, modal workflows, upload/download
  transport, and cross-section state synchronization together, split into
  `page shell + composables + section components`.
- Page/business modules that violate this rule should be treated as blocked for
  merge until split seams are introduced (not a post-merge TODO).
- Do not create ad-hoc upload/download flows outside the attachment system.
- Do not create a second request-error UX when `requestClient` already owns the
  error.
- Do not ship protected UI entry points that rely on backend `403` as the only
  permission guard.
- Do not duplicate dynamic menu translations in the frontend; host menus are
  already translated by backend menu data, while plugin menu titles come from
  plugin manifests.

## Governance Refactor Patterns (Executable)

- Oversized operations/list pages default split:
  route/page shell keeps layout and wiring; composables own data/query/workflow;
  section components own presentation details.
- Shared components (for example file picker, config form, plugin drawer body)
  must not absorb unrelated product workflows by option creep. Split by
  capability boundary before adding another unrelated feature switch.
- Plugin frontend pages follow the same rule as host pages:
  keep plugin route shell thin, extract plugin-local composables and section
  units under the plugin package.
- Codegen frontend defaults:
  keep builder page shell focused on route/state handoff, extract field editor,
  DB import, preview/history, and dirty-state guards into focused composables or
  section components.

## Pre-Development Checklist

Read these files in order when touching frontend code:

1. This index.
2. [Directory Structure](./directory-structure.md)
3. The task-specific file:
   - page/component work -> [Component Guidelines](./component-guidelines.md)
   - composables/page AI extensions -> [Hook Guidelines](./hook-guidelines.md)
   - Pinia/domain/auth/public config work -> [State Management](./state-management.md)
   - API payloads and types -> [Type Safety](./type-safety.md)
   - tests and regression checks -> [Quality Guidelines](./quality-guidelines.md)
4. If the task crosses backend, AI, domains, uploads, plugins, or permissions,
   also read `../guides/cross-layer-thinking-guide.md`.

## Representative Examples In This Repo

- Table CRUD page with `useCrudPage`:
  `frontend/apps/web-antd/src/views/admin/system/attachments/index.vue`
- Card/list CRUD page with `useCrudList` and page AI extras:
  `frontend/apps/web-antd/src/views/admin/ai/agents/index.vue`
- Upload and download wrapper:
  `frontend/apps/web-antd/src/api/admin/attachment.ts`
- Shared renderless list composable:
  `frontend/apps/web-antd/src/composables/use-crud-list.ts`
- User domain-aware routing:
  `frontend/apps/web-antd/src/router/routes/user/index.ts`
- Shell + parts decomposition examples:
  `frontend/apps/web-antd/src/components/business/file-picker/**`,
  `frontend/apps/web-antd/src/views/admin/plugins/modules/plugin-config-drawer/**`

## Anti-Patterns To Avoid

- Building a one-off page pattern when `useCrudPage`, `useCrudList`,
  `useCrudDrawer`, or shared page AI helpers already cover it.
- Calling `requestClient.upload()` directly from business code.
- Parsing image or attachment ids with blind `Number()` / `parseInt()` casts.
- Creating local permission logic instead of using `v-access` or shared access
  helpers.
- Letting page code guess menu-title ownership between host menus and plugin
  manifests.
- Keeping one page/component as a "business general manager" that coordinates
  unrelated feature flows across multiple domains.
