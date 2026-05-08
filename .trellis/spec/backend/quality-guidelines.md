# Quality Guidelines

> Backend changes are not done when the code compiles. They are done when the
> relevant tests, contracts, and operational checks are covered.

## Overview

Required commands from `backend/`:

```bash
python scripts/check_prompt_contracts.py
pytest
ruff check .
ruff format .
```

Primary references:

- `backend/pyproject.toml`
- `README.md`

## Repository Quality Baseline Contract

Use this contract when a task claims repository-wide backend quality baseline,
changes `backend/pyproject.toml` quality-tool settings, fixes pytest collection,
or makes broad mechanical lint/format changes.

## Production Acceptance Probe Contract

Use this contract when a task claims production delivery readiness, SaaS
handoff readiness, security-audit closure, capacity-readiness closure, or
release acceptance beyond ordinary unit/lint gates.

Run from `backend/`:

```powershell
python scripts/production_acceptance_probe.py --api-base-url http://localhost:8000 --frontend-base-url http://localhost:5666 --load-smoke-requests 32 --load-smoke-concurrency 8 --allow-blocked
python -m pip_audit --local --skip-editable
python -m bandit -r app scripts -x .venv,migrations,plugins/.backups,tests -ll
pnpm --dir ../frontend audit --audit-level high --registry https://registry.npmjs.org --json
pnpm --dir ../frontend audit --prod --audit-level high --registry https://registry.npmjs.org --json
```

Contract:

- `passed` means the local probe proved that specific gate in the current
  environment.
- `blocked` means the delivery gate is still not accepted because required
  infrastructure, credentials, scenario ledgers, or operator tooling is absent.
  Do not report `blocked` as production-ready.
- The local `/ready` load smoke is a health-smoke only; it is not a capacity
  benchmark. Real capacity acceptance still requires k6/Locust or an equivalent
  load plan, target concurrency/throughput, SLOs, and operator signoff.
- Security acceptance needs both dependency audit and SAST/DAST evidence.
  `pip-audit` and `bandit -ll` passing does not replace DAST or a manual
  threat-model review for public routes.
- Backup/restore acceptance requires actual `pg_dump`/`pg_restore`/`psql`
  tooling and a restore drill against a disposable database, not only a script
  presence check.
- DAST acceptance requires an actual OWASP ZAP baseline/API scan execution
  against a local or test target. Docker availability alone is tooling evidence,
  not scan acceptance; a missing local image or unreachable registry is
  `blocked`, and ZAP FAIL alerts are `failed`.
- Frontend dependency audit must use a registry with a working audit endpoint.
  Registry endpoint/network failures are `blocked`; high/critical production
  dependency findings are `failed`.
- AI runtime readiness remains governed by
  `.trellis/spec/ai-runtime/testing-discipline.md`: real-dialogue smoke must
  have provider credentials, a scenario ledger, an agent selector, and an
  archived smoke report before anyone can claim complete AI dialogue production
  acceptance.

### Scope / Trigger

- Trigger: `python -m pytest -q`, `python -m ruff check .`, or
  `python -m ruff format --check .` fails for reasons outside one narrow
  feature test.
- Trigger: a task modifies pytest collection/package layout, Ruff
  `select`/`ignore`/`exclude`/format settings, or Alembic/model registration
  helpers as part of quality cleanup.
- Non-trigger: one targeted unit test failure for a feature branch. Use the
  smallest relevant test there, then include the baseline gates before merge if
  the branch touches shared quality configuration.

### Command Signatures

Run these from `backend/` unless noted:

```powershell
python -m pytest -q
python -m ruff check .
python -m ruff format --check .
python scripts/check_prompt_contracts.py
python scripts/lint_migrations.py
```

For frontend impact from a backend-quality cleanup, run from repo root:

```powershell
pnpm --dir frontend/apps/web-antd exec vue-tsc --noEmit --skipLibCheck --pretty false
```

For Alembic graph checks on Windows, set the import root explicitly:

```powershell
$env:PYTHONPATH='.'; alembic heads
```

### Configuration Contracts

- `backend/pyproject.toml` must keep pytest collecting the real backend suite:
  `testpaths = ["tests"]`. Do not narrow this to make collection green.
