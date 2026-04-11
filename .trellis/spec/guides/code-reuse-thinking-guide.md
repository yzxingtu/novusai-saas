# Code Reuse Thinking Guide

> Pain-free reuse keeps NovusAI *consistent* across admin, tenant, and user
> surfaces, and across backend/AI/frontend/plugin layers.

---

## The Why

Duplicating logic across layers breaks behavior parity, hides bugs, and
frustrates operators who expect the same `trace_id`, menu, upload/download,
and AI contracts everywhere.

## Core Principle: High Cohesion, Low Coupling

Treat reuse as an architectural tool, not just a way to save lines of code.
Every new page, composable, controller, service, repository, runtime helper,
or plugin integration should stay **highly cohesive** and **loosely coupled**.

- High cohesion: one module should have one dominant responsibility and one
  primary reason to change. If a file is mixing page rendering, API
  transformation, permission decisions, upload orchestration, and runtime
  wiring, split it along those boundaries.
- Low coupling: depend on stable contracts and shared helpers, not on another
  module's internal details. If a controller needs repository query details, a
  page needs another surface's store internals, or a shared helper needs page-
  specific flags to work, the boundary is already drifting.

Practical rule:

- keep transport concerns in controller/API modules
- keep business policy and orchestration in services/composables built for that
  purpose
- keep persistence/query behavior in repositories/models
- keep view-specific rendering and interaction state in the page/component
  layer
- keep cross-surface reuse behind narrow shared helpers instead of copy-pasted
  logic or sideways imports
- keep oversized governance modules on `thin facade + focused parts`; never add
  a new miscellaneous toolbox to avoid proper boundary extraction
- plugin/runtime governance can use `facade + mixin/parts` where mixins encode
  stable concern slices and orchestrator parts own execution choreography
- once a facade becomes the stable reuse seam, protect it as the compatibility
  surface and add new behavior in the focused parts instead of inflating the
  facade again

Warning signs that cohesion/coupling is drifting:

- one file changes whenever two unrelated features change
- callers must know hidden implementation details to use a helper correctly
- the same transform/guard/constant is duplicated across layers or surfaces
- a shared helper keeps growing feature switches for unrelated use cases
- a higher layer bypasses its normal dependency and reaches into a lower
  layer's internals
- a page/component starts acting as a business general manager coordinating
  multiple unrelated workflows

Default large-file remedy:

- backend: keep the public facade file, move cohesive logic into sibling modules
  or a package
- frontend page: keep the route shell, move state/process logic into composables
  and heavy visual subsections into section components
- shared layers: split by capability family, not by "misc/common/utils"
- thin facades are a valid end state; the goal is responsibility clarity, not
  to keep recursively splitting already-thin compatibility shells

Recommended governance seams:

- plugin platform backend:
  lifecycle orchestration, registry/read model, cleanup/runtime sync, and
  transport adapter should be independent seams
  - landed reference: `lifecycle.py(443)` facade + `lifecycle_orchestrator.py(987)` parts
- codegen backend:
  config/read model management, generator core, migration hook, and CLI/API
  transport should be independent seams
- codegen/plugin frontend:
  page shell, feature composables, and section components split by user-facing
  workflow (builder, history, preview, import/export, plugin drawer sections)

We already ship shared helpers for:

- CRUD pages (`useCrudPage`, `useCrudList`, `useCrudDrawer`, `useCrudForm`)
- Attachments (`smartUploadFile`, `requestClient.download`, `downloadBlob`,
  `getAttachmentUrl`, image helpers)
- Error/data transforms (`showRequestError`, `getErrorMessage`,
  `transformAttachmentInfo`)
- Backend tenants (`TenantController`, `TenantService`, `TenantRepository`)
- Responses (`success()`, `error()`, `build_error_payload()`)
- UI Runtime/page operation extensions (`use-ai-operations`, `use-ui-action-channel`, protocol-aligned page metadata, etc.)

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
4. If reuse would force unrelated callers to depend on page-specific or
   feature-specific behavior, stop and split the abstraction instead of making
   the shared helper broader and more coupled.

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
  ↔ camelCase mapping and CRUD callbacks.
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

### Plugin + UI Runtime Helpers

- Extend UI behavior through shared runtime helpers such as
  `use-ai-operations.ts` and `use-ui-action-channel.ts`, not through legacy
  `ai.extra` / page-level registration fallback.
- Keep page context payloads thin and serializable, and use `ui_get_snapshot`
  plus `ui_read_*` for on-demand detail reads.
- Reuse `use-ui-action-channel.ts` for `ui_*` action handling and avoid
  reintroducing `page_operation_*` style bridge channels.
- Register plugin menus/routes via the shared plugin helper stack to keep
  permission and runtime gating consistent.

Examples & anti-pattern:

- `frontend/apps/web-antd/src/views/admin/ai/agents/index.vue`
- `frontend/apps/web-antd/src/composables/use-ai-operations.ts`
- Anti-pattern: manually wiring ad-hoc runtime action pipelines, legacy bridge
  channels, or plugin runtime gating.

---

## Post-Change Checklist

- Confirm no existing helper or composable already covers the new feature.
- Confirm each new or expanded module still has one dominant responsibility.
- Confirm dependencies point through the intended contract/helper instead of a
  peer module's internal implementation.
- Confirm shared helpers expose a narrow API and do not require feature-local
  knowledge from every caller.
- Document the reuse path in these specs so future contributors know which
  helper to consult.
- Add targeted unit tests (see `frontend/apps/web-antd/src/composables/__tests__/`).
- Update Trellis specs instead of relying on private chat after adding helpers.

## Anti-Patterns Recap

- Copying another surface’s CRUD scaffolding instead of using `useCrudPage` or
  `useCrudList`.
- Growing a "shared" helper that now mixes unrelated workflows just to avoid
  creating a second focused abstraction.
- Reaching across layers or surfaces to import internals instead of extending
  the supported contract.
- Keeping one page/controller/CLI entry as a "business manager" and only
  slicing by line count without responsibility boundaries.
- Rebuilding attachment/upload logic outside the helper API.
- Reimplementing plugin or AI registration instead of using shared helpers.
