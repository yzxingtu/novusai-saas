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
- Plugin runtime rules: `.trellis/spec/guides/plugin-runtime-playbook.md`
- Domain/permissions rules: `.cursor/rules/tenant-architecture.md`, `.cursor/rules/rbac-and-data-permission.md`, `.cursor/rules/menu-i18n.md`
- AI contract rules: `.cursor/rules/ai-architecture.md`, `.cursor/rules/async-notification-websocket.md`

## Step 2: Identify Boundary Contracts

For each layer pair, answer:

- **AI chain truth**: Does the feature keep the runtime chain as
  `Agent -> Skill -> AIGateway`? Do not let controllers/services call gateway
  chat or embedding methods directly. Runtime capability truth is
  `AgentSkillGrant`, not package visibility alone. Do not revive deprecated
  `ToolRegistry` or `tool_bindings` style paths. Fixed LLM-facing prompt text
  (system blocks, router prompts, tool descriptions, retry guidance, UI runtime
  workflow guidance) must live in `backend/app/ai/prompt_contracts/resources/`,
  not inline in Python execution code.
- **Frontend ↔ API**: Does the page use `useCrudPage`/`useCrudList` for schema-driven search/form config? Does it rely on attachments or downloads (smartUploadFile + requestClient.download)? Reference `frontend/apps/web-antd/src/composables/use-crud-list.ts`, `frontend/apps/web-antd/src/api/admin/attachment.ts`.
- **API ↔ Service**: Do controllers only delegate to services (TenantController/GlobalController pattern)? Do services honor RBAC (`@permission_resource`, `@permission_action`) and logging conventions (`get_logger`, success wrappers)? See `backend/app/core/base_controller.py`, `.cursor/rules/rbac-and-data-permission.md`.
- **Controller boundary guard**: Does any touched `app/api/**` module introduce
  direct DB query assembly (`db.execute`, `session.execute`, inline `select`)?
  If yes, stop and move that logic to service/repository/query-service seams.
- **Service ↔ Repository/Model**: Are queries centralized in repositories with tenant filters? Do models expose `__filterable__`, `__sortable__`, and specify `__delete_deps__` when needed? See `backend/app/repositories/tenant/tenant_domain_tenant_repository.py`, `backend/app/models/tenant/tenant_domain.py`.
- **RBAC/Data permission truth**: Is access control staying in the established
  backend mechanisms? Controllers need `@permission_resource(..., parent_resource=...)`;
  row-level filtering should rely on `__data_permission__`, `data_permission_ctx`,
  creator/org/dept autofill, and parent-model inheritance through the base
  repository/data-permission pipeline rather than service-level custom SQL.
- **Service ↔ Migrations**: Do migrations stay idempotent, register in `backend/migrations/env.py`, and avoid f-string SQL? Reference `.cursor/rules/alembic-migration-authoring.md`, `backend/migrations/env.py`.
- **Backend ↔ AI/Tasks**: Does async behavior use `@register_task` in `backend/app/tasks/ai.py`? Are trace ids preserved when enqueuing/consuming? See `backend/app/tasks/base.py`, `.cursor/rules/trace-and-monitoring.md`.
- **Uploads/Attachments ↔ Frontend**: Are uploads routed through `smartUploadFile` and attachments stored via `AttachmentService`? Is `public` vs `private` treated as part of attachment identity and dedupe scope? Do platform uploads preserve `tenant_id=0`? Are display images using shared image endpoints and private previews using signed access/preview URLs? See `.cursor/rules/attachments-and-storage.md`, `backend/app/services/tenant/attachment_service.py`, `frontend/apps/web-antd/src/components/business/file-picker/FilePicker.vue`.
- **Plugins ↔ Backend**: Does plugin UI rely on `plugin.yaml` as the only declaration source? Are `endpoint` and `publicEndpoint` used exclusively and correctly, assets split strictly between `/plugin-assets/...` and `/plugin-public-assets/...`, loader cache keys tied to runtime signature, and menu/page/runtime gates treated as separate fail-closed checks? Check `.trellis/spec/guides/plugin-runtime-playbook.md`, `frontend/apps/web-antd/src/stores/plugin-slots.ts`.
- **Plugins ↔ Permissions**: If plugin permissions changed, does the flow still
  use `sync_plugin_permissions(plugin.name)` and keep menu/page/runtime gating
  aligned?
