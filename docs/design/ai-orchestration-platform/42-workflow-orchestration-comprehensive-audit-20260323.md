# Workflow Orchestration Comprehensive Audit

Date: 2026-03-23

## Scope

This audit reviewed:

- `backend/plugins/workflow-orchestration/**`
- host migration entry points that affect plugin installability and startup safety
- host frontend plugin loader expectations that affect plugin page mounting

The goal was to validate the AI-1/2/3/4 delivery against the current repository truth, identify real blockers, and record the execution order for the next round.

## Late Update

Host migration standardization was completed later on 2026-03-23.

- Added a shared helper that resolves Alembic `version_locations` from DB-registered plugins instead of scanning every repo plugin directory:
  - `backend/app/plugins/migration_paths.py`
- Rewired the host migration entry points to use that helper:
  - `backend/app/core/database.py`
  - `backend/app/cli.py`
  - `backend/app/plugins/lifecycle.py`
  - `backend/migrations/env.py`
- Updated the startup/manual remediation text to point to the plugin-aware CLI path:
  - `python -m app.cli db upgrade heads`
- While validating the new CLI path, an unrelated repository issue was exposed and fixed:
  - `backend/plugins/storage-billing/backend/migrations/versions/002_add_tenant_bindings.py`
  - the second storage-billing revision incorrectly repeated `branch_labels = ("plugin_storage_billing",)`, which made Alembic reject `heads/current/history`
- Validation after the fix:
  - `pytest backend/tests/test_plugin_migration_paths.py backend/tests/test_database_migration_recovery.py backend/tests/test_plugin_startup_discovery_boundaries.py -q`
  - `python -m app.cli db heads`
- `python -m app.cli db current`
- `python -m app.cli db history`
- `python -c "from app.core.database import run_migrations; print(run_migrations())"`
- Operator note confirmed again on 2026-03-24:
  - plugin-aware migration entry points are `python -m app.cli db current`, `python -m app.cli db upgrade heads`, and backend startup via `app.core.database.run_migrations()`
  - raw `python -m alembic current|upgrade heads` still does not share the same dynamic plugin `version_locations` injection path and can report a false-negative revision-resolution error even when the real startup path is healthy

## Latest Operator Truth

Later validation on 2026-03-23 confirmed the real local operator chain for the paid `workflow-orchestration` plugin:

- `python -m app.cli plugin sync-manifest --plugin workflow-orchestration`
- activate a valid paid license
- `python -m app.cli plugin enable --plugin workflow-orchestration`
- optionally `python -m app.cli plugin assign-tenant --plugin workflow-orchestration --tenant-id <TENANT_ID>`

Additional host truths discovered during that validation:

- Host plugin config updates no longer overwrite the DB manifest snapshot implicitly:
  - `backend/app/services/system/plugin_service.py`
- Plugin menu registration now compacts only overlong menu `action` values so they fit `permissions.action VARCHAR(50)` without forcing plugin-side page renames:
  - `backend/app/plugins/registry.py`
  - `backend/tests/test_plugin_menu_action_compaction.py`
- Plugin page-derived menus now support sibling page-name parent aliases during registration, so a product-module plugin can group its own child pages under a single plugin parent menu without hard-coding generated permission suffixes:
  - `backend/app/plugins/_extension_registrar.py`
  - `backend/plugins/workflow-orchestration/plugin.yaml`
  - `backend/tests/test_plugin_menu_action_compaction.py`
- DEBUG-mode license verification fallback is now hardened to reject payloads whose `plugin` does not match the expected plugin:
  - `backend/app/plugins/license.py`
  - `backend/tests/test_plugin_license_verification_policy.py`
- Plugin enable now isolates permission-sync failures inside a savepoint so a failed permission flush does not poison the outer session and cascade into `PendingRollbackError`:
  - `backend/app/plugins/lifecycle.py`
  - `backend/tests/test_plugin_lifecycle_license_gate.py`
- CLI `plugin enable` fixes DB state and registers runtime extensions only inside the CLI process. A separately running backend server still needs an in-process admin API enable or a process restart/reload to run `restore_enabled_plugins()` in that server process:
  - `backend/app/cli.py`
  - `backend/app/api/admin/plugins.py`
  - `backend/app/main.py`

## Latest Follow-up

Additional code-level reconciliation was completed on 2026-03-24:

- plugin startup restore now re-syncs plugin periodic tasks into `periodic_tasks`, so Celery Beat can still see workflow-orchestration tasks after process restart:
  - `backend/app/plugins/startup.py`
  - `backend/tests/test_plugin_startup_restore_modes.py`
