# Workflow Orchestration Live Smoke And Acceptance Runbook

Date: 2026-03-24

## Scope

This runbook is the execution companion for the workflow-orchestration product-module plugin.

It assumes the design baseline in:

- `docs/design/ai-orchestration-platform/39-orchestration-module-pluginization-strategy-20260323.md`
- `docs/design/ai-orchestration-platform/40-workflow-orchestration-product-module-implementation-checklist-20260323.md`
- `docs/design/ai-orchestration-platform/41-workflow-orchestration-module-4-agent-execution-plan-20260323.md`
- `docs/design/ai-orchestration-platform/42-workflow-orchestration-comprehensive-audit-20260323.md`

Its purpose is not to restate architecture. Its purpose is to tell the operator exactly how to validate the module in a real local environment.

## Current Truth

As of 2026-03-24, the current repository truth is:

- plugin code, migrations, admin frontend, tenant frontend, and plugin-local frontend entry/build scaffold are present
- targeted host regression fixes for manifest sync, paid license activation flow, plugin menu action compaction, DEBUG license fallback hardening, and permission-sync savepoint protection are present
- targeted host and plugin regression tests relevant to this operator path are green
- the remaining work for real usage is primarily operational:
  - ensure the plugin DB row is in the right state
  - ensure the target tenant is assigned
  - ensure the currently running backend process has restored enabled plugins in-process
  - run API and browser smoke

Critical nuance:

- `python -m app.cli plugin enable --plugin workflow-orchestration` fixes DB state and performs runtime registration only inside the CLI process
- if your backend server is already running in another process, that server process still needs a restart/reload or an in-process admin API enable there
- for migration inspection and repair, use `python -m app.cli db ...` instead of raw `python -m alembic ...`
- raw `python -m alembic current|upgrade heads` can miss plugin revision paths and produce a misleading `Can't locate revision identified by 'wo_002_wf_ver_nullable_fix'` error even when the real startup path is healthy

## Acceptance Target

The minimum acceptable live outcome is:

1. admin side can see workflow-orchestration plugin as enabled
2. assigned tenant receives workflow-orchestration in `/tenant/plugins/slots`
3. tenant route mount works
4. tenant home page renders
5. at least one workflow list / run list / artifact list page can open without plugin-loader or route-resolution failure

This runbook intentionally treats deeper business-path validation as phase 2.

## Preconditions

Before running smoke, confirm all of the following:

1. database migrations are healthy
2. the workflow-orchestration plugin exists in the plugin table
3. the plugin has an active paid license
4. the plugin status is `enabled`
5. the target tenant has been assigned
6. the running backend process has loaded plugin runtime extensions in-process

If any one of these is false, browser smoke is not authoritative.

Migration command rule:

- supported operator command: `python -m app.cli db current`
- supported operator command: `python -m app.cli db upgrade heads`
- supported runtime path: backend startup calling `app.core.database.run_migrations()`
- unsupported diagnostic shortcut for this pluginized migration graph: raw `python -m alembic current|upgrade heads`

## Recommended Operator Path

Run from `E:\git_clone\novusai-saas-yudi\backend`.

### Step 1. Sync plugin manifest snapshot

```bash
python -m app.cli plugin sync-manifest --plugin workflow-orchestration
```

Expected:

- CLI prints `Manifest synced`

Reason:

- current host policy intentionally keeps DB manifest snapshot explicit
- same-version disk drift should be reconciled with `sync-manifest`, not by unrelated config updates

### Step 2. Activate paid license

If a valid license key is not yet active:

```bash
python -m app.cli plugin activate-license --plugin workflow-orchestration --key "<LICENSE_KEY>"
```

Expected:

- CLI prints `License activated`

If you need to generate a local development license first, use the existing local license workflow already validated in the audit path.

### Step 3. Enable plugin

```bash
python -m app.cli plugin enable --plugin workflow-orchestration
```

Expected:

- CLI prints `Plugin enabled: workflow-orchestration`
- CLI also prints the runtime note reminding you that a separately running backend process still needs restart/reload or in-process admin enable

If this step fails:

- inspect `backend/logs/app.log`
- re-check plugin menu permission compaction and paid license state

### Step 4. Assign tenant

```bash
python -m app.cli plugin assign-tenant --plugin workflow-orchestration --tenant-id <TENANT_ID>
```

Expected:

- CLI prints `Assigned ... tenant(s)`

Reason:

