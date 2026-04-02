# State Management

> Pinia is the primary application state mechanism, with additional state held
> in route params, composables, and Vben framework stores.

## Overview

The repo currently uses:

- `store/` for business stores grouped by `admin`, `shared`, `tenant`, and
  `user`
- `stores/` for plugin/runtime infrastructure stores
- Vben access/auth stores for framework-level permissions and tokens
- composable-local refs/computed values for page-local state

Examples:

- Shared public config store:
  `frontend/apps/web-antd/src/store/shared/public-config.ts`
- Shared auth store:
  `frontend/apps/web-antd/src/store/shared/multi-auth.ts`
- Plugin runtime store:
  `frontend/apps/web-antd/src/stores/plugin-slots.ts`

## State Categories

### Local page state

- Keep search text, drawer visibility, selection, and temporary UI state in the
  page or composable unless another surface truly needs it.

Examples:

- `frontend/apps/web-antd/src/views/admin/system/attachments/index.vue`
- `frontend/apps/web-antd/src/views/admin/ai/agents/index.vue`

### Shared business state

- Use Pinia under `store/shared` for cross-page state such as public config,
  multi-auth, notifications, socket presence, or user preferences.

Examples:

- `frontend/apps/web-antd/src/store/shared/public-config.ts`
- `frontend/apps/web-antd/src/store/shared/multi-auth.ts`
- `frontend/apps/web-antd/src/store/shared/notification.ts`

### Framework/runtime state

- Use Vben access stores for tokens, menus, and access codes.
- Use `stores/` for plugin runtime state rather than mixing it into business
  stores.

Examples:

- `frontend/apps/web-antd/src/directives/access.ts`
- `frontend/apps/web-antd/src/stores/plugin-extensions.ts`

## When To Use Global State

Promote state to a store only when:

- multiple routes/layouts need it
- it survives navigation
- it coordinates domain/auth/plugin/runtime behavior
- it is a true application-level preference or capability state

Do not create global state for one page's temporary UI concerns.

## Domain And Public Config Rules

- Domain detection and public config loading should go through
  `usePublicConfigStore`.
- Do not build a second source of truth for tenant-vs-platform domain logic in
  route pages.
- Tenant public config should only load after domain detection says the host is
  tenant-facing.
- User auth pages reuse shared `/auth/*`; do not create a second user-only auth
  routing system.
- Platform domains must not behave like tenant domains by path guesswork alone.

### User-Surface And Domain Isolation Rules

- User pages must use `UserLayout`, not `BasicLayout` or tenant/admin layouts.
- User routes live in `frontend/apps/web-antd/src/router/routes/user/index.ts`
  and keep the stable `/`, `/agents`, `/ai-chat`, `/help`, and `/settings/*`
  structure, with `/home` only as a compatibility alias.
- Domain gating is enforced by the route guard and public-config store, so do
  not prefetch tenant public config on platform domains.
- Platform domains cannot infer tenant behavior from URL path alone; host/domain
  detection stays authoritative.

Examples:

- `frontend/apps/web-antd/src/store/shared/public-config.ts`
- `frontend/apps/web-antd/src/router/guard.ts`
- `frontend/apps/web-antd/src/router/routes/root.ts`
- `frontend/apps/web-antd/src/router/routes/user/index.ts`
- `frontend/apps/web-antd/src/layouts/user.vue`

## Server State

- API modules are the source for server state shape.
- Composables and pages fetch and transform server state through those API
  wrappers.
- Do not stash raw duplicated API payloads in global state unless there is a
  strong cross-page need.

## Common Mistakes

- Duplicating domain detection or branding logic outside
  `usePublicConfigStore`.
- Storing plugin runtime state in ordinary business stores.
- Treating local browser storage as the final truth for permissions or trust.
- Promoting page-only state to Pinia too early.
- Loading tenant public config on platform domains before domain detection is
  complete.
