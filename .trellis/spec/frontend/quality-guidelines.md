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
- modules that mix page rendering, transport transforms, permission policy, and
  unrelated runtime side effects in one place
- page-level "business manager" modules that keep growing by adding unrelated
  workflows to one SFC/composable instead of splitting by stable responsibility
- duplicate HTTP error toasts caused by page-local catch handlers that do not
  disable the default request error UI
- cross-surface imports between `admin`, `tenant`, and `user` business modules
- reaching into another surface's page/store/component internals instead of
  using shared composables, API modules, or stores
- unsanitized `v-html`

## Required Patterns

- Use `$t()` / `t()` for visible text.
- Keep pages/components/composables/API wrappers high-cohesion: page-specific
  UI stays in the page layer, shared data/loading logic stays in shared
  composables or API modules.
- If a page or component has grown oversized, prefer `page shell + composables +
section components` or `component shell + focused child units` instead of
  adding more branches to the same SFC.
- When a refactor claims a shell is now thin, reviewers should expect the
  extracted workflow composables or child units to carry follow-up changes.
  Do not move new logic back into the shell just because the public path stayed
  stable.
- Bundled plugin frontends follow the same oversized-page rule as host
  frontends. Do not keep a giant plugin page just because it lives under
  `backend/plugins/**`; extract plugin-local section components and composables
  inside the plugin package, then validate with that plugin's own frontend
  build/lint/type gates.
- Bundled plugin interaction components can close with
  `component shell + controller/state-machine + copy/shared helpers`, but the
  claim is only complete when the extracted controller/layout/a11y seams have
  focused tests in the plugin package.
- Governance refactor default split:
  `page shell + composables + section components`, and keep API transport
  adaptation in API modules rather than SFC-local ad-hoc transforms.
- Codegen/plugin-heavy pages should expose narrow child contracts
  (props/events/injected refs) instead of cross-file mutable global state.
- Keep shared frontend abstractions low-coupling: expose narrow inputs/outputs
  so callers do not need router/store/plugin internals to use them.
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
- New comments, TODOs, and inline documentation must follow the repo's
  bilingual comment convention when comments are necessary.
- Shared frontend layers must not turn into cross-domain dump buckets. If a
  composable or shared component keeps absorbing unrelated page flows, split it
  by use case boundary instead of widening its option bag.
- When a page uses `provide/inject` to share refs/computed refs across extracted
  child components, do not treat the injected object as a plain value bag in
  templates. Child components must destructure the refs they need at the
  top level (or expose plain values/functions), otherwise Vue template unwrapping
  and `vue-tsc` type safety both break.

Examples:

- `frontend/apps/web-antd/src/api/admin/attachment.ts`
- `frontend/apps/web-antd/src/directives/access.ts`
- `frontend/apps/web-antd/src/utils/error-helpers.ts`

## Bilingual Comment Convention

- Comments are mandatory when the logic is complex, easy to misread, subtly
  ordered, compatibility-sensitive, repetitive enough to hide intent, or likely
  to be forgotten during later maintenance.
- Every retained code comment, inline documentation note, `TODO`, and `FIXME`
  must include both Chinese and English. Prefer Chinese first, then English,
  with explicit `中文:` and `EN:` labels.
- Keep comments concise and explain the reason or invariant, not the obvious
  syntax. If a small refactor would make the code self-explanatory, refactor
  first; if the UI/domain rule or execution order is still non-obvious, keep
  the bilingual comment immediately above the block it protects.
- Use this shape for ordinary comments:

```ts
// 中文: 这里保留稳定 key，避免刷新后会话状态丢失。
// EN: Keep the stable key so refreshes do not drop session state.
```

- Use this shape for longer helper documentation:

```ts
/**
 * 中文: 合并后端权限、计划限制和本地禁用态，得到按钮最终可用状态。
 *
 * EN: Combines backend permissions, plan limits, and local disabled state into
 * the final button availability.
 */
```

- Use this shape for follow-up notes:

```ts
// TODO: 中文: 旧弹窗迁移完成后删除这个适配分支。
// TODO: EN: Remove this adapter branch after the legacy modal migration lands.
```

## Governance Refactor Acceptance Gates

When a change claims "page split" or "shared UI governance" completion, reviewers
should require:

- Responsibility gate:
  route shell is thin, heavy data/workflow logic moved into focused composables.
- Anti-business-manager gate:
  no single page/component keeps unrelated workflow orchestration as the only
  integration point; extraction into section/composable seams is mandatory.
- Coupling gate:
  sections/components consume narrow contracts and do not depend on another
  surface/page internal state shape.
- Compatibility gate:
  route path, visible entry points, and permission behavior remain stable unless
  migration notes explicitly declare a change.
- Validation gate:
  at least one targeted unit test or e2e flow proves the extracted seam still
  works end-to-end.
- Contract gate:
  stable public component/page entry paths may stay in place, but the shell
  must no longer own cross-domain workflow state, API transforms, and dialog
  orchestration at once.

## Dev-only Bootstrap Credential for Local E2E

- Local bootstrap credentials should only be activated when
  `APP_ENV=development` and `DEV_BOOTSTRAP_AUTH_ENABLED=true` is present;
  browser-based prod/CI runs must never trigger this pathway.
- Playwright/local helpers should prefer this fast path when running suites against
  a developer workstation, but keep the legacy `/auth/login` experience as a
  fallback whenever the bootstrap flag is missing or tests run elsewhere.
- Ensure frontend helpers only call bootstrap endpoints from loopback hosts
  or local-dev hosts (`localhost`, `127.0.0.1`, `::1`, `*.local`) and require
  developer-specific secrets pulled from a local `backend/.env` entry:
  `DEV_ADMIN_BOOTSTRAP_SECRET` and `DEV_TENANT_BOOTSTRAP_SECRET`. Track only
  placeholders in `.env.example` or docs so no real secrets are committed.