- **Domain/Permissions ↔ Frontend**: Are domains resolved via `detectDomainType()` and public config store? Are user pages under `UserLayout` with `/api/user/*` and shared `/auth/*` contracts intact? See `.cursor/rules/user-endpoint-and-domain-isolation.md`, `frontend/apps/web-antd/src/store/shared/public-config.ts`.
- **Frontend boundary guard**: Is the page kept as shell + sections while heavy
  business orchestration lives in composables/shared helpers, rather than one
  SFC acting as a business manager?
- **Tenant product boundary**: If the work touches tenant AI, recycle bin, or
  capability exposure, does it keep the intended product boundary intact? Tenant
  surfaces may consume platform-provided capabilities and read catalog data, but
  they must not silently gain platform-only CRUD or the admin total recycle bin.
- **Trace/Monitoring**: Do errors/logs include trace_id and use `novusai trace show` instrumentation? See `.cursor/rules/trace-and-monitoring.md`, `backend/app/tasks/ai.py`.
- **CLI/runtime governance**: If CLI or ops scripts are touched, is public
  entrypoint kept thin with stable command names/options, and is heavy logic
  split into focused command/runtime modules?
- **Plugin lifecycle/runtime governance**: If plugin platform files are touched,
  is shape kept as `facade + mixin/parts` with compatibility preserved
  (reference: `lifecycle.py(432)` + `lifecycle_orchestrator.py(833)`)?
- **Governance test seam**: If package-level imports would drag unrelated
  out-of-scope modules into a route/controller test, can the test isolate the
  touched controller module directly while still validating the public transport
  contract?

### Frontend UI Runtime Priority Order

When the work involves page context, page operations, or UI runtime tools,
check whether the page fits an existing entry point before adding low-level
wiring:

1. `useCrudPage`
2. `useCrudList` (+ shared runtime helpers such as `use-ai-operations.ts` when
   the page needs protocol-aligned metadata or form/session hooks)
3. thin `page_context` + UI Runtime `ui_*` tools path for non-CRUD pages

### Dev-only Bootstrap Credential Contract

- Confirm the backend exposes `POST /admin/auth/dev/bootstrap` and
  `POST /tenant/auth/dev/bootstrap` only when `APP_ENV=development` and
  `DEV_BOOTSTRAP_AUTH_ENABLED=true` is set.
- The bootstrap path must refuse non-loopback/non-local-dev hosts
  (`localhost`, `127.0.0.1`, `::1`, `*.local`) and require developer-specific
  secrets defined only in that workstation's `backend/.env`:
  `DEV_ADMIN_BOOTSTRAP_SECRET`, `DEV_TENANT_BOOTSTRAP_SECRET`. Document
  placeholders in `.env.example` or guides.
- Backend-side env config, not request payloads, must choose the bootstrap
  identities: `DEV_ADMIN_BOOTSTRAP_USERNAME`,
  `DEV_TENANT_BOOTSTRAP_USERNAME`, and `DEV_TENANT_BOOTSTRAP_TENANT_CODE`.
- Bootstrap JWTs must expire within the normal session TTL and keep refresh
  enforcement active—forever tokens are forbidden.
- Playwright/local frontend helpers should prefer hitting this dev-only bootstrap
  endpoint when running on a developer workstation, but valid tests must still
  work through `/auth/login` whenever the flag is absent.
- For `frontend/apps/web-antd` page verification, the durable validation target
  should be a checked-in Playwright spec under `__tests__/e2e`; use MCP browser
  tooling for diagnosis and debugging, not as the default release gate.
- Track these requirements both in the backend and frontend quality guidelines so
  every layer understands the same expectations.

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
8. If controller files changed, did you explicitly confirm no new controller
   direct-query path was introduced?