- current scope model uses `admin_and_selected_tenants`
- tenant visibility is resolved by `Plugin.scope + ResourceTenantAssignment + runtime gate + license gate`

### Step 5. Restart or reload the running backend process

This step is required if your API server was already running before step 3.

Expected after restart:

- startup runs `restore_enabled_plugins()`
- startup then re-syncs plugin permissions
- plugin frontend slots and runtime API routes become available in that server process

If you skip this step, DB may say `enabled` while the live server still behaves as if the plugin were not loaded.

## API Smoke

### Step 6. Tenant plugin visibility smoke

Call:

```text
GET /tenant/plugins
GET /tenant/plugins/slots
```

Expected:

- `workflow-orchestration` appears in the visible plugin list for the assigned tenant
- tenant slot payload includes workflow-orchestration pages under `pages`

Interpretation:

- if `/tenant/plugins` is correct but `/tenant/plugins/slots` is empty, inspect in-process extension restoration
- if both are empty, inspect tenant assignment, plugin scope, plugin status, and license runtime gate

### Step 7. Optional admin slot smoke

Call:

```text
GET /admin/plugins/slots
```

Expected:

- admin slot payload includes workflow-orchestration admin pages

Note:

- if your current local admin login path is blocked by captcha enforcement, do not treat that as a plugin failure; it is an environment auth prerequisite

## Browser Smoke

Use the already running frontend and backend. Do not start new dev servers from this runbook.

### Admin entry candidates

- `/admin/plugins/workflow-orchestration`
- `/admin/plugins/workflow-orchestration/templates`
- `/admin/plugins/workflow-orchestration/releases`
- `/admin/plugins/workflow-orchestration/runtime`

### Tenant entry candidates

- `/tenant/plugins/workflow-orchestration`
- `/tenant/plugins/workflow-orchestration/workflows`
- `/tenant/plugins/workflow-orchestration/runs`
- `/tenant/plugins/workflow-orchestration/artifacts`

Minimum pass condition:

1. route resolves
2. plugin page component loads
3. no immediate plugin-loader missing-export error
4. page can request its backend API without a route-not-found failure

## Suggested Validation Order

Use this order exactly:

1. CLI `sync-manifest`
2. CLI `activate-license`
3. CLI `enable`
4. CLI `assign-tenant`
5. restart/reload backend process
6. `/tenant/plugins`
7. `/tenant/plugins/slots`
8. tenant browser route
9. admin browser route

This order is deliberate. It separates:

- DB truth
- tenant authorization truth
- in-process runtime truth
- browser rendering truth

## Failure Matrix

### Symptom: plugin row says enabled but tenant routes still 404

Likely causes:

- running backend process was not restarted after CLI enable
- enabled state exists in DB but runtime extensions were not restored in the live server process

### Symptom: tenant route exists but sidebar/menu does not show plugin

Likely causes:

- target tenant was not assigned
- tenant runtime gate denied due to inactive license or scope
- plugin permissions were not re-synced in the live server process after restart

### Symptom: plugin page route mounts but component fails to render

Likely causes:

- plugin frontend asset loading problem
- plugin release manifest / dev entry mismatch
- missing exported page component name

Current audit status says the plugin-local frontend entry/build contract is already closed, so treat this as an integration defect, not an expected gap.

### Symptom: admin API enable path is blocked by login captcha

Interpretation:

- this is an environment auth prerequisite, not evidence that workflow-orchestration logic is broken
- use CLI for DB/operator actions, then restart the live backend process, then continue smoke

## What Is Already Verified By Automated Tests

The following is already covered by targeted regression tests and should not be re-litigated during smoke unless a live symptom contradicts it:

- paid-license activation policy
- DEBUG-mode license fallback plugin mismatch rejection
- plugin operator CLI commands
- plugin menu action compaction for long page names
- permission-sync savepoint protection during enable

## What Still Requires Manual Verification

The following is still manual/live:

- real tenant route mount in the currently running frontend
- real admin route mount in the currently running frontend
- real request path through the running backend process after restart/reload
- real authenticated browser session prerequisites

## Exit Criteria

Mark the module as “live-smoke passed” only if all of the following are true:

1. plugin status is `enabled`
2. paid license is active
3. tenant assignment exists
4. `/tenant/plugins/slots` returns workflow-orchestration pages
5. at least one tenant page opens successfully in browser
6. at least one admin page opens successfully in browser

If 1-4 pass but 5-6 fail, classify the state as:

- `runtime-integrated, browser-smoke-pending`

That is not a full acceptance pass.
