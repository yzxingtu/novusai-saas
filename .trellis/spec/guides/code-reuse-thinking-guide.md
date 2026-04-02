# Code Reuse Thinking Guide

> Pain-free reuse keeps NovusAI *consistent* across admin, tenant, and user
> surfaces, and across backend/AI/frontend/plugin layers.

---

## The Why

Duplicating logic across layers breaks behavior parity, hides bugs, and
frustrates operators who expect the same `trace_id`, menu, upload/download,
and AI contracts everywhere.

We already ship shared helpers for:

- CRUD pages (`useCrudPage`, `useCrudList`, `useCrudDrawer`, `useCrudForm`)
- Attachments (`smartUploadFile`, `requestClient.download`, `downloadBlob`,
  `getAttachmentUrl`, image helpers)
- Error/data transforms (`showRequestError`, `getErrorMessage`,
  `transformAttachmentInfo`)
- Backend tenants (`TenantController`, `TenantService`, `TenantRepository`)
- Responses (`success()`, `error()`, `build_error_payload()`)
- Plugin/page-AI extensions (`appendPageOperations`, `createPrefilledCreatePageOperation`, etc.)

Examples:

- Table CRUD page: `frontend/apps/web-antd/src/views/admin/system/attachments/index.vue`
- Card/grid CRUD page + AI extras:
  `frontend/apps/web-antd/src/views/admin/ai/agents/index.vue`
- Attachment API helpers:
  `frontend/apps/web-antd/src/api/admin/attachment.ts`
- Shared CRUD composables:
  `frontend/apps/web-antd/src/composables/use-crud-list.ts`,
  `frontend/apps/web-antd/src/composables/use-crud-form.ts`, and
  `frontend/apps/web-antd/src/composables/use-ai-operations.ts`
- Tenant stack sample: `backend/app/api/tenant/domains.py` → `TenantService` →
  `TenantRepository` → `success()`

---

## Before Writing New Logic

1. Search the existing helpers (composables, API modules, CRUD adapters).
2. Confirm whether the surface already uses a helper (table/list/upload/error)
   and whether you can extend it with props/options.
3. Stick to the established flows so that the rest of the stack continues to
   rely on one canonical contract.

Reuse wins when:

- A feature touches `admin`, `tenant`, `user`, or plugin scaffolding at the
  same time.
- Multiple pages/components would otherwise duplicate the same API
  transformation.
- The platform already exposes a generic builder for that contract.

Don't abstract when:

- Only one page needs the logic.
- A helper would become more complex than the bespoke implementation.

---

## High-Impact Helpers

### CRUD Infrastructure

- Use `useCrudPage` or `useCrudList` whenever you need tabular or card-based
  CRUD with search, pagination, actions, recycle bin, and AI operations.
- Use `useCrudForm`/`useCrudDrawer` so the form automatically handles snake_case
  ↔ camelCase mapping, AI page keys, and CRUD callbacks.
- Reuse `#/adapter/form` schema helpers instead of hand-writing repetitive
  search/form schema objects.
- Reuse scope helpers such as `useScopeFields()`, `getScopeOptions()`, and
  `ScopeSelect` instead of cloning scope option logic per page.

Examples & anti-pattern:

- `frontend/apps/web-antd/src/views/admin/system/attachments/index.vue`
- `frontend/apps/web-antd/src/views/admin/ai/agents/index.vue`
- Anti-pattern: copy-pasting table/render logic from another surface instead of
  reusing `useCrudPage` or `useCrudList`.

### Attachment Pipeline

- Always use `smartUploadFile`, `FilePicker`, `ImageUpload`, or shared helpers
  if you are uploading attachments.
- Always call `requestClient.download()` plus `downloadBlob()` for downloads.
- Use `getAttachmentUrl()`/`toAttachmentImageUrl()` for preview URLs or thumbnails.
- Normalize API payloads via `transformAttachmentInfo()` in the attachment API
  modules; do not re-map snake_case in each page.

Examples & anti-pattern:

- `frontend/apps/web-antd/src/api/admin/attachment.ts`
- `frontend/apps/web-antd/src/components/business/file-picker/FilePicker.vue`
- Anti-pattern: manually building `FormData` or using `window.open()` for exports.

### Error/Permission Contracts

- Let `requestClient` and `showRequestError()` own the toast so you avoid
  duplicate notifications.
- Use `v-access` or shared access helpers with permission codes from plugins.
- Plugin menu titles must come from plugin manifests; host menus come from
  backend `menu.json`.

Examples & anti-pattern:

- `frontend/apps/web-antd/src/utils/error-helpers.ts`
- `frontend/apps/web-antd/src/directives/access.ts`
- `.cursor/rules/menu-i18n.md`
- Anti-pattern: frontends re-implementing translation logic or showing two
  toasts for one failure.

### Tenant/Backend Layer

- Follow the `TenantController -> TenantService -> TenantRepository` chain.
- Let controllers call `success()`, `error()`, or `build_error_payload()` so the
  API contract stays consistent.
- Use repository metadata for filtering/sorting and avoid duplicating query
  logic in services.

Examples & anti-pattern:

- `backend/app/api/tenant/domains.py`
- `backend/app/services/system/tenant_domain_service.py`
- `backend/app/repositories/tenant/tenant_domain_tenant_repository.py`
- Anti-pattern: copying repository code into services or controllers.

### Plugin + Page AI Helpers

- Register AI operations with the shared page AI helpers:
  `appendPageOperations`, `registerPageContext`, `buildPageAIFormExtraData`.
- Register plugin menus/routes via the shared plugin helper stack to keep
  permission and runtime gating consistent.

Examples & anti-pattern:

- `frontend/apps/web-antd/src/views/admin/ai/agents/index.vue`
- `frontend/apps/web-antd/src/composables/use-ai-operations.ts`
- Anti-pattern: manually wiring AI page operations or plugin runtime gating.

---

## Post-Change Checklist

- Confirm no existing helper or composable already covers the new feature.
- Document the reuse path in these specs so future contributors know which
  helper to consult.
- Add targeted unit tests (see `frontend/apps/web-antd/src/composables/__tests__/`).
- Update Trellis specs instead of relying on private chat after adding helpers.

## Anti-Patterns Recap

- Copying another surface’s CRUD scaffolding instead of using `useCrudPage` or
  `useCrudList`.
- Rebuilding attachment/upload logic outside the helper API.
- Reimplementing plugin or AI registration instead of using shared helpers.
