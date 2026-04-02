# Hook Guidelines

> In this Vue codebase, "hooks" means composables under `src/composables/`.
> They are the main place for reusable page logic.

## Overview

The repo already has mature composables for CRUD pages, drawers/forms, page AI,
plugin refresh, sockets, screenshot capture, and more. Reuse them before
building a new abstraction.

Primary examples:

- `frontend/apps/web-antd/src/composables/use-crud-list.ts`
- `frontend/apps/web-antd/src/composables/use-crud-form.ts`
- `frontend/apps/web-antd/src/composables/use-detail-page-ai.ts`
- `frontend/apps/web-antd/src/composables/use-plugin-admin-refresh.ts`

## Custom Hook Patterns

- Keep composables renderless and configuration-driven.
- Accept a typed options object rather than many positional arguments.
- Return state and actions the page can compose freely.
- Put business-specific UI rendering back in the page/component layer.

Example:

- `useCrudList` centralizes list/search/pagination/delete/page-AI logic without
  dictating the rendering component:
  `frontend/apps/web-antd/src/composables/use-crud-list.ts`

## Data Fetching

- Data fetching usually lives in API wrappers plus composables or route pages.
- CRUD composables call typed API modules, not raw URLs scattered through pages.
- Prefer schema-driven helpers from `#/adapter/form` and shared CRUD form/list
  composables before writing page-specific fetch/form plumbing.
- Request errors should go through shared helpers when the page opts out of the
  default interceptor UI.

Examples:

- API-backed list behavior:
  `frontend/apps/web-antd/src/composables/use-crud-list.ts`
- Shared error helper:
  `frontend/apps/web-antd/src/utils/error-helpers.ts`

## Naming Conventions

- Reusable composables should begin with `use`.
- Prefer file names that match the exported composable, for example
  `use-crud-list.ts`, `use-crud-form.ts`, `use-page-session.ts`.
- When a composable is page-AI related, extend the current page AI vocabulary
  instead of inventing parallel naming.

## Page AI Extension Rules

- Default to the platform page AI protocol.
- Add extra page operations through the existing extension points
  (`ai.extra`, `useDetailPageAi`, `usePageAIOperations`, shared builders).
- Prefer append/disable strategies over replacing the standard platform
  behavior.
- Open/create/edit actions should use existing builders like
  `buildPageAIFormExtraData()` or `createPrefilledCreatePageOperation()`.
- Extend `useCrudForm` / `useCrudDrawer` behavior rather than reimplementing
  field mapping and CRUD submit flows.

Examples:

- `frontend/apps/web-antd/src/views/admin/ai/agents/index.vue`
- `frontend/apps/web-antd/src/composables/use-ai-operations.ts`

## Tests

- Put composable tests in `src/composables/__tests__/`.
- Mock framework dependencies and request clients instead of standing up the
  whole app.

Examples:

- `frontend/apps/web-antd/src/composables/__tests__/use-crud-list.test.ts`
- `frontend/apps/web-antd/src/composables/__tests__/use-ai-operations.test.ts`

## Common Mistakes

- Hiding page-specific business assumptions inside a generic composable.
- Letting a composable import route pages or concrete business views.
- Recreating CRUD/page-AI flows that already exist in shared composables.
- Handling HTTP errors locally without disabling the default request error UI,
  which causes duplicate toasts.
- Hand-writing repetitive search/form schema structures instead of using shared
  adapter/form and CRUD helpers.