- Helpers should prefer `POST /admin/auth/dev/bootstrap` and
  `POST /tenant/auth/dev/bootstrap`, while still allowing `/auth/login`
  fallback for CI or non-local environments.
- Bootstrap JWTs must honor the same expiration/refresh expectations as regular
  login tokens; shipping never-expiring tokens is forbidden.
- Document the feature flag, host allowlist, and `.env` secret expectation in the
  developer guide so the handshake is reproducible without exposing confidential
  values.

## Testing Requirements

- Add or update unit tests for composables, stores, and logic-heavy utilities.
- For `frontend/apps/web-antd` page regression and acceptance checks, prefer
  checked-in Playwright specs under
  `frontend/apps/web-antd/__tests__/e2e/`; do not treat MCP browser runs as the
  primary release evidence.
- Use the shared Playwright auth/bootstrap helpers in
  `frontend/apps/web-antd/__tests__/e2e/common/` so protected pages are tested
  through API-seeded sessions instead of manual login UI flows.
- `chrome-devtools` / other MCP browser tools remain valid for ad-hoc diagnosis,
  console/network inspection, and temporary triage, but non-essential page
  verification should not stop at MCP interaction transcripts when a Playwright
  spec can cover the flow.
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
- For `frontend/apps/web-antd` page regression, the source of truth is the
  checked-in Playwright spec under `__tests__/e2e`, not a one-off MCP browser
  walkthrough.
- New page/browser regression coverage should be added to
  `frontend/apps/web-antd/__tests__/e2e/*.spec.ts` and be runnable through
  `pnpm exec playwright test ...`.
- Playwright auth helpers should prefer backend dev bootstrap APIs:
  - `POST /admin/auth/dev/bootstrap`
  - `POST /tenant/auth/dev/bootstrap`
    and fall back to:
  - `POST /admin/auth/login`
  - `POST /tenant/auth/login`
- Session helpers must seed namespaced localStorage keys instead of dragging UI
  captcha flows into every smoke test:
  - `${namespace}_admin_token`
  - `${namespace}_admin_refresh_token`
  - `${namespace}_tenant_admin_token`
  - `${namespace}_tenant_admin_refresh_token`
- Preferred local env for smoke:
  - `DEV_ADMIN_BOOTSTRAP_SECRET`
  - `DEV_TENANT_BOOTSTRAP_SECRET`
- Fallback env for tenant smoke:
  - `TENANT_ADMIN_USERNAME`
  - `TENANT_ADMIN_PASSWORD`
  - `TENANT_ADMIN_TENANT_CODE`
- Fallback env for admin smoke:
  - `ADMIN_USERNAME` / `PLATFORM_ADMIN_USERNAME`
  - `ADMIN_PASSWORD` / `PLATFORM_ADMIN_PASSWORD`
- Identity smoke assertions should target stable page anchors plus
  `.identity-display`, `.member-panel`, `.monitoring-grid`, or `.vxe-table`
  instead of brittle label internals.

### 4. Validation & Error Matrix

| Condition                                      | Expected Behavior                                                          |
| ---------------------------------------------- | -------------------------------------------------------------------------- |
| Valid dev bootstrap secret                     | Matching smoke suite passes with API-seeded session and no manual login UI |
| Valid admin credentials                        | Admin dashboard / profile smoke passes with API-seeded session             |
| Valid tenant credentials + tenant code         | Tenant dashboard / profile / organization / logs smoke passes              |
| Missing tenant code                            | Tenant smoke skips instead of hanging on login UI                          |
| Tenant domain env absent                       | Suite still runs against localhost                                         |
| Page text shifts from “最近活动” to “近期活动” | Spec should assert the real page anchor, not an outdated copy guess        |

### 5. Good/Base/Bad Cases

- Good: seed auth once in `beforeEach`, navigate directly to the protected page,
  and assert `.identity-display` plus the page's real business anchor.
- Good: when a page is part of release-risk regression, land or update a spec in
  `frontend/apps/web-antd/__tests__/e2e/` and use its Playwright result as the
  verification record.
- Base: tenant smoke stays on localhost and provides `tenantCode` only to the
  backend login API.
- Bad: use drag-slider captcha automation in every browser test, then treat
  intermittent login failures as page regressions.
- Bad: use MCP browser interactions as the only proof that a page flow works
  when the same flow should be captured by a stable Playwright spec.

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
- Stop at MCP browser exploration for `frontend/apps/web-antd` page acceptance
  and skip adding/running the matching Playwright spec.

#### Correct

- Use backend login APIs to create tokens and seed the namespaced browser
  session before `page.goto(...)`.
- Assert the shared identity container and the page's real visible anchor text /
  table shell.
- Treat MCP browser tools as debugging aids, while the checked-in Playwright
  spec remains the primary regression and acceptance path.

## Code Review Checklist

Before merge, confirm:

- The page uses an existing platform pattern if one exists.
- The changed modules still respect high cohesion and low coupling; no new
  cross-surface dependency or oversized "shared" abstraction was introduced.
- Any oversized SFC or TS module was split by responsibility boundary, not by
  arbitrary chunking.
- Text, permissions, menu ownership, and route ownership are correct.
- Custom buttons, dropdown items, `CellOperation` custom codes, and
  `CellSwitch` toggles are not relying on backend `403` as the only guard.
- Upload/download/image behavior uses the attachment helpers.
- API transforms and types stay in the API/types layers.
- Unit tests and browser validation match the real risk of the change.