- Keep pytest temporary files in a repo-local ignored directory when the
  developer machine's global temp directory is unreliable. The accepted
  setting is `--basetemp=.pytest-tmp`, and `.pytest-tmp/` must remain ignored.
- Ruff format must use `line-ending = "lf"` so Windows `core.autocrlf`
  warnings do not decide formatter output.
- Ruff cleanup must not add broad `exclude`, `extend-exclude`, `per-file-ignores`,
  or remove lint families from `select` unless the task records a concrete
  rule conflict with the owning Trellis spec.
- `git diff --check` warnings about `LF will be replaced by CRLF` are line-ending
  conversion notices. They are not whitespace failures when the command exits
  zero and reports no `trailing whitespace`, `space before tab`, blank-EOF, or
  conflict-marker issue.

### Validation And Error Matrix

| Symptom | Allowed Fix | Forbidden Fix | Required Check |
|---|---|---|---|
| pytest import mismatch from same-named tests | Add package `__init__.py` files or rename one test module while preserving both tests | Delete one test, narrow `testpaths`, or add broad `--ignore` | `python -m pytest -q` plus targeted duplicate-module tests |
| pytest references a retired structural seam | Update the structural test to the current public facade, or add a stable facade only if the import is still a supported contract | Reintroduce deprecated runtime behavior only for tests | Targeted structural test and full pytest |
| Ruff unused imports in files with registration side effects | Replace long import lists with explicit registration/facade contracts that still trigger side effects | Blind `ruff --fix` that removes registration imports without proving behavior | `python -m ruff check .` plus subsystem structural check |
| Formatter drift across many files | Run `python -m ruff format .` as a mechanical pass, then inspect non-format semantic files separately | Mix broad format with unrelated product refactors | `python -m ruff format --check .` and `git diff --check` |
| Windows temp permission errors in pytest | Use repo-local ignored `--basetemp=.pytest-tmp` | Skip affected tests or mark global warnings as ignored | Full pytest from `backend/` |

### Good / Base / Bad Cases

Good:

```text
Fix collection by adding package __init__.py files so
tests/unit/ai/test_prompt_addition_support.py and
tests/ai/context/test_prompt_addition_support.py have distinct module names.
Both tests still collect and run.
```

Base:

```text
Format-only changes are accepted when they are produced by
python -m ruff format . and followed by ruff format --check, ruff check, and
git diff --check.
```

Bad:

```toml
# Do not shrink collection to hide failures.
testpaths = ["tests/services"]

# Do not exclude live backend code to make lint green.
extend-exclude = ["app/ai", "plugins"]
```

### Wrong Vs Correct

Wrong:

```python
# A retired runtime path was deleted, so the test is simply skipped forever.
pytestmark = pytest.mark.skip(reason="old AI path")
```

Correct:

```python
def test_current_facade_composes_supported_mixins() -> None:
    assert issubclass(CurrentFacade, SupportedMixin)
```

Wrong:

```powershell
python -m ruff check . --fix
# Then commit without checking that Alembic/model registration still happens.
```

Correct:

```powershell
python -m ruff check . --fix --select I001,UP009,UP012,UP035,UP037,C420,SIM117
python -m ruff check .
python -m pytest -q
$env:PYTHONPATH='.'; alembic heads
```

### Tests Required

When a PR claims the repository quality baseline is clean, report these exact
commands and outcomes:

- `python -m pytest -q`: include passed/skipped/warning counts.
- `python -m ruff check .`: must pass.
- `python -m ruff format --check .`: must pass.
- `python scripts/check_prompt_contracts.py`: must pass for any backend baseline
  touching `app/ai`, `app/services/ai`, tests under `tests/ai`, or broad format
  that includes AI files.
- `python scripts/lint_migrations.py`: must pass when migrations, Alembic env,
  model exports, or broad backend format touches migration files.
- Frontend type/lint/test command(s) when frontend files or shared contracts
  changed.

If AI dialogue live paths are changed, these structural gates are not enough:
also follow `.trellis/spec/ai-runtime/testing-discipline.md` and do not claim a
dialogue milestone is green without behavioral and smoke evidence.

## Forbidden Patterns

- Controller logic that performs business decisions or direct DB queries.
- Service logic that manually reconstructs repository behavior.
- Modules that mix transport, business policy, persistence, and background-task
  concerns without a clear boundary.
