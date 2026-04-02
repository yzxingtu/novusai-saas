# Component Guidelines

> How Vue pages and components are built in NovusAI SaaS.

## Overview

Most route pages use `<script setup lang="ts">`, `defineOptions({ name: ... })`,
Vben `Page`, and Ant Design Vue building blocks. The repo strongly prefers
declarative CRUD and shared business components over bespoke page wiring.

## Component Structure

Preferred structure for route pages:

1. `script setup` imports and local helpers
2. `defineOptions({ name: ... })`
3. declarative CRUD/composable setup
4. template using shared layout and business components

Representative examples:

- Table CRUD page:
  `frontend/apps/web-antd/src/views/admin/system/attachments/index.vue`
- Card/list CRUD page:
  `frontend/apps/web-antd/src/views/admin/ai/agents/index.vue`
- User layout component:
  `frontend/apps/web-antd/src/layouts/user.vue`

## Page Pattern Selection

- Use `useCrudPage` for data-dense list/table pages.
- Use `useCrudList` for card grids, split panels, configuration boards, and
  pages that need custom rendering but standard list/search/pagination behavior.
- Prefer schema-driven form/search helpers from `#/adapter/form` over manually
  assembled repetitive schemas.
- Use shared business components and Vben drawers/modals instead of rebuilding
  list/detail scaffolding.

Examples:

- `frontend/apps/web-antd/src/views/admin/system/attachments/index.vue`
- `frontend/apps/web-antd/src/views/admin/ai/agents/index.vue`
- `frontend/apps/web-antd/src/composables/use-crud-list.ts`

## Props And Inputs

- Type props explicitly with TypeScript.
- Prefer stable ids, codes, and typed records rather than passing large
  anonymous objects through many layers.
- For CRUD forms, prefer field-driven configuration and shared helpers rather
  than handcrafted repetitive schemas.
- When a page uses `useCrudDrawer` / `useCrudForm`, let the shared field-mapping
  behavior handle snake_case <-> camelCase transforms.
- Scope-related form fields should reuse the established helpers
  (`useScopeFields()`, `getScopeOptions()`, `ScopeSelect`) rather than cloning
  scope UI logic.
- Editability decisions should use `tenant_id` or `owner_tenant_id`, not infer
  behavior from `scope` alone.

Examples:

- `frontend/apps/web-antd/src/composables/use-crud-form.ts`
- `frontend/apps/web-antd/src/views/admin/ai/agents/modules/form.vue`

## Styling Patterns

- Use the existing Vben + Ant Design Vue visual language.
- Utility classes and existing theme tokens are common in route pages.
- Reuse shared helpers for images and attachments instead of hardcoding URLs.

Examples:

- Attachment image rendering:
  `frontend/apps/web-antd/src/views/admin/system/attachments/index.vue`
- Image helpers:
  `frontend/apps/web-antd/src/utils/image.ts`

## Permissions And I18n

- User-visible strings must use `$t()` or `t()`.
- Permission-gated actions must use `v-access` or shared access helpers.
- Permission codes follow `{resource}:{action}`.
- Use `v-access:code` for permission-code checks and `v-access:role` only when
  role-gated behavior is truly needed.
- Users with `*` access codes are super admins and should inherit all code-based
  checks through the shared directive/helpers.
- Host menu translations come from backend menu payloads, not frontend
  duplicates.
- Plugin menu titles come from `plugin.yaml`, not frontend `menu.*` keys.
- Locale-switch behavior should keep sidebar, breadcrumb, document title, and
  page heading aligned.
- Do not rely on online Iconify API behavior for platform functionality; follow
  the local icon pipeline already used in this repo.

Examples:

- `frontend/apps/web-antd/src/directives/access.ts`
- `frontend/apps/web-antd/src/views/admin/ai/agents/index.vue`
- `.cursor/rules/menu-i18n.md`

## Upload, Download, And Media Components

- Business uploads must go through `smartUploadFile`, `FilePicker`,
  `ImageUpload`, or wrappers built on top of them.
- Platform uploads must respect the existing `tenant_id=0` platform convention.
- Attachment visibility (`public` vs `private`) is part of the attachment
  identity and must not be treated as a cosmetic detail.
- Downloads must use `requestClient.download()` plus `downloadBlob()`.
- Images should use shared attachment/image helpers rather than manual URL
  concatenation.
- Display images should use the shared image endpoints/helpers; private preview
  paths must keep using the signed preview/access contract.
- Business code must not construct storage URLs, bucket paths, or preview URLs
  manually.

Examples:

- `frontend/apps/web-antd/src/api/admin/attachment.ts`
- `frontend/apps/web-antd/src/components/business/file-picker/FilePicker.vue`
- `frontend/apps/web-antd/src/components/business/image-upload/ImageUpload.vue`

## Accessibility And UX

- Use meaningful button text, tags, tooltips, and alt text when applicable.
- Keep disabled/hidden states permission-aware.
- Avoid duplicate error toasts for a single HTTP failure; let the request layer
  or the page own the error, but not both.
- If the page owns the HTTP error, disable the default request UI first with
  `showErrorMessage: false` and `showCodeMessage: false`, then call the shared
  error helper.
- Do not introduce unsanitized `v-html` rendering paths for user-controlled or
  backend-provided content.

## Common Mistakes

- Building a custom page shell instead of using the existing CRUD composables.
- Hardcoding text, permission logic, or menu-title ownership in the component.
- Calling `requestClient.upload()` or `window.open()` directly from business UI.
- Manually parsing attachment/image ids with unsafe casts.
- Treating plugin menu titles as ordinary frontend locale keys instead of
  manifest-owned metadata.
- Spreading legacy `200 + success=false` soft-failure handling into new APIs or
  pages.
