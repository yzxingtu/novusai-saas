# Cross-Layer Thinking Guide

> Use this guide whenever a task touches two or more of the following pillars:
> backend API, database/migrations, frontend pages/composables, AI agents/skills,
> plugins, attachments/uploads, domain/permissions, and trace/monitoring.

## Step 1: Map the Data Flow

Trace the full path from the initial input to the final UI/ML experience:

```
Client/Agent → Frontend composable (useCrudList/useCrudPage) → API wrapper →
Controller (TenantController/GlobalController) → Service → Repository →
Model → Migration (if schema changed)
             ↓
             Celery task/AI agent → plugins, uploads, trace logging
```

Key references:

- Frontend CRUD page pattern: `frontend/apps/web-antd/src/views/admin/system/attachments/index.vue`
- API adapter and download helpers: `frontend/apps/web-antd/src/api/admin/attachment.ts`
- Controller/service/repository chain: `backend/app/api/tenant/domains.py`, `backend/app/services/system/tenant_domain_service.py`, `backend/app/repositories/tenant/tenant_domain_tenant_repository.py`, `backend/app/models/tenant/tenant_domain.py`
- Trace middleware/logging: `backend/app/middleware/trace.py`, `backend/app/core/logging.py`
- Attachment + storage rules: `.cursor/rules/attachments-and-storage.md`
- Plugin system rules: `.cursor/rules/plugin-system.md`
- Domain/permissions rules: `.cursor/rules/tenant-architecture.md`, `.cursor/rules/rbac-and-data-permission.md`, `.cursor/rules/menu-i18n.md`
- AI contract rules: `.cursor/rules/ai-architecture.md`, `.cursor/rules/async-notification-websocket.md`

## Step 2: Identify Boundary Contracts

For each layer pair, answer:

- **AI chain truth**: Does the feature keep the runtime chain as
  `Agent -> Skill -> AIGateway`? Do not let controllers/services call gateway
  chat or embedding methods directly. Runtime capability truth is
  `AgentSkillGrant`, not package visibility alone. Do not revive deprecated
  `ToolRegistry` or `tool_bindings` style paths.
- **Frontend ↔ API**: Does the page use `useCrudPage`/`useCrudList` for schema-driven search/form config? Does it rely on attachments or downloads (smartUploadFile + requestClient.download)? Reference `frontend/apps/web-antd/src/composables/use-crud-list.ts`, `frontend/apps/web-antd/src/api/admin/attachment.ts`.
- **API ↔ Service**: Do controllers only delegate to services (TenantController/GlobalController pattern)? Do services honor RBAC (`@permission_resource`, `@permission_action`) and logging conventions (`get_logger`, success wrappers)? See `backend/app/core/base_controller.py`, `.cursor/rules/rbac-and-data-permission.md`.
- **Service ↔ Repository/Model**: Are queries centralized in repositories with tenant filters? Do models expose `__filterable__`, `__sortable__`, and specify `__delete_deps__` when needed? See `backend/app/repositories/tenant/tenant_domain_tenant_repository.py`, `backend/app/models/tenant/tenant_domain.py`.
- **RBAC/Data permission truth**: Is access control staying in the established
  backend mechanisms? Controllers need `@permission_resource(..., parent_resource=...)`;
  row-level filtering should rely on `__data_permission__`, `data_permission_ctx`,
  creator/org/dept autofill, and parent-model inheritance through the base
  repository/data-permission pipeline rather than service-level custom SQL.
- **Service ↔ Migrations**: Do migrations stay idempotent, register in `backend/migrations/env.py`, and avoid f-string SQL? Reference `.cursor/rules/alembic-migration-authoring.md`, `backend/migrations/env.py`.
- **Backend ↔ AI/Tasks**: Does async behavior use `@register_task` in `backend/app/tasks/ai.py`? Are trace ids preserved when enqueuing/consuming? See `backend/app/tasks/base.py`, `.cursor/rules/trace-and-monitoring.md`.
- **Uploads/Attachments ↔ Frontend**: Are uploads routed through `smartUploadFile` and attachments stored via `AttachmentService`? Is `public` vs `private` treated as part of attachment identity and dedupe scope? Do platform uploads preserve `tenant_id=0`? Are display images using shared image endpoints and private previews using signed access/preview URLs? See `.cursor/rules/attachments-and-storage.md`, `backend/app/services/tenant/attachment_service.py`, `frontend/apps/web-antd/src/components/business/file-picker/FilePicker.vue`.
- **Plugins ↔ Backend**: Does plugin UI rely on `plugin.yaml` as the only declaration source? Are `endpoint` and `publicEndpoint` used exclusively and correctly, assets split strictly between `/plugin-assets/...` and `/plugin-public-assets/...`, loader cache keys tied to runtime signature, and menu/page/runtime gates treated as separate fail-closed checks? Check `.cursor/rules/plugin-system.md`, `frontend/apps/web-antd/src/stores/plugin-slots.ts`.
- **Plugins ↔ Permissions**: If plugin permissions changed, does the flow still
  use `sync_plugin_permissions(plugin.name)` and keep menu/page/runtime gating
  aligned?