- Controllers or services that bypass their normal contract and reach into
  lower-layer internals just to ship a shortcut.
- New controller-level SQL/ORM query assembly (`db.execute`, `session.execute`,
  ad-hoc `select(...)`) in `backend/app/api/**`.
- `except Exception: pass` or `continue`.
- New raw `@celery_app.task` or `@shared_task` in business task modules.
- New migration SQL using interpolated identifiers.
- Shipping backend work without the tests that already exist for the touched
  subsystem.
- Manufacturing a repository green state by deleting tests, narrowing pytest
  collection, adding broad `skip`/`xfail`, broadening Ruff excludes, or removing
  lint families without a spec-backed justification.
- Reintroducing deprecated AI runtime paths such as `ToolRegistry` or
  `tool_bindings`.
- Reintroducing fixed LLM-facing prompt text directly in Python under
  `app/ai` or `app/services/ai` instead of using the shared prompt contract
  resources.

## Required Patterns

- New or substantially changed services should have unit tests in
  `backend/tests/services/`.
- Keep each controller/service/repository/runtime helper focused on one
  dominant responsibility; if unrelated reasons trigger edits in the same
  module, split the module before adding more branching.
- If a backend file is oversized because it mixes multiple stable change axes,
  prefer `facade + internal package/modules` over keeping one giant file or
  introducing an untyped miscellaneous helper bucket.
- Oversized backend CLI or maintenance scripts follow the same rule: keep the
  public `cmd_*` / parser entrypoint thin, move scaffold templates or other
  large static payloads into dedicated resource modules, and keep command names,
  flags, and test-visible helper contracts compatible.
- For governance refactors, prefer `facade + parts` over a mega helper:
  backend facade keeps stable import/route/CLI contract, parts modules own
  concrete responsibilities (query, orchestration, runtime, cleanup).
- When a governance-heavy controller or facade is split, add at least one
  transport-level or contract-level sentinel test so regressions are caught
  above the service mock layer.
- When controller-local workflow/presenter logic is extracted into a dedicated
  service, add both:
  - a route contract sentinel for the transport seam
  - a service unit test for the extracted workflow rules (validation, commit,
    token issuance, response shaping, or similar)
- Plugin admin write-side workflows follow the same rule:
  if `admin/plugins.py` sheds notifications, menu override orchestration,
  cleanup, or license flows into `plugin_admin_workflow_service.py`, keep both
  the route contract tests and workflow unit tests in the same change.
- Plugin install-preview workflows (marketplace/upload preview + confirm +
  token validation) must live in `plugin_install_preview_service.py`; keep
  `plugin_install_preview.py` and `admin/plugins.py` transport-only, and
  preserve `test_admin_plugin_marketplace_contract.py` as the route sentinel.
- For plugin lifecycle/runtime governance, prefer `facade + mixin/parts`:
  facade keeps supported exports and assembly, while orchestrator parts own
  lifecycle execution paths. Current reference shape:
  `lifecycle.py(443)` + `lifecycle_orchestrator.py(987)`.
- Plugin platform and codegen backend changes should follow responsibility seams
  explicitly (`runtime registry/lifecycle`, `read model`, `cleanup`, `generator`,
  `config manager`, `transport adapter`) rather than one mixed service.
- Shared backend helpers should expose narrow contracts so callers do not need
  repository/query/runtime internals to use them correctly.
- AI runtime or routing changes that touch model-facing instruction text should
  pass `python scripts/check_prompt_contracts.py` and add or update prompt
  contract resources instead of hardcoding new strings inline.
- Tests must not depend on a real database, Redis, network, or third-party API.
- Reuse fixtures and mock factories from `backend/tests/services/conftest.py`.
- Many service tests instantiate services with `__new__` and inject `db`,
  `tenant_id`, and `repo` manually; follow that existing pattern.
- Async service tests should use `pytest.mark.asyncio`.
- If a route-level test only needs one controller module but the package
  `__init__` imports unrelated out-of-scope modules, direct-load the target
  file instead of broad-importing the whole package. Keep the test focused on
  the touched transport contract.
- For uploads, quotas, traces, plugins, and domain isolation, include at least
  one real-path validation step in addition to unit tests.
- New RBAC-aware controllers should update `@permission_resource`,
  `parent_resource`, and the matching `messages.json` action translations in the
  same change.