9. If frontend page/component files changed, did you explicitly confirm the page
   is not acting as a cross-domain business orchestrator?
10. If CLI/platform governance files changed, did you confirm `thin facade +
    focused parts` with compatibility preserved?
11. If plugin lifecycle/runtime files changed, did you confirm
    `facade + mixin/parts` and avoid re-converging orchestration into one giant
    module?
12. If route-level regression tests were added for a split controller, did you
    keep the test isolated to the touched transport contract instead of relying
    on unrelated package import side effects?

If the answer is no, stop and gather the missing contract before coding.

## Step 4: Post-Change Confirmation

- Run relevant backend/ frontend lint + tests (`pytest`, `ruff check`, `pnpm test:unit`).
- Verify trace_id surfaces via `showRequestError` or backend `build_public_error_text`.
- If uploads/files changed, ensure downloads still call `requestClient.download` + `downloadBlob`.
- If plugins or permissions changed, confirm `/permissions/menus`, `/plugins/slots`, and `v-access` flows match the manifest contract.
- If AI agents changed, ensure frontend still exposes a thin `page_context`
  contract, `ui_*` runtime actions, and shared runtime helpers through
  `useCrudList`/`useCrudPage` without reviving legacy `ai.*` or `ai.extra`
  option bags.
- If quota/rate-limit behavior changed, confirm runtime interception behavior,
  not only CRUD or diagnostics UI.
- If tenant/user routing changed, confirm `router/guard.ts` and
  `store/shared/public-config.ts` still enforce domain isolation.

## Scenario: Frontend Dev Domain And Backend CORS Alignment

### 1. Scope / Trigger

- Trigger: changing the frontend dev host, backend API origin, platform-domain
  detection, or seeing browser errors such as
  `No 'Access-Control-Allow-Origin' header` on `/api/public/platform/config`.
- Trigger: changing plugin asset routes, Socket.IO origin handling, or image/API
  URLs that must stay aligned with the same backend origin.

### 2. Signatures

- Frontend env:
  - `frontend/apps/web-antd/.env.development`
  - `VITE_GLOB_API_URL`
  - `VITE_PLATFORM_DOMAINS`
- Frontend runtime:
  - `frontend/apps/web-antd/src/utils/api-url.ts`
  - `frontend/apps/web-antd/src/utils/request/instance.ts`
  - `frontend/apps/web-antd/src/store/shared/socketio.ts`
  - `frontend/apps/web-antd/src/utils/image.ts`
  - `frontend/apps/web-antd/vite.config.mts`
- Backend env:
  - `backend/.env`
  - `backend/.env.example`
  - `CORS_ORIGINS`
  - `PLATFORM_DOMAINS`
  - `TENANT_DOMAIN_SUFFIX`
- Backend runtime:
  - `backend/app/core/config.py`
  - `backend/app/core/cors.py`
  - `backend/app/middleware/dynamic_cors.py`

### 3. Contracts

- `VITE_GLOB_API_URL` is the frontend source of truth for the backend origin.
  Use an absolute origin such as `http://192.168.31.129:8000` when the browser
  must call the backend directly, or a relative path such as `/api` only when a
  reverse proxy is intentionally in front of both frontend and backend.
- Frontend dev runtime may rewrite the API hostname only when
  `VITE_GLOB_API_URL` points at a loopback host (`localhost`, `127.0.0.1`,
  `0.0.0.0`, `::1`). If the env already uses a non-loopback host such as
  `192.168.31.129`, the runtime must preserve that explicit host.
- `VITE_PLATFORM_DOMAINS` and backend `PLATFORM_DOMAINS` must both include the
  host that actually serves the admin frontend in development. Example: when the
  page is opened at `http://192.168.31.129:5666/admin`, both env keys must
  include `192.168.31.129`.
- `CORS_ORIGINS` must list exact frontend origins, including scheme and port.
  Valid examples:
  - `["http://localhost:5666","http://192.168.31.129:5666"]`
  - `http://localhost:5666,http://192.168.31.129:5666`
