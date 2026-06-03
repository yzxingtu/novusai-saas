# NovusAI Production Acceptance Runbook

Date: 2026-05-08

## Scope

This runbook turns the remaining production delivery risks into repeatable
commands. A gate is accepted only when the command proves it in the current
environment. Missing tools, missing credentials, missing targets, and missing
human approval remain `blocked`.

Code and Compose readiness are not the same as external production acceptance.
A local probe can prove the repo-owned stack shape, but public release signoff
still requires the external capacity, restore, security, DAST, observability,
and AI real-dialogue evidence recorded by these gates.

Release and customer sync signoff must also satisfy the branch, tag, changelog,
upgrade-note, and Yudi base metadata gate in
[`release-backport-policy.md`](./release-backport-policy.md).

## Probe

Run the broad probe from `backend/`:

```powershell
.\.venv\Scripts\python.exe scripts\production_acceptance_probe.py `
  --api-base-url http://localhost:8000 `
  --frontend-base-url http://localhost:5666 `
  --load-smoke-requests 32 `
  --load-smoke-concurrency 8 `
  --allow-blocked
```

This command should prove readiness and monitoring, but it does not run the
expensive or credentialed gates unless the flags below are provided.
`--allow-blocked` only changes the process exit code when no gate failed; it
does not turn missing credentials, missing tools, or missing archived smoke
evidence into `passed` acceptance.

## Capacity

Local benchmark:

```powershell
.\.venv\Scripts\python.exe scripts\production_acceptance_probe.py `
  --api-base-url http://localhost:8000 `
  --capacity-requests 128 `
  --capacity-concurrency 16 `
  --capacity-p95-budget-ms 1000 `
  --capacity-error-budget-ratio 0 `
  --allow-blocked
```

This is a local benchmark across public app, readiness, health, and metrics
endpoints. It is not a production capacity signoff. Formal capacity acceptance
still needs target environment, expected throughput, duration, SLO budgets, and
operator signoff. k6 or Locust can be used for that formal plan; the probe keeps
their absence visible through the tooling gate.

## PostgreSQL Backup / Restore

Start local PostgreSQL first:

```powershell
docker compose -f ..\docker-compose.dev.yml up -d postgres
```

Then run a disposable restore drill:

```powershell
.\.venv\Scripts\python.exe scripts\production_acceptance_probe.py `
  --run-backup-restore-drill `
  --postgres-container novusai-postgres-dev `
  --postgres-db novusai_saas `
  --postgres-user postgres `
  --allow-blocked
```

The drill creates a generated database named `novusai_restore_drill_*`, restores
into it, verifies Alembic/public-table evidence, and drops it. Do not point this
at production. A production restore drill must use an approved disposable target.

## Security Scans

Run backend dependency audit, backend SAST, and frontend dependency audit:

```powershell
.\.venv\Scripts\python.exe scripts\production_acceptance_probe.py `
  --run-security-scans `
  --allow-blocked
```

The probe runs:

- `python -m pip_audit --local --progress-spinner off`
- `python -m bandit -r app scripts -x .venv,migrations,plugins/.backups,tests -ll`
- `pnpm audit --prod --audit-level high --registry https://registry.npmjs.org --json`

Passing these gates does not replace DAST or manual threat-model review for
public routes.

## DAST

DAST is intentionally opt-in because it requires OWASP ZAP or a local Docker
image:

```powershell
.\.venv\Scripts\python.exe scripts\production_acceptance_probe.py `
  --run-dast-baseline `
  --dast-target-url http://host.docker.internal:8000 `
  --allow-dast-pull `
  --allow-blocked
```

Without `--allow-dast-pull`, the probe only uses an already-local ZAP image or a
native `zap-baseline.py` command. Missing ZAP tooling remains `blocked`.

## AI Real-Dialogue Smoke

Scenario ledger:

```text
ops/ai-smoke/smoke-scenarios.md
```

Run against a real provider and archive the report:

```powershell
python -m app.cli ai real-dialogue-smoke --agent-id <id> --raw-json `
  > ..\.trellis\tasks\<task-id>\smoke-runs\<milestone>\report.json
```

Then pass the report to the probe:

```powershell
.\.venv\Scripts\python.exe scripts\production_acceptance_probe.py `
  --ai-smoke-agent-id <id> `
  --ai-smoke-report ..\.trellis\tasks\<task-id>\smoke-runs\<milestone>\report.json `
  --allow-blocked
```

Do not mark AI dialogue production acceptance as passed unless provider
credentials, an agent selector, the scenario ledger, and an archived passed smoke
report all exist. Hand-written LLM mocks do not satisfy this gate.

The report must be strict JSON with `schema_version:
ai-real-dialogue-smoke/v1`, `report_type: ai_real_dialogue_smoke`,
`execution_kind: real_dialogue`, matching ledger hash, and provider call-log
evidence for every must-pass scenario. The legacy `ai smoke` command is a
capability-manifest check only; it does not prove a real provider-backed turn.

By default, the report's `repo.commit` must match current `HEAD` and
`repo.dirty` must be exactly `false`. If later documentation or evidence commits
move `HEAD` beyond the runtime commit that generated the report, pass the
runtime commit explicitly:

```powershell
.\.venv\Scripts\python.exe scripts\production_acceptance_probe.py `
  --ai-smoke-agent-id <id> `
  --ai-smoke-report ..\.trellis\tasks\<task-id>\smoke-runs\<milestone>\report.json `
  --ai-smoke-accepted-runtime-commit <accepted-runtime-commit> `
  --allow-blocked
```

This is only for rechecking archived evidence after documentation-only drift.
The probe blocks reuse when backend/frontend runtime code, migrations,
production Compose, deployment scripts, production env examples, capacity plans,
or Prometheus scrape/rule files changed after the accepted runtime commit.

In probe output, `ai_runtime_smoke_cli` and
`ai_real_dialogue_smoke_scenarios` are prerequisite/readiness checks only. They
do not satisfy `ai_provider_credentials`, `ai_smoke_agent_selector`, or
`ai_real_dialogue_smoke_execution`.
