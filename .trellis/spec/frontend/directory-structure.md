# Directory Structure

> How frontend code is organized in `frontend/apps/web-antd/src`.

## Overview

The frontend separates code by responsibility and by surface. `admin`,
`tenant`, and `user` must stay isolated in business code, while shared
composables and utilities live in common layers.

## Actual Directory Layout

```text
frontend/apps/web-antd/src/
|-- api/            # Endpoint-specific API wrappers (admin/tenant/user/shared/public)
|-- components/     # Reusable UI and business components
|-- composables/    # Renderless logic hooks and page AI helpers
|-- constants/      # Shared constants
|-- core/           # Vben adapter/framework glue
|-- directives/     # Custom directives such as v-access
|-- features/       # Cross-cutting feature packages used by pages
|-- layouts/        # Surface layouts (basic, auth, user, iframe)
|-- locales/        # Frontend i18n bundles
|-- router/         # Route modules, guards, and access bootstrap
|-- store/          # Pinia stores grouped by admin/shared/tenant/user
|-- stores/         # Infra/plugin runtime stores
|-- types/          # Shared TS types
|-- utils/          # Pure utilities and request helpers
|-- views/          # Route-level pages split by admin/tenant/user/public
```

## Dependency Direction

Follow the existing dependency flow:

```text
views -> composables -> store/api -> utils
views -> adapter/vxe-table -> api
router/access -> api/menu -> access store
```

Do not invert it. In particular:

- `api/` must not depend on `views/`
- `utils/` should stay as low-level helpers
- generic adapter/composable code must not depend on concrete business pages

## Surface Separation Rules

- `views/admin/**` should only use admin/shared APIs and stores.
- `views/tenant/**` should only use tenant/shared APIs and stores.
- `views/user/**` should only use user/shared APIs and stores.
- Shared logic belongs in `components/`, `composables/`, `utils/`, `api/shared`,
  or `store/shared` when it is genuinely cross-surface.

Examples:

- Admin table page:
  `frontend/apps/web-antd/src/views/admin/system/attachments/index.vue`
- Tenant page:
  `frontend/apps/web-antd/src/views/tenant/ai/agents/index.vue`
- User routes:
  `frontend/apps/web-antd/src/router/routes/user/index.ts`

## Where New Code Should Go

### Route pages

- Put route-level pages under `views/{surface}/...`.
- Keep route files close to their page-specific `data.ts`, modules, and related
  form/detail components.
- User-facing route trees keep the `UserLayout` contract and the stable `/`,
  `/agents`, `/ai-chat`, `/help`, and `/settings/*` conventions.

Examples:

- `frontend/apps/web-antd/src/views/admin/system/attachments/`
- `frontend/apps/web-antd/src/views/admin/ai/agents/`

### API wrappers

- Put endpoint wrappers under `api/{surface}/`.
- Shared cross-surface wrappers can live in `api/shared/` or `api/public/`.
- API modules are the right place for backend snake_case to frontend camelCase
  transforms.

Examples:

- `frontend/apps/web-antd/src/api/admin/attachment.ts`
- `frontend/apps/web-antd/src/api/tenant/attachment.ts`
- `frontend/apps/web-antd/src/api/user/attachment.ts`

### State

- Put business stores in `store/{admin|shared|tenant|user}/`.
- Put plugin/runtime infra stores in `stores/`.
- Prefer shared stores only when the state is truly shared across surfaces.
- Domain/public-config/auth state should stay in shared stores rather than being
  reimplemented per page.

Examples:

- `frontend/apps/web-antd/src/store/shared/public-config.ts`
- `frontend/apps/web-antd/src/store/shared/multi-auth.ts`
- `frontend/apps/web-antd/src/stores/plugin-slots.ts`

### Composables

- Put renderless page logic in `composables/`.
- Reuse the CRUD/page AI infrastructure before inventing a new pattern.

Examples:

- `frontend/apps/web-antd/src/composables/use-crud-list.ts`
- `frontend/apps/web-antd/src/composables/use-crud-form.ts`
- `frontend/apps/web-antd/src/composables/use-detail-page-ai.ts`

## Naming Conventions

- Vue route pages commonly use `index.vue`.
- Reusable modules under a page can use PascalCase component files.
- Composables use `use-*.ts` or `use*.ts` based on existing naming in the
  folder; prefer following the immediate local pattern.
- API files use domain/resource names such as `attachment.ts`,
  `codegen.ts`, `system-log.ts`.

## Examples Of Good Structure

- Table CRUD with colocated page helpers:
  `frontend/apps/web-antd/src/views/admin/system/attachments/`
- Card/list CRUD with modules and operations:
  `frontend/apps/web-antd/src/views/admin/ai/agents/`
- User layout and user route separation:
  `frontend/apps/web-antd/src/layouts/user.vue`
  `frontend/apps/web-antd/src/router/routes/user/index.ts`

## Anti-Patterns

- Importing `tenant` business modules into `admin` pages or the reverse.
- Putting API transform logic directly into Vue pages.
- Creating a new "shared" directory for code that is only reused once.
- Storing plugin runtime state in business stores under `store/`.