- `vite.config.mts` plugin asset proxies (`/plugin-assets`,
  `/plugin-public-assets`, `/plugin-icons`) must derive their backend target
  from `VITE_GLOB_API_URL` origin instead of hardcoding `http://127.0.0.1:8000`.
- If frontend uses a direct backend origin instead of `/api` proxying, backend
  CORS must be configured before expecting `/api/public/platform/config`,
  auth APIs, images, or Socket.IO handshakes to succeed from the browser.

### 4. Validation & Error Matrix

| Condition | Expected Behavior |
|---|---|
| Frontend opened from `http://localhost:5666`, backend is `http://127.0.0.1:8000`, domains include localhost | Requests succeed; loopback rewrite may normalize the hostname for dev convenience |
| Frontend opened from `http://192.168.31.129:5666`, backend is `http://192.168.31.129:8000`, exact origin present in `CORS_ORIGINS` | Browser preflight succeeds and backend reflects `Access-Control-Allow-Origin: http://192.168.31.129:5666` |
| Frontend uses LAN IP but backend CORS still allows only localhost | Browser blocks preflight with no `Access-Control-Allow-Origin` header |
| Platform host missing from `VITE_PLATFORM_DOMAINS` or `PLATFORM_DOMAINS` | Public-config/domain detection can misclassify the host and route/branding behavior becomes inconsistent |
| Plugin asset proxy still hardcodes `127.0.0.1:8000` while API origin changed | `/plugin-assets/*`, `/plugin-public-assets/*`, or `/plugin-icons/*` hit the wrong backend origin |

### 5. Good/Base/Bad Cases

- Good: browser visits `http://192.168.31.129:5666/admin`,
  `VITE_GLOB_API_URL=http://192.168.31.129:8000`,
  `VITE_PLATFORM_DOMAINS=localhost,127.0.0.1,192.168.31.129`,
  `PLATFORM_DOMAINS=localhost,127.0.0.1,192.168.31.129`, and
  `CORS_ORIGINS` includes `http://192.168.31.129:5666`.
- Base: browser visits `http://localhost:5666/admin`,
  `VITE_GLOB_API_URL=http://127.0.0.1:8000`, domains include localhost, and
  backend `CORS_ORIGINS` includes `http://localhost:5666`.
- Bad: browser visits `http://192.168.31.129:5666/admin`, but frontend/backend
  env still allow only localhost. Requests fail with CORS and platform-domain
  detection may also drift.

### 6. Tests Required

- `pnpm --dir frontend/apps/web-antd exec vitest run src/utils/__tests__/api-url.test.ts`
- `pytest backend/tests/middleware/test_dynamic_cors.py`
- Browser/network validation:
  - Open `/admin`
  - Confirm `/api/public/platform/config` returns 200 instead of a preflight
    CORS failure
  - Confirm `Access-Control-Allow-Origin` matches the exact page origin when the
    frontend calls the backend directly

### 7. Wrong vs Correct

#### Wrong

- Change `frontend/apps/web-antd/.env.development` to a LAN IP but leave backend
  CORS configured only for `http://localhost:5666`.
- Hardcode `http://127.0.0.1:8000` in `vite.config.mts` plugin asset proxies
  after moving API traffic to another backend origin.
- Treat `CORS_ORIGINS` as host-only or omit the port; browser CORS checks are
  origin-based, not hostname-only.

#### Correct

- Keep `VITE_GLOB_API_URL`, plugin asset proxy target, image base URL,
  Socket.IO server URL, backend `CORS_ORIGINS`, and both platform-domain lists
  aligned to the actual frontend/backend topology.
- Use exact frontend origins in backend `CORS_ORIGINS`, and keep platform-domain
  keys host-only (`localhost`, `127.0.0.1`, `192.168.31.129`) for domain
  detection.

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
- Reintroducing fixed LLM-facing prompt strings directly in Python instead of
  adding or updating a prompt contract resource.
