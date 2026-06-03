# NovusDoc Rich Text AI Operations Handoff

> Date: 2026-05-05  
> Owner lane: DevOps / Docs  
> Scope: local run, validation, configuration, rollback, troubleshooting. No business implementation changes.

## Summary

- Latest product/architecture decision: **runtime assignment truth for this release is `system.ai_writing`**.
- NovusDoc rich-text right-click actions — continue, rewrite, insert/new content, format, optimize, proofread, translate, summarize, expand, custom/chat — must resolve the Agent bound to `system.ai_writing`.
- `plugin.novusdoc.rich_text_ai` is **not** part of this release's runtime resolver. Treat it only as plugin manifest/catalog metadata and a possible future independent scene feature.
- `plugin.novusdoc.rich_text_ai` catalog/future metadata is not a runtime acceptance target for this round.
- Local frontend `http://localhost:5666` and backend `http://localhost:8000` were reachable during this handoff.
- Admin default dev login worked during initial verification: `/admin/login`, `admin / admin123456`.
- Skill package page `/admin/ai/skill-packages` loaded after login during initial verification.
- Initial Agent Assignment page showed `system.ai_writing -> NovusDoc Writer`, enabled; this is the relevant runtime control row for this round.
- Initial NovusDoc editor page `/admin/plugins/novusdoc/editor/9` loaded an existing document and auto-saved; later refresh/re-login rendered the app 404 page, so plugin route/menu sync remains a release-blocking re-check.
- Current status is **BLOCKED for release** until the verification gates in [Release / QA Re-test Gate](#release--qa-re-test-gate) are green.

## Required Local Services

```bash
# repository root
docker compose -f docker-compose.dev.yml up -d
```

Provides:

- PostgreSQL `localhost:5432`, database `novusai_saas`, user/password `postgres/postgres`
- Redis `localhost:6379`

Backend:

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
uv sync --extra dev
copy .env.example .env
novusai db upgrade head
novusai run --host 127.0.0.1 --port 8000 --reload
```

Worker:

```bash
cd backend
.venv\Scripts\activate
novusai celery dev
```

Frontend:

```bash
cd frontend
pnpm install
pnpm dev:antd
```

Important env defaults:

- backend `.env`: `DATABASE_*`, `REDIS_*`, `CORS_ORIGINS=["http://localhost:5666"]`, `PLATFORM_DOMAINS=localhost,127.0.0.1`
- frontend `apps/web-antd/.env.development`: `VITE_PORT=5666`, `VITE_GLOB_API_URL=http://localhost:8000`

## Feature Code / Assignment Contract

### Runtime truth

`system.ai_writing` is the only runtime assignment truth for this release.

| Feature code | Role | Runtime behavior |
|---|---|---|
| `system.ai_writing` | Runtime assignment truth | Resolve this row for NovusDoc Rich Text AI operations. Changing this binding must change the Agent used by rich-text AI calls. |
| `plugin.novusdoc.rich_text_ai` | Plugin catalog / manifest / future feature | May appear in plugin `ai_requirements`, skill-package metadata, migration seed data, or future planning. It must not participate in this release's runtime Agent resolver. |

### Verification required

Release validation must prove:

1. `system.ai_writing` exists and is active/bound to a published available Agent.
2. Changing `system.ai_writing` in `/admin/ai/agent-assignments` changes the `agent_id` logged by the rich-text AI stream.
3. Rich-text right-click/selection actions use the same `system.ai_writing` Agent for continue, rewrite, insert/new content, format, and other supported actions.
4. `plugin.novusdoc.rich_text_ai` metadata, if present, does not override or shadow `system.ai_writing` in runtime calls.

## Skill Package Page Notes

`/admin/ai/skill-packages` is catalog/source/grouping UI, not sufficient proof of runtime binding.

Checklist:

- Page opens without 401/403/500.
- NovusDoc Rich Text AI package/skill metadata may be visible for catalog/discovery purposes.
- Package metadata may mention `plugin.novusdoc.rich_text_ai` as plugin scene/catalog metadata, but runtime control for this release remains `system.ai_writing`.
- If Rich Text AI depends on skills, verify direct Agent skill grants on the Agent bound to `system.ai_writing`; do not rely only on package presence.
- SkillPackage remains “directory/source/grouping”; runtime capability must be proven through `system.ai_writing` Agent Assignment resolution.

## Agent Assignment Page Notes

Page: `http://localhost:5666/admin/ai/agent-assignments`

Checklist:

- Target runtime feature exists: `system.ai_writing`.
- Bound Agent is published and reachable by the current admin/tenant scope.
- Toggle is enabled for `system.ai_writing`.
- Changing the `system.ai_writing` Agent selection must be reflected in backend rich-text AI stream logs.
- `plugin.novusdoc.rich_text_ai`, if present, is not the runtime row for this release and should not be used as the acceptance target.
- For tenant calls, AI plan access and API quota must pass before streaming starts.

## NovusDoc Editor Validation

Page: `http://localhost:5666/admin/plugins/novusdoc/editor/9`

Prerequisites:

- NovusDoc plugin installed and enabled.
- Admin permission includes `plugin.novusdoc.novusdoc_admin:view`; editing requires `update`, export requires `export`.
- Document id exists; if `9` is missing, create a document from `/admin/plugins/novusdoc` and use that id.
- `window.NovusPluginShared.mountRichTextEditor` is available.

Expected Rich Text AI workflow after implementation:

1. Select text or place cursor in editor.
2. Right-click or open selection menu.
3. Show actions such as continue, rewrite, insert/new content, format, optimize, proofread, translate, summarize, expand, custom.
4. Trigger `POST /api/admin/ai/writing/{feature}` or `POST /api/admin/ai/rich-text/operations/{action}` as SSE.
5. Resolve runtime Agent through `system.ai_writing` assignment.
6. Receive `event: message` deltas and `event: done`.
7. Show generated result preview before mutating editor content.
8. Support accept/apply, undo/cancel, and safe failure without losing selected text.
9. Apply result via explicit editor selection/cursor payload, not DOM/page runtime.
10. Auto-save document through `PUT /admin/plugins/novusdoc/api/docs/{id}` only after an accepted content mutation.

Current local status: **BLOCKED**. Initial editor load/save was observed once, but Rich Text AI menu/SSE was not observed; later refresh/re-login rendered the app 404 page. Re-test plugin route/menu sync and the full Rich Text AI interaction after latest frontend/backend changes are running.

## AI Writing API Contract

Current backend routes:

- Compatibility: `POST /api/admin/ai/writing/{feature}`
- Compatibility: `POST /api/tenant/ai/writing/{feature}`
- Rich-text operation: `POST /api/admin/ai/rich-text/operations/{action}`
- Rich-text operation: `POST /api/tenant/ai/rich-text/operations/{action}`

Runtime assignment resolution for these endpoints must use `system.ai_writing` for this release.

Backend canonical actions include:

- `continue`
- `insert`
- `rewrite`
- `optimize`
- `proofread`
- `translate`
- `summarize`
- `expand`
- `format`
- `custom`
- `chat`

Before release, frontend action templates/types/tests must be aligned with backend canonical actions for product-required actions such as `insert` and `format`.

Backend request fields currently include:

- `selected_text`
- `before_text`
- `after_text`
- `context_title`
- `document_title`
- `document_id`
- `document_type`
- `surface`
- `instruction`
- `format_instruction`
- `target_lang`
- `history`
- `plain_input_policy` (only for plain input/textarea operations; contains field kind, enabled flag, and action allowlist)

Frontend request types may expose only a subset; keep both schemas synchronized before declaring API complete.

Governance boundary: do not send `page_context`, `page_session_id`, `ui_*`, `pageop_*`, DOM snapshots, or current-page runtime state. Rich Text AI must use explicit editor payloads only.

## Verification Executed

Browser checks already performed:

- `GET http://localhost:8000/api/public/platform/config` returned 200.
- Skill package page opened and loaded catalog cards during initial login session.
- Agent assignment page initially showed `system.ai_writing -> NovusDoc Writer`, enabled. This is the relevant runtime row for this release.
- Initial NovusDoc editor id `9` check loaded; `GET /admin/plugins/novusdoc/api/docs/9` and `PUT /admin/plugins/novusdoc/api/docs/9` returned 200.
- Initial editor page console had no error/warn.
- No `/admin/ai/writing/*` or `/admin/ai/rich-text/operations/*` request was observed during the initial editor check.
- Later refresh/re-login check reached `http://localhost:5666/admin/plugins/novusdoc/editor/9` but rendered the app 404 page; re-check plugin route/menu sync before final release validation.

Backend structural/service tests, latest recorded rerun:

```powershell
cd backend
$env:NOVUSAI_CLI_DISABLE_FILE_LOGGING='1'
python -m pytest tests/services/test_writing_service.py tests/api/test_tenant_agent_assignment_resolve_route.py tests/api/test_tenant_ai_runtime_plan_guards.py::test_tenant_ai_writing_rejects_plan_disabled_before_stream_service tests/migrations/test_novusdoc_rich_text_ai_seed.py -q
```

Recorded result: `9 passed, 1 failed`. Failure:

- `tests/services/test_writing_service.py::TestStreamWritingFeature::test_stream_writing_feature_raises_on_error_event`
- Error: mocked `_resolve_writing_agent` returned `int`, while updated `stream_writing_feature` expected `(agent_id, resolved_feature_code)`.
- Status: **BLOCKED** until backend pytest is green after the `system.ai_writing` runtime-truth decision is implemented in tests and code.

Frontend structural tests previously run:

```powershell
cd frontend
pnpm -F @vben/web-antd exec vitest run --dom src/features/rich-text-ai/__tests__/contracts.test.ts src/components/business/rich-text-editor/__tests__/RichTextEditor.test.ts src/components/business/rich-text-editor/__tests__/mountRichTextEditor.test.ts
```

Recorded result: 3 test files passed, 5 tests passed.

This is not enough for release. The latest blocker list still includes `vue-tsc` and full interaction checks below.

These are structural/service-contract checks only. They are not behavioral or real-provider smoke acceptance.

## Current BLOCKED Items

Release remains blocked until all items below are resolved and re-run:

1. **Feature-code runtime contract:** rich-text runtime must resolve `system.ai_writing`; `plugin.novusdoc.rich_text_ai` must remain catalog/future metadata only for this release.
2. **Backend pytest:** current recorded backend run has one failure; rerun full targeted backend set after code/test sync.
3. **Frontend typecheck:** `vue-tsc` is still blocked/not green; run `pnpm -F @vben/web-antd run typecheck` or the project-approved equivalent.
4. **DocumentEditor result preview:** generated AI result must be previewed before mutating editor content.
5. **DocumentEditor undo/cancel:** user must be able to cancel/undo an AI result without losing original content.
6. **Selection protection:** replacing text must validate that the original selection/range is still valid and must not overwrite unrelated content after cursor/selection drift.
7. **Smoke not run:** no real-provider or approved replay smoke has been executed for Rich Text AI; do not claim complete or regression-green.
8. **Plugin route/menu re-check:** editor route rendered 404 on later re-login; route/menu/plugin sync needs re-verification.

## Rollback

Fast disable:

- Disable or unbind `system.ai_writing` in `/admin/ai/agent-assignments` if the rich-text AI feature must be stopped quickly.
- Because `system.ai_writing` may have other legacy writing consumers, coordinate with product/backend before disabling it globally.
- Hide/disable the Rich Text AI frontend menu if a feature gate exists; this is safer when `system.ai_writing` is shared.
- Keep base NovusDoc editor, CRUD, and auto-save enabled.

Data rollback:

- If migration `20260505_0027_seed_novusdoc_rich_text_ai.py` was applied, `plugin.novusdoc.rich_text_ai` cleanup affects catalog/future metadata only for this release.
- Do not treat removal of `plugin.novusdoc.rich_text_ai` as a runtime rollback for this round.
- Keep `system.ai_writing` unless its separate legacy consumers are intentionally retired or the release rollback explicitly requires disabling all writing AI.

Frontend rollback:

- Revert AI context menu / SSE caller / result preview / result apply code only.
- Preserve `RichTextEditor` base mount/edit/save behavior.

## Troubleshooting

| Symptom | Check |
|---|---|
| Page redirects to login | Admin token expired; log in again. |
| Skill packages empty or 500 | DB migrations, SkillPackage rows, plugin sync. |
| `system.ai_writing` row missing/unbound | `novusai db upgrade head`; seed data; `/admin/ai/agent-assignments`; bind a published Agent. This is the runtime row for this release. |
| `plugin.novusdoc.rich_text_ai` row missing | Catalog/future metadata may be missing, but this should not block runtime for this release unless the catalog page is part of the acceptance scope. |
| Bound Agent ignored | Compare `system.ai_writing` binding with backend resolver; check `ai_writing_stream` log `resolved_feature_code` and `agent_id`. |
| Editor route renders 404 | Re-check plugin install/enable state, menu sync, frontend plugin manifest, and admin permissions. |
| Editor document missing | Document id not found; create or use another id. |
| AI menu missing | Frontend implementation/feature gate/hot reload; console errors; RichTextEditor selection APIs. |
| SSE `AI_WRITING_ERROR` | `system.ai_writing` assignment state, Agent unpublished/deleted, provider key missing, model unavailable, upstream timeout. |
| Tenant 403 | Tenant AI plan/access disabled. |
| Tenant quota failure | Monthly API quota exhausted. |
| Result preview missing | DocumentEditor preview flow not wired; release blocked. |
| Undo/cancel missing | DocumentEditor undo/cancel flow not wired; release blocked. |
| Selection drift or wrong replacement | Selection snapshot/range validation missing or stale; release blocked. |
| Result applies but does not persist | Check NovusDoc `PUT docs/{id}` permission and auto-save debounce. |

## Release / QA Re-test Gate

Do not mark Rich Text AI release-ready until all gates below are green:

- [ ] Runtime resolver, frontend constants/API calls, tests, and runbook all use `system.ai_writing` as the runtime assignment truth for this release.
- [ ] `plugin.novusdoc.rich_text_ai` is documented/tested only as plugin manifest/catalog/future independent scene metadata and does not affect runtime Agent resolution.
- [ ] Changing the `system.ai_writing` binding changes runtime `agent_id` in backend logs for rich-text continue/rewrite/insert/format actions.
- [ ] Assigned `system.ai_writing` Agent is published and has required model/skill capability.
- [ ] Skill package detail/catalog displays Rich Text AI metadata without implying package presence is runtime authorization.
- [ ] Editor context menu appears and triggers the approved Rich Text AI SSE endpoint.
- [ ] Backend logs/diagnostics show the expected `system.ai_writing` resolved feature and `agent_id`.
- [ ] Admin page verified; tenant page verified if tenant support is in scope.
- [ ] `vue-tsc` / frontend typecheck is green.
- [ ] Targeted frontend structural tests are green.
- [ ] Targeted backend pytest is green.
- [ ] DocumentEditor result preview is verified.
- [ ] DocumentEditor undo/cancel is verified.
- [ ] DocumentEditor selection/range protection is verified.
- [ ] Real-provider or approved replay smoke has run and is archived; smoke currently not run.
- [ ] Structural, behavioral, and smoke evidence are separated; do not use “all tests passed” as full acceptance.
- [ ] Rollback path confirmed before release.
