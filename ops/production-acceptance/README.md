# Production Acceptance Gates

This runbook records the executable local acceptance gates used before claiming
SaaS delivery readiness. The probe reports each gate as `passed`, `failed`, or
`blocked`.

## Command

Run from `backend/` while the local API, frontend, PostgreSQL, Redis, and Docker
are available:

```powershell
.\.venv\Scripts\python.exe scripts\production_acceptance_probe.py `
  --api-base-url http://localhost:8000 `
  --frontend-base-url http://localhost:5666 `
  --load-smoke-requests 32 `
  --load-smoke-concurrency 8 `
  --capacity-requests 96 `
  --capacity-concurrency 16 `
  --capacity-p95-budget-ms 1500 `
  --capacity-error-budget-ratio 0 `
  --run-backup-restore-drill `
  --run-security-scans `
  --run-dast-baseline `
  --dast-target-url http://localhost:8000 `
  --artifact-dir ops\acceptance-artifacts `
  --allow-blocked `
  --timeout 5
```

## Latest Local Result

Last local run: 2026-05-08, Asia/Shanghai.

Overall status: `blocked`

Summary: `19 passed`, `3 blocked`, `0 failed`.

Passed gates:

- API readiness: `/ready` returned `ready=true`.
- API health: `/health` returned `healthy` with Redis connected.
- Prometheus metrics: `/metrics` returned the expected exposition.
- Frontend root: `http://localhost:5666` returned success.
- Capacity harness: built-in Python HTTP benchmark available.
- Capacity benchmark: 96 requests, concurrency 16, zero errors, p95 under the
  1500 ms budget.
- PostgreSQL backup/restore: Docker `pg_dump`, `pg_restore`, and `psql` were
  available; disposable restore completed, Alembic heads matched, and 94 public
  tables were restored.
- Python dependency audit: `pip-audit --local --skip-editable` completed with
  no known vulnerabilities.
- Python SAST: `bandit -ll` completed with no medium/high findings.
- Frontend dependency audit: both `pnpm audit --audit-level high` and
  `pnpm audit --prod --audit-level high` completed with zero high/critical
  findings.
- OWASP ZAP baseline: Docker ZAP scan completed with `FAIL-NEW: 0`.

Blocked gates:

- AI provider credentials are not configured in this environment.
- AI smoke agent selector is not configured (`AI_SMOKE_AGENT_ID` or
  `AI_SMOKE_AGENT_CODE`).
- Real-dialogue smoke execution has no archived passed report.

## AI Real-Dialogue Smoke

The probe intentionally does not mark AI dialogue production acceptance as
passed without real external evidence. To clear the remaining blocked gates:

1. Configure a real provider credential in `backend/.env` or the process
   environment.
2. Configure `AI_SMOKE_AGENT_ID` or `AI_SMOKE_AGENT_CODE`.
3. Run the AI smoke command against the scenarios in
   `ops/ai-smoke/smoke-scenarios.md`.
4. Archive a report with `overall_status: passed` and per-scenario pass/fail
   results, then pass the report path to the probe with `--ai-smoke-report`.

Example:

```powershell
.\.venv\Scripts\python.exe -m app.cli ai smoke --agent-id <id> --json `
  > ..\ops\acceptance-artifacts\ai-real-dialogue-smoke.json

.\.venv\Scripts\python.exe scripts\production_acceptance_probe.py `
  --api-base-url http://localhost:8000 `
  --frontend-base-url http://localhost:5666 `
  --ai-smoke-report ..\ops\acceptance-artifacts\ai-real-dialogue-smoke.json `
  --allow-blocked
```

## Artifact Policy

Generated local artifacts live under `ops/acceptance-artifacts/` and are ignored
by Git. Regenerate them during release verification instead of treating one
developer machine's scan output as source.