- workflow-orchestration module settings no longer report already-delivered capabilities as deferred:
  - removed stale deferred flags for `runtime_state_machine`, `tenant_runtime_routes`, and `frontend_pages`
  - current deferred list now only keeps host settings UI and hosted trigger execution entrypoints
  - files:
    - `backend/plugins/workflow-orchestration/backend/models/presets.py`
    - `backend/plugins/workflow-orchestration/backend/tests/runtime/test_module_config_truth.py`

Residual truth after this follow-up:

- plugin frontend pages, menu grouping, locale registration, and tenant/admin routes are already on the real runtime path
- plugin admin API permission gating is already closed at dispatcher level and now follows host admin RBAC
- startup restore covers enabled-plugin migration replay and periodic-task re-sync, but does not itself imply a fresh permission re-sync
- workflow runtime/model enum naming drift still exists; current execution truth lives in `backend/plugins/workflow-orchestration/backend/runtime/constants.py`, while `backend/plugins/workflow-orchestration/backend/models/enums.py` remains a partial historical subset

Targeted regression validation after these host fixes:

- `pytest backend/tests/test_plugin_lifecycle_license_gate.py backend/tests/test_plugin_license_verification_policy.py backend/tests/test_plugin_cli_operator_flow.py backend/tests/test_plugin_menu_action_compaction.py -q`
- result: `12 passed`

## Verified Facts

### Backend runtime

- Plugin runtime tests pass: `pytest backend/plugins/workflow-orchestration/backend/tests/runtime -q` → `23 passed, 1 warning`
- Plugin backend compile passes: `python -m compileall backend/plugins/workflow-orchestration/backend`
- `run_migrations()` succeeds in the current local environment

### Migration state

- The workflow plugin migration chain is linear:
  - `wo_001_init`
  - `wo_002_wf_ver_nullable_fix`
- The earlier revision-id length problem is no longer present after the revision id was shortened to `wo_001_init`

### Frontend mountability

- Before this audit round, the plugin frontend had view files only
- It did not have a root frontend entry file, release build config, or a page export surface matching `plugin.yaml`

## Findings

### F1. Historical blocker: host startup previously auto-loaded every repo plugin migration

Original problem before the later host migration standardization:

- startup and migration bootstrap used repo-wide plugin discovery semantics
- this could make a source-only plugin influence migration graph resolution too early

Impact:

- a source-only plugin can block main application startup
- this violates the intended "optional module / installable plugin" boundary
- `workflow-orchestration` can affect startup even when it is not enabled

Relevant files:

- `backend/app/core/database.py`
- `backend/app/plugins/migration_paths.py`
- `backend/app/plugins/lifecycle.py`
- `backend/migrations/env.py`

Status:

- resolved later in this audit sequence by switching migration path resolution to DB-registered plugins
- current operator path should be read from the "Late Update" section, not from this historical finding heading

### F2. Raw Alembic CLI and startup/plugin lifecycle do not resolve the same revision graph

Current behavior:

- startup/plugin lifecycle inject plugin `version_locations` before Alembic command execution
- raw `alembic heads/current/history` still depends on static config too early

Observed consequence:

- raw CLI did not list workflow-orchestration revisions even though `alembic_version` contains `wo_002_wf_ver_nullable_fix`
- this can produce misleading `Can't locate revision identified by 'wo_002_wf_ver_nullable_fix'` errors from the raw CLI path

Relevant files:

- `backend/alembic.ini`
- `backend/migrations/env.py`
- `backend/app/core/database.py`
- `backend/app/plugins/lifecycle.py`

Status:

- identified
- intentionally not changed in this round because it requires host-level migration CLI standardization
- not a blocker for real startup or operator flow as long as the project-standard entry points remain `python -m app.cli db ...` and `app.core.database.run_migrations()`

### F3. Workflow plugin frontend was not loadable in either dev or release mode

Before this audit round, `plugin.yaml` declared frontend pages and a dev entry/release manifest contract, but the plugin frontend directory lacked:

- `frontend/src/index.ts`
- plugin-local Vite build config
- plugin-local package metadata
- exported component names matching `plugin.yaml frontend.pages[*].component`

Impact:

- host plugin loader could not resolve page components
- `setup()` locale registration never ran
- real browser mounting was blocked regardless of AI-3/AI-4 view completeness

Relevant files:

- `backend/plugins/workflow-orchestration/plugin.yaml`
- `frontend/apps/web-antd/src/utils/plugin-loader.ts`
- `frontend/apps/web-antd/src/utils/plugin-shared.ts`

Status:

- fixed in this audit round inside plugin boundary

### F4. `wo_002_wf_ver_nullable_fix` had a downgrade hazard

Observed truth:

- `wo_001_init` already creates the final intended nullable state
- `wo_002` upgrade is effectively a no-op against that state
- `wo_002` downgrade previously flipped nullability away from the current ORM/schema truth

Impact:

- downgrade/uninstall flows could regress schema semantics
- downgrade could fail if trigger rows rely on `NULL workflow_version_id`