- **Domain/Permissions ↔ Frontend**: Are domains resolved via `detectDomainType()` and public config store? Are user pages under `UserLayout` with `/api/user/*` and shared `/auth/*` contracts intact? See `.cursor/rules/user-endpoint-and-domain-isolation.md`, `frontend/apps/web-antd/src/store/shared/public-config.ts`.
- **Tenant product boundary**: If the work touches tenant AI, recycle bin, or
  capability exposure, does it keep the intended product boundary intact? Tenant
  surfaces may consume platform-provided capabilities and read catalog data, but
  they must not silently gain platform-only CRUD or the admin total recycle bin.
- **Trace/Monitoring**: Do errors/logs include trace_id and use `novusai trace show` instrumentation? See `.cursor/rules/trace-and-monitoring.md`, `backend/app/tasks/ai.py`.

### Frontend Page-AI Priority Order

When the work involves page AI or page operations, check whether the page fits
an existing entry point before adding low-level wiring:

1. `useCrudPage`
2. `useCrudList`
3. `useDetailPageAi`
4. lower-level page AI composables only when the page cannot fit the standard
   patterns

## Step 3: Validate Contracts Before Coding

Checklist:

1. Have you documented the input/output shape for each boundary (frontend props, API payload, service contract, repository query, model migration)?
2. Did you confirm attachment/upload flows reuse smartUploadFile and `AttachmentService`?
3. Did you capture the RBAC/data-permission requirements (`@permission_resource`,
   `parent_resource`, `messages.json`, `v-access`, repository/base-layer data
   filters)?
4. Did you capture trace_id expectations (middleware, logs, Celery tasks,
   frontend notifications, `novusai trace show`)?
5. Did you note any plugin/public config requirements (manifest titles,
   asset path split, runtime gate, `publicConfigStore`, `detectDomainType`)?
6. If tenant/user surfaces are involved, did you verify the product boundary:
   tenant-side capability limits, user layout/auth routing, and no platform
   domain prefetch of tenant public config?
7. If tenant AI/package flows are involved, did you keep tenant package views as
   catalog/read-only surfaces rather than runtime authority or package-binding
   truth?

If the answer is no, stop and gather the missing contract before coding.

## Step 4: Post-Change Confirmation

- Run relevant backend/ frontend lint + tests (`pytest`, `ruff check`, `pnpm test:unit`).
- Verify trace_id surfaces via `showRequestError` or backend `build_public_error_text`.
- If uploads/files changed, ensure downloads still call `requestClient.download` + `downloadBlob`.
- If plugins or permissions changed, confirm `/permissions/menus`, `/plugins/slots`, and `v-access` flows match the manifest contract.
- If AI agents changed, ensure page AI operations still register with `appendPageOperations` and share `AI_PAGE_KEY`.
- If quota/rate-limit behavior changed, confirm runtime interception behavior,
  not only CRUD or diagnostics UI.
- If tenant/user routing changed, confirm `router/guard.ts` and
  `store/shared/public-config.ts` still enforce domain isolation.

## Anti-Patterns

- Copying logic into another layer without updating the upstream contract or spec.
- Adding uploads/downloads outside the attachment helpers and storage services.
- Letting trace_id vanish between backend logs and frontend error toasts.
- Duplicating menu/item titles between plugin manifests and frontend translations.
- Skipping repository metadata (`__filterable__`, `__sortable__`, `__selectable__`) when exposing new list filters or sorts.
- Building service-level org filters instead of using the repository/data-permission
  pipeline.
- Treating plugin page visibility as proof that runtime gate, asset scope, and
  permission bridge are all correct.