- Controller-level `db.execute(...)`, `session.execute(...)`, or ad-hoc ORM
  query construction is a design smell by default. Move that query into the
  owning service, repository, or a dedicated query helper unless the module is a
  true low-level infrastructure endpoint.
- For menu-less RBAC controllers that mount actions via `parent_resource`,
  ensure the parent menu controller is imported first in
  `backend/app/api/{scope}/__init__.py`; otherwise synced permissions will get
  `parent_id=null` and appear as orphan/root operations in `/permissions`.
- Secondary permission-tree consumers (for example
  `/admin/plans/available-permissions`) must reuse the shared
  `PermissionService` translation and parent-fill helpers instead of re-rolling
  fallback logic, or plugin titles can degrade to `title` and ancestor menus can
  disappear.
- Tenant organization nodes that support direct permission assignment must
  enforce the leader-only rule at the API layer: only the current node leader
  or an ancestor organization leader may submit `permission_ids`; non-leaders
  may view but must not mutate assignments.
- Plugin permission changes should continue to use
  `sync_plugin_permissions(plugin.name)` instead of broad ad-hoc refreshes.
- Row-level permission changes should be validated through the repository/base
  filtering path, not only through service mocks.
- New code comments, docstrings, `TODO`, or `FIXME` notes must follow the
  repo's bilingual comment convention when comments are necessary.

Examples:

- `backend/tests/services/conftest.py`
- `backend/tests/services/test_attachment_service.py`
- `backend/tests/services/test_ai_quota_runtime_diagnostics.py`

## Bilingual Comment Convention

- Comments are mandatory when the logic is complex, easy to misread, subtly
  ordered, compatibility-sensitive, repetitive enough to hide intent, or likely
  to be forgotten during later maintenance.
- Every retained code comment, docstring, `TODO`, and `FIXME` must include both
  Chinese and English. Prefer Chinese first, then English, with explicit
  `中文:` and `EN:` labels.
- Keep comments concise and explain the reason or invariant, not the obvious
  syntax. If a small refactor would make the code self-explanatory, refactor
  first; if the domain rule or execution order is still non-obvious, keep the
  bilingual comment immediately above the block it protects.
- Use this shape for ordinary comments:

```python
# 中文: 先锁定租户计划，再计算覆盖值，避免把无计划状态误判为无限制。
# EN: Resolve the tenant plan before overrides so missing plans never become unlimited.
```

- Use this shape for docstrings:

```python
def resolve_quota_boundary(...):
    """中文: 汇总计划、租户覆盖值和平台上限，得到最终配额边界。

    EN: Combines the plan, tenant overrides, and platform ceiling into the
    effective quota boundary.
    """
```

- Use this shape for follow-up notes:

```python
# TODO: 中文: 收敛临时导入迁移后删除这个稳定入口分支。
# TODO: EN: Remove this stable-entry branch after the temporary import migration converges.
```

## Dev-only Bootstrap Credential for Local E2E

- Local bootstrap credentials must only be issuable when
  `APP_ENV=development` and `DEV_BOOTSTRAP_AUTH_ENABLED=true` is set;
  production, shared CI, or cloud runners must never call this flow.
- The backend must refuse bootstrap requests that do not originate from
  loopback or local-dev hosts (`localhost`, `127.0.0.1`, `::1`, `*.local`) and
  must validate secrets sourced from each developer's personal `backend/.env`
  file:
  `DEV_ADMIN_BOOTSTRAP_SECRET`, `DEV_TENANT_BOOTSTRAP_SECRET`. Track only
  clearly marked placeholders in `.env.example` so real secrets are never
  checked in.
- The backend target identities must come from local config, not request-time
  free-form user selection. Use `DEV_ADMIN_BOOTSTRAP_USERNAME`,
  `DEV_TENANT_BOOTSTRAP_USERNAME`, and `DEV_TENANT_BOOTSTRAP_TENANT_CODE`.
- Bootstrap JWTs must expire and align with existing session TTL/refresh
  guarantees; never ship a forever token or drop the `exp` claim so these
  credentials cannot live indefinitely.
- Playwright/local browser helpers must use this dev bootstrap path for
  authenticated local e2e suites through `POST /admin/auth/dev/bootstrap`,
  `POST /tenant/auth/dev/bootstrap`, or the matching user-surface dev bootstrap
  endpoint. Missing bootstrap configuration makes the smoke blocked or skipped;
  checked-in smoke helpers must not fall back to legacy `/auth/login` routes.