Status:

- fixed in this audit round by making `wo_002` downgrade a no-op

### F5. AI handoff docs have drift and incomplete truth coverage

Observed issues:

- AI-3 and AI-4 integration caveats were directionally correct, but some sample export/route guidance drifted from the live manifest
- older parallel-delivery-kit handoff templates remain mostly empty and should not be used as truth

Impact:

- future merge work can follow stale symbols or routes
- audit quality drops if teams rely on placeholder handoffs instead of the live plugin tree

Status:

- identified
- follow-up doc cleanup still recommended

## Fixes Applied In This Audit Round

### Plugin frontend skeleton

Added plugin-local frontend runtime entry and build scaffold:

- `backend/plugins/workflow-orchestration/frontend/src/index.ts`
- `backend/plugins/workflow-orchestration/frontend/package.json`
- `backend/plugins/workflow-orchestration/frontend/vite.config.ts`

What this now does:

- exports the exact page component names declared in `plugin.yaml`
- keeps compatibility aliases for the shorter names used in earlier handoff notes
- registers admin and tenant locale bundles through `NovusPluginShared.registerLocale`
- defines a plugin-local UMD build contract and generates `plugin.manifest.json` during build

### Migration safety

Adjusted:

- `backend/plugins/workflow-orchestration/backend/migrations/versions/002_fix_workflow_version_nullability.py`

Change:

- downgrade is now a no-op so it no longer diverges from the `wo_001_init` schema truth

## Remaining Gaps

### Host/platform changes still required

1. Startup migration scope must stop blindly scanning all repo plugins if the product requirement is truly "optional installable module".
2. Raw CLI migration commands must use the same plugin revision discovery strategy as startup/plugin lifecycle.

### Plugin release/browser validation is only partially closed

The plugin frontend release scaffold is no longer theoretical.

Verified after this audit:

- `npm install --no-package-lock --legacy-peer-deps` inside `backend/plugins/workflow-orchestration/frontend`
- `npm run build` inside `backend/plugins/workflow-orchestration/frontend`
- `python -m app.cli plugin build E:\git_clone\novusai-saas-yudi\backend\plugins\workflow-orchestration`
- `python -m app.cli plugin validate E:\git_clone\novusai-saas-yudi\backend\plugins\workflow-orchestration`
- release-mode frontend contract validation against `frontend/dist/plugin.manifest.json`

Still not verified:

- browser-level admin route mount
- browser-level tenant route mount
- paid-plugin license path in a real browser session

## Recommended Execution Order

1. Keep the plugin-only fixes from this audit round.
2. Decide host policy for optional plugin migrations:
   - installed-only
   - enabled-only
   - or explicit allowlist
3. Unify Alembic CLI and startup/plugin lifecycle revision discovery.
4. Run a browser mount smoke test under a valid plugin license in both dev and release host modes.
5. Clean handoff docs so only one current truth set remains authoritative.

## Evidence Snapshot

Independent validation run in this audit round:

- `python -m pytest backend/plugins/workflow-orchestration/backend/tests/runtime -q`
- `python -m compileall backend/plugins/workflow-orchestration/backend`
- `python -c "from app.core.database import run_migrations; print(run_migrations())"`

Result:

- backend plugin runtime is currently test-green
- frontend packaging/release build is now closed inside plugin boundary
- host migration strategy remains the main platform-level blocker

## Late Update

### Host migration graph is now plugin-row aware

Host migration entry points were hardened so Alembic only includes migration paths for plugins that exist in the database plugin registry and are not soft-deleted.

Changed files:

- `backend/app/plugins/migration_paths.py`
- `backend/app/core/database.py`
- `backend/app/cli.py`
- `backend/app/plugins/lifecycle.py`
- `backend/migrations/env.py`

Validated:

- `pytest backend/tests/test_plugin_migration_paths.py backend/tests/test_database_migration_recovery.py backend/tests/test_plugin_startup_discovery_boundaries.py -q`
- `python -m app.cli db heads`
- `python -m app.cli db current`
- `python -m app.cli db history`

## Late Update

### Browser smoke blocker has been narrowed down

Current browser-level smoke is not primarily blocked by missing frontend exports, missing
`plugin.yaml` page declarations, or a broken Vite dev provider.

The real blockers in the current local environment are:

1. `workflow-orchestration` is a paid plugin and currently has no active license
2. the plugin record is still `installed`, not `enabled`
3. the DB manifest snapshot is stale relative to disk and startup correctly marks
   `sync-manifest` as required

This means the remaining path to real browser smoke is operational state alignment:

1. sync manifest
2. activate a valid license
3. enable the plugin
4. for tenant smoke, assign the plugin to the target tenant and use the correct tenant domain context

For local development, the host CLI now provides the missing operator path so this sequence does not
require hand-written API calls:

```powershell
cd backend
python -m app.cli plugin sync-manifest --plugin workflow-orchestration
python -m app.cli license keygen
python -m app.cli license generate --plugin workflow-orchestration --days 30
python -m app.cli plugin activate-license --plugin workflow-orchestration --key "<GENERATED_KEY>"
python -m app.cli plugin enable --plugin workflow-orchestration
python -m app.cli plugin assign-tenant --plugin workflow-orchestration --tenant-id <TENANT_ID>
```

Notes:

- in local DEBUG mode, license verification may use the development fallback when no public key is configured
- `assign-tenant` is only needed for tenant-side smoke because the plugin scope is
  `admin_and_selected_tenants`

### Manifest truth has been clarified

The admin plugin list/detail APIs intentionally expose the database manifest snapshot, not a live
view of `backend/plugins/*/plugin.yaml`.

This is by design:

- startup discover detects same-version drift and marks it as `sync_required`
- startup restore does not hot-sync manifest
- explicit `sync-manifest` is the supported write path for non-version manifest drift

However, one host implementation path was inconsistent with that contract:

- `backend/app/services/system/plugin_service.py`
- `update_plugin_config()` loaded the latest disk manifest for schema validation and also wrote it
  back into `plugin.manifest`

That side effect is now fixed. Configuration updates still validate against the latest disk schema,
but they no longer implicitly sync the DB manifest snapshot.

Regression coverage added:

- `backend/tests/test_plugin_manifest_sync_service.py`
- `backend/tests/test_plugin_trial_license_policy.py`

### Handoff drift warning

The most authoritative document for the current repository truth is this audit file.

The earlier AI-2 / AI-3 / AI-4 handoff notes inside
`docs/design/ai-orchestration-platform/41-workflow-orchestration-delivery-kit-20260323/`
still contain outdated integrator assumptions, especially around:

- missing frontend page exports
- missing plugin frontend root entry
- missing locale registration chain
- missing `plugin.yaml` route/page declarations

Those statements are no longer current repository truth and should not be used as the primary
integration checklist.
- `python -c "from app.core.database import run_migrations; print(run_migrations())"`

Outcome:

- optional/source-only repo plugins no longer poison startup migration resolution
- disabled but installed plugins still participate in migration history, which keeps Alembic graph continuity intact

### Plugin CLI validation now catches source-build frontend drift earlier

`backend/scripts/plugin_cli.py` validate now fails fast for frontend plugins when:

- `frontend/package.json` is missing or invalid
- `frontend/vite.config.ts` is missing
- `vue` exists only in `peerDependencies` and not in `dependencies` or `devDependencies`

Regression coverage:

- `pytest tests/test_plugin_cli_release_workflow.py -q`

Real plugin validation:

- `python -m app.cli plugin validate E:\git_clone\novusai-saas-yudi\backend\plugins\workflow-orchestration`

Current caveat:

- two old `.backups` samples still use `icon: lucide:*`, which violates the current `PluginManifest` metadata rule; the historical baseline test was updated to encode that current truth instead of incorrectly expecting those samples to pass validation.

### Host dev-mode plugin loading contract is real, and loader now degrades safely

Changed files:

- `frontend/apps/web-antd/build/vite-plugin-novus-plugins.ts`
- `frontend/apps/web-antd/src/utils/__tests__/vite-plugin-novus-plugins.test.ts`
- `frontend/apps/web-antd/src/utils/plugin-loader.ts`
- `frontend/apps/web-antd/src/utils/__tests__/plugin-loader.test.ts`

Current truth:

- host Vite already exposes `/__plugin_dev__/{plugin}/entry` via `novusPluginsLoader.configureServer()`
- the Vite plugin resolves plugin `frontend.dev.entry` from `plugin.yaml`, transforms the source through Vite, and watches the plugin source directory in dev mode
- host loader still tries `/__plugin_dev__/{plugin}/entry` first in dev mode
- if that dev import fails, host now falls back to the plugin release manifest/bundle path instead of aborting plugin page loading entirely
- `runtimeContract.dev_entry` is forwarded into the dev URL query for forward compatibility, even though the current Vite middleware resolves the entry from plugin manifest data on disk

Validated:

- `pnpm exec vitest run apps/web-antd/src/utils/__tests__/vite-plugin-novus-plugins.test.ts apps/web-antd/src/utils/__tests__/ai-page-capabilities.test.ts apps/web-antd/src/utils/__tests__/plugin-loader.test.ts --dom`

Important boundary:

- the dev provider exists only in the host Vite dev server, not in backend FastAPI routes
- browser sessions that bypass the host Vite dev server and hit backend only will still rely on release assets
- the loader fallback remains a pragmatic availability guard for dev-source failures, not a replacement for the Vite middleware
