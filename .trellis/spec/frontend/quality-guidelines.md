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

## Scenario: Playwright Authenticated Identity Smoke Coverage

### 1. Scope / Trigger

- Trigger: shared identity display, remote identity selectors, profile identity
  cards, operation logs, AI call logs, or organization member panels change.
- Why this needs code-spec depth: these pages are visually sensitive and span
  admin + tenant surfaces, so browser coverage must avoid captcha / login UI
  flakiness and validate the actual identity containers instead.

### 2. Signatures

- Config:
  - `frontend/apps/web-antd/playwright.config.ts`
- Session helpers:
  - `frontend/apps/web-antd/__tests__/e2e/common/session.ts`
  - `frontend/apps/web-antd/__tests__/e2e/common/auth.ts`
  - `frontend/apps/web-antd/__tests__/e2e/common/admin-auth.ts`
- Smoke specs:
  - `frontend/apps/web-antd/__tests__/e2e/admin-dashboard.spec.ts`
  - `frontend/apps/web-antd/__tests__/e2e/admin-profile.spec.ts`
  - `frontend/apps/web-antd/__tests__/e2e/tenant-dashboard.spec.ts`
  - `frontend/apps/web-antd/__tests__/e2e/tenant-profile.spec.ts`
  - `frontend/apps/web-antd/__tests__/e2e/organization.spec.ts`
  - `frontend/apps/web-antd/__tests__/e2e/operation-log.spec.ts`
  - `frontend/apps/web-antd/__tests__/e2e/ai-call-logs.spec.ts`

### 3. Contracts

- Default browser base URL is `http://localhost:5666` unless
  `E2E_BASE_URL` overrides it.
- Tenant domain mode is opt-in via `TENANT_E2E_USE_DOMAIN=true`; do not require
  subdomain routing for ordinary authenticated page smoke coverage.
- Playwright auth helpers must call backend login APIs directly:
  - `POST /admin/auth/login`
  - `POST /tenant/auth/login`
- Session helpers must seed namespaced localStorage keys instead of dragging UI
  captcha flows into every smoke test:
  - `${namespace}_admin_token`
  - `${namespace}_admin_refresh_token`
  - `${namespace}_tenant_admin_token`
  - `${namespace}_tenant_admin_refresh_token`
- Required env for tenant smoke:
  - `TENANT_ADMIN_USERNAME`
  - `TENANT_ADMIN_PASSWORD`
  - `TENANT_ADMIN_TENANT_CODE`
- Required env for admin smoke:
  - `ADMIN_USERNAME` / `PLATFORM_ADMIN_USERNAME`
  - `ADMIN_PASSWORD` / `PLATFORM_ADMIN_PASSWORD`
- Identity smoke assertions should target stable page anchors plus
  `.identity-display`, `.member-panel`, `.monitoring-grid`, or `.vxe-table`
  instead of brittle label internals.

### 4. Validation & Error Matrix

| Condition | Expected Behavior |
|---|---|
| Valid admin credentials | Admin dashboard / profile smoke passes with API-seeded session |
| Valid tenant credentials + tenant code | Tenant dashboard / profile / organization / logs smoke passes |
| Missing tenant code | Tenant smoke skips instead of hanging on login UI |
| Tenant domain env absent | Suite still runs against localhost |
| Page text shifts from “最近活动” to “近期活动” | Spec should assert the real page anchor, not an outdated copy guess |

### 5. Good/Base/Bad Cases

- Good: seed auth once in `beforeEach`, navigate directly to the protected page,
  and assert `.identity-display` plus the page's real business anchor.
- Base: tenant smoke stays on localhost and provides `tenantCode` only to the
  backend login API.
- Bad: use drag-slider captcha automation in every browser test, then treat
  intermittent login failures as page regressions.

### 6. Tests Required

- `pnpm --dir frontend exec vue-tsc --noEmit --skipLibCheck --pretty false -p apps/web-antd/tsconfig.json`
- `pnpm --dir frontend/apps/web-antd test:e2e -- --grep "Tenant Dashboard smoke|Tenant Profile smoke|Tenant Organization smoke|Tenant Operation Logs smoke|Tenant AI Call Logs smoke"`
- `pnpm --dir frontend/apps/web-antd test:e2e -- --grep "Admin Dashboard smoke|Admin Profile smoke"`

### 7. Wrong vs Correct

#### Wrong

- Make page-smoke coverage depend on solving captcha sliders through the login
  UI.
- Assert hidden or stale copy tokens when a stable business section title or
  shared component already exists.

#### Correct

- Use backend login APIs to create tokens and seed the namespaced browser
  session before `page.goto(...)`.
- Assert the shared identity container and the page's real visible anchor text /
  table shell.

## Code Review Checklist

Before merge, confirm:

- The page uses an existing platform pattern if one exists.
- Text, permissions, menu ownership, and route ownership are correct.
- Custom buttons, dropdown items, `CellOperation` custom codes, and
  `CellSwitch` toggles are not relying on backend `403` as the only guard.
- Upload/download/image behavior uses the attachment helpers.
- API transforms and types stay in the API/types layers.
- Unit tests and browser validation match the real risk of the change.
