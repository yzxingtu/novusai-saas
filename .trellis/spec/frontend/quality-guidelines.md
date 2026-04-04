# Quality Guidelines

> Frontend changes are complete only when static checks, unit tests, and the
> relevant browser validations are covered.

## Overview

Common commands from `frontend/`:

```bash
pnpm lint
pnpm test:unit
pnpm build:antd
```

For upload/media heavy changes, the repo also relies on targeted type and test
checks such as:

```bash
pnpm exec vue-tsc --noEmit --skipLibCheck --pretty false -p apps/web-antd/tsconfig.json
```

## Forbidden Patterns

- `console.log`
- hardcoded user-visible text
- direct `requestClient.upload()` in business code
- `window.open()` download flows
- duplicate HTTP error toasts caused by page-local catch handlers that do not
  disable the default request error UI
- cross-surface imports between `admin`, `tenant`, and `user` business modules
- unsanitized `v-html`

## Required Patterns

- Use `$t()` / `t()` for visible text.
- Use `v-access` or shared access helpers for permission-gated UI.
- Do not rely on backend `403` alone for routine permission UX. Protected
  entry points should normally be hidden or disabled in the frontend as well.
- Use `smartUploadFile` or its wrapped shared components for uploads.
- Use `requestClient.download()` plus `downloadBlob()` for downloads.
- Use shared error helpers (`showRequestError`, `getErrorMessage`) when a page
  deliberately owns the request error UI.
- If a page takes ownership of HTTP error presentation, disable the default
  request error UI with `showErrorMessage: false` and `showCodeMessage: false`
  first.
- Do not expand legacy `200 + success=false` soft-failure contracts into new
  endpoints or new page flows.
- New comments, TODOs, and inline documentation should follow the repo's
  bilingual comment convention when comments are necessary.

Examples:

- `frontend/apps/web-antd/src/api/admin/attachment.ts`
- `frontend/apps/web-antd/src/directives/access.ts`
- `frontend/apps/web-antd/src/utils/error-helpers.ts`

## Testing Requirements

- Add or update unit tests for composables, stores, and logic-heavy utilities.
- Prefer `chrome-devtools` for routine browser validation; use Playwright when
  file uploads or multi-tab flows require it.
- For CRUD pages, validate search, pagination, and permission-controlled
  actions.
- For permission work, validate both sides of the contract:
  frontend entry-point visibility and backend enforcement.
- For forms, validate open, submit, and failure feedback.
- For upload/download flows, validate both the happy path and visibility/route
  correctness.
- For recycle-bin-enabled pages, validate the recycle bin UI and route behavior
  for the current surface.
- For request-error-owner changes, validate that one failed request produces one
  coherent message path.
- For quota/rate-limit work, validate the live runtime behavior rather than only
  CRUD/UI responses.
- Check console and network first before blaming page logic.
- When a page uses `CellOperation` custom actions or `CellSwitch`, explicitly
  validate that a limited-permission account cannot see or trigger update/delete
  behavior.
- When a page opens a protected drawer/modal from a custom button or dropdown,
  validate that the opener itself is hidden for accounts missing the target
  permission.

Examples:

- `frontend/apps/web-antd/src/composables/__tests__/use-crud-list.test.ts`
- `frontend/apps/web-antd/src/layouts/__tests__/locale-navigation-sync.test.ts`
- `frontend/apps/web-antd/src/store/shared/__tests__/public-config.test.ts`

## Browser Regression Priorities

- Confirm the right surface route opens (`admin`, `tenant`, or `user`).
- Confirm no new console errors remain after the change.
- Confirm route/menu/title/i18n stay in sync after locale changes.
- Confirm request failures show one coherent message path with `trace_id`
  preserved when relevant.
- Confirm users with list/detail-only roles do not see update/delete/test/toggle
  controls that would later fail with `403`.
- Confirm `novusai trace show <trace_id>` remains a viable operator workflow for
  backend-linked failures when the change affects request error presentation.
- Confirm plugin routes and menus respect runtime, permission, and locale rules
  when the task touches plugins.
- Confirm upload/download pages hit the expected attachment endpoints and do not
  regress to ad-hoc transport paths.
- Confirm recycle-bin behavior respects surface boundaries, especially admin vs
  tenant differences.
- Confirm plugin matrix coverage when relevant: menu enter, direct URL, hard
  refresh, locale switch, permission loss, and runtime-gated disable paths.

## Code Review Checklist

Before merge, confirm:

- The page uses an existing platform pattern if one exists.
- Text, permissions, menu ownership, and route ownership are correct.
- Custom buttons, dropdown items, `CellOperation` custom codes, and
  `CellSwitch` toggles are not relying on backend `403` as the only guard.
- Upload/download/image behavior uses the attachment helpers.
- API transforms and types stay in the API/types layers.
- Unit tests and browser validation match the real risk of the change.