- Document the feature flag, allowlisted hosts, target selectors, and required
  local secrets in repo guides so every developer can reproduce the handshake
  without sharing real secrets.

## Testing Requirements

### Service changes

- Cover happy path, boundary conditions, and failure branches.
- Prefer multiple focused cases over one oversized integration test.

### Upload, visibility, and storage work

- Run targeted attachment/storage tests.
- Validate visibility-sensitive behavior, not only upload success.
- Prefer browser validation with chrome-devtools first; use Playwright when file
  upload or multi-tab behavior makes it necessary.

Examples:

- `backend/tests/services/test_attachment_service.py`
- `backend/tests/test_storage_plugins.py`

### Trace, error, and logging work

- Verify user-visible errors preserve `trace_id`.
- Verify `novusai trace show <trace_id>` remains a usable operator entrypoint.
- If the change affects frontend-visible failures, confirm the UI still shows
  one coherent error path rather than duplicate toasts.
- For AI streaming fallback fixes, validate both "upstream fails before first
  chunk" and "stream returns no meaningful chunk" scenarios so the user never
  receives a silent empty assistant turn.
- For Responses-stream usage backfill fixes, validate the "terminal event has no
  usage" path as well: stream completion must stay bounded and fall back to
  estimated usage instead of waiting through long SDK/provider retries.

### AI quota, rate limit, or AI logging work

- Do not stop after lint or type checks.
- Validate runtime behavior, queue consumption, and diagnostics fields where
  relevant.
- When AI call logging or task signatures change, verify the worker is running
  the new code and consuming the `ai_gateway` queue.
- If the UI depends on those logs or limits, validate the full operator path,
  not just the backend return payload.
- For datetime-bearing APIs, verify hand-built dict payloads do not leak naive
  UTC strings such as `2026-04-03T19:00:41` without `+00:00`. Browser clients
  will parse those as local time and drift by the timezone offset.

### Recycle bin and route-order work

- For recycle-bin-enabled modules, validate the module recycle bin flow and the
  surface-specific route behavior.
- If a controller has dynamic `/{id}` style routes, confirm recycle-bin routes
  are registered early enough to avoid path-parameter collisions.

## Code Review Checklist

Before merge, confirm:

- The code lives in the correct layer.
- The changed modules remain high-cohesion and low-coupling; no new sideways
  dependency or boundary bypass was introduced.
- Any oversized backend file was reduced by responsibility boundary, not by
  arbitrary textual chunking.
- Tenant vs global scope is correct.
- Admin, tenant, and user surface boundaries remain intact.
- i18n, permission, menu, trace, migration, and tests are updated together when
  required.
- Controllers are thin and services carry business logic.
- Repositories own data access.
- Any new model is exported and migration-registered.
- Any new task is registered with `@register_task` and reachable by the worker.
- Any API response that bypasses `BaseSchema` still serializes datetimes through
  the shared UTC-safe path instead of direct `.isoformat()` on ORM values.

## Governance Refactor Acceptance Gates

When a change claims backend governance/file-splitting completion, reviewers must
see all of the following:

- Controller query boundary check:
  no new direct DB query assembly in touched `backend/app/api/**` modules.
  Any exception requires explicit infrastructure-endpoint waiver in task docs.
- Public contract check:
  public route names, CLI command names/options, and supported import-visible
  helpers stay stable unless migration notes explicitly record a breaking
  contract change.
- Split-seam check:
  refactor uses responsibility seams (facade + mixin/parts), not arbitrary
  line-count chunking or a new miscellaneous helper sink.
- Workstream ownership check:
  touched files align with `.trellis` ownership matrix for the active umbrella task.

## Real Examples To Follow

- Service/unit-test style:
  - `backend/tests/services/test_attachment_service.py`
  - `backend/tests/services/test_agent_service.py`
- Trace/log aware task implementation:
  - `backend/app/tasks/ai.py`
- Layered tenant CRUD:
  - `backend/app/api/tenant/domains.py`
  - `backend/app/services/system/tenant_domain_service.py`
  - `backend/app/repositories/tenant/tenant_domain_tenant_repository.py`
